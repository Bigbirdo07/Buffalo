"""Group diseases by convergent mechanistic evidence.

A cluster is a claim that several diseases disrupt comparable biology. That is a
stronger claim than any pairwise retrieval makes, so the graph it runs on is
built conservatively.

**Only molecularly anchored edges may form clusters.** A pair linked solely by
phenotype and anatomy can share a clinical picture with no common mechanism --
cerebellar atrophy plus Purkinje involvement is shared by acute viral
encephalitis and genetic ataxias alike. Admitting those edges would produce
large, confident, biologically empty clusters, which is the single most likely
way for this kind of system to mislead. Phenotype overlap is reported inside a
cluster, never used to build one.

**Edges are weighted by information content, not by count.** Two diseases sharing
one rare molecular function are more alike than two sharing five ubiquitous
process terms.

**Not every disease belongs to a cluster.** Singletons are the expected majority
and are reported as NO_DEFENSIBLE_CLUSTER rather than forced into a neighbour.

Methods are compared rather than chosen in advance, because community detection
optimises modularity -- a property of the graph -- while what matters here is
whether a group of diseases is biologically coherent. The audit reports both.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from enum import StrEnum

import networkx as nx

from atlas.services.candidate_generation import (
    Candidate,
    FeatureIndex,
    generate_candidates,
)

CLUSTERING_VERSION = "mechanism-cluster-v1"

# An edge needs a molecular anchor and at least this much shared information.
# Below it, a pair shares little beyond terms common enough to be uninformative.
MIN_EDGE_INFORMATION = 8.0

# A feature may *anchor* an edge only if it is this specific. Retrieval is
# permissive (5% of the corpus) because a broad match is still worth looking at;
# anchoring is a far stronger claim and is held to 1%.
#
# This came from a measured failure, not from theory. With one threshold for
# both, TP53 anchored 1,025 edges across 98 diseases and the graph's highest
# degree nodes were Alzheimer disease, lupus and four carcinomas. "Both diseases
# involve TP53" is not a mechanism claim: most cancers involve TP53. STUB1, by
# contrast, appears in 3 diseases and anchors meaningfully.
ANCHOR_MAX_CORPUS_FREQUENCY = 33

# Louvain resolution. Higher values produce smaller, tighter communities.
#
# The default is high because modularity and biological interpretability pull in
# opposite directions here, and this project optimises for the second. Measured
# on the real graph (3,082 nodes, 24,529 edges):
#
#     resolution   clusters   largest   median   modularity
#              1         29       341       94        0.723
#              8        101        91       30        0.623
#             15        160        51       18        0.555
#             25        230        39       13        0.494
#
# Modularity peaks at resolution 1, which yields a 341-member "cluster" that
# states nothing biological. At 15 the SCAR16 community is 15 diseases and has a
# core a biologist can check: STUB1 disorders alongside Lafora disease, PRKN
# Parkinson, CBL-related disorder, Opitz G/BBB and CMT2P -- malin, parkin, CBL,
# MID1 and LRSAM1 are all E3 ubiquitin ligases. Choosing by modularity alone
# would have discarded that result.
LOUVAIN_RESOLUTION = 15.0

# Labelling a cluster needs a feature present in most members; otherwise the
# cluster has no statable shared core and says so.
CORE_FEATURE_FRACTION = 0.6


class ClusterMethod(StrEnum):
    LOUVAIN = "louvain"
    LABEL_PROPAGATION = "label_propagation"
    GREEDY_MODULARITY = "greedy_modularity"
    CONNECTED_COMPONENTS = "connected_components"


@dataclass(frozen=True)
class MechanismEdge:
    left_id: str
    right_id: str
    information: float
    anchor_axes: tuple[str, ...]
    shared_feature_ids: tuple[str, ...]
    shared_labels: tuple[str, ...]


@dataclass
class MechanismCluster:
    cluster_id: str
    method: str
    member_ids: tuple[str, ...]
    member_names: tuple[str, ...]
    # Features present in at least CORE_FEATURE_FRACTION of members: the reason
    # these diseases are together, stated in their own terms.
    shared_core: tuple[tuple[str, str, int], ...] = ()
    internal_edges: int = 0
    mean_edge_information: float = 0.0
    # Features in some members but not others. A cluster is only useful if its
    # differences are as visible as its similarities.
    distinguishing: tuple[tuple[str, str, int], ...] = ()
    caveats: tuple[str, ...] = field(default_factory=tuple)

    @property
    def size(self) -> int:
        return len(self.member_ids)

    @property
    def has_statable_core(self) -> bool:
        return bool(self.shared_core)

    @property
    def canonical_label(self) -> str:
        if not self.shared_core:
            return "NO_DEFENSIBLE_CLUSTER"
        return " + ".join(label for _id, label, _n in self.shared_core[:3])


def anchor_axes(
    candidate: Candidate, *, max_frequency: int = ANCHOR_MAX_CORPUS_FREQUENCY
) -> tuple[str, ...]:
    """Axes qualifying a pair as molecularly anchored.

    An axis anchors only through a feature specific enough to mean something: a
    hub gene shared by a hundred diseases describes a research area, not a
    mechanism. See ANCHOR_MAX_CORPUS_FREQUENCY for the measured reason.
    """
    found: list[str] = []
    for method, features in candidate.methods.items():
        if method not in {
            "SHARED_GENE_OR_PROTEIN",
            "SHARED_MOLECULAR_FUNCTION",
            "SHARED_CELLULAR_PROCESS",
        }:
            continue
        if any(item.corpus_frequency <= max_frequency for item in features):
            found.append(method)
    return tuple(sorted(found))


def build_mechanism_graph(
    index: FeatureIndex,
    *,
    neighbours_per_disease: int = 30,
    min_information: float = MIN_EDGE_INFORMATION,
) -> tuple[nx.Graph, dict[str, int]]:
    """Build the undirected disease graph clusters are detected on."""
    graph: nx.Graph = nx.Graph()
    stats: Counter[str] = Counter()
    for record in index.fingerprints:
        graph.add_node(record["disease_id"], name=record["disease_name"])

    for record in index.fingerprints:
        disease_id = record["disease_id"]
        for candidate in generate_candidates(
            index, disease_id, limit=neighbours_per_disease
        ):
            stats["pairs_considered"] += 1
            axes = anchor_axes(candidate)
            if not axes:
                stats["rejected_no_molecular_anchor"] += 1
                continue
            information = candidate.total_information
            if information < min_information:
                stats["rejected_low_information"] += 1
                continue
            if graph.has_edge(disease_id, candidate.disease_id):
                continue
            shared = candidate.top_features(limit=50)
            graph.add_edge(
                disease_id,
                candidate.disease_id,
                weight=information,
                anchor_axes=axes,
                shared_feature_ids=tuple(item.feature_id for item in shared),
                shared_labels=tuple(item.label for item in shared),
            )
            stats["edges"] += 1
    return graph, dict(stats)


def detect(
    graph: nx.Graph,
    method: ClusterMethod,
    *,
    seed: int = 0,
    resolution: float = LOUVAIN_RESOLUTION,
) -> list[set[str]]:
    """Run one community-detection method. Seeded, so runs are reproducible."""
    working = graph.subgraph([n for n in graph if graph.degree(n) > 0]).copy()
    if working.number_of_nodes() == 0:
        return []
    if method is ClusterMethod.LOUVAIN:
        return [
            set(community)
            for community in nx.community.louvain_communities(
                working, weight="weight", seed=seed, resolution=resolution
            )
        ]
    if method is ClusterMethod.LABEL_PROPAGATION:
        return [
            set(community)
            for community in nx.community.asyn_lpa_communities(
                working, weight="weight", seed=seed
            )
        ]
    if method is ClusterMethod.GREEDY_MODULARITY:
        return [
            set(community)
            for community in nx.community.greedy_modularity_communities(
                working, weight="weight", resolution=resolution
            )
        ]
    return [set(component) for component in nx.connected_components(working)]


def describe_cluster(
    index: FeatureIndex,
    graph: nx.Graph,
    members: set[str],
    method: str,
    cluster_id: str,
) -> MechanismCluster:
    """Say why these diseases are together, and how they differ."""
    ordered = sorted(members)
    counts: Counter[str] = Counter()
    labels: dict[str, str] = {}
    for disease_id in ordered:
        record = index.by_id[disease_id]
        for feature in record["features"]:
            feature_id = feature["feature_id"]
            if not index.is_retrievable(feature_id):
                continue
            counts[feature_id] += 1
            labels.setdefault(feature_id, feature["label"])

    threshold = max(2, int(len(ordered) * CORE_FEATURE_FRACTION))
    core = [
        (feature_id, labels[feature_id], count)
        for feature_id, count in counts.most_common()
        if count >= threshold
    ]
    core.sort(key=lambda row: (-index.ic(row[0]), row[0]))
    distinguishing = [
        (feature_id, labels[feature_id], count)
        for feature_id, count in counts.most_common(40)
        if 1 < count < threshold
    ]

    internal = graph.subgraph(ordered)
    weights = [data["weight"] for _a, _b, data in internal.edges(data=True)]
    caveats: list[str] = []
    if not core:
        caveats.append(
            "No feature is shared by most members, so this group has no statable "
            "mechanistic core and should not be presented as a mechanism cluster."
        )
    if len(ordered) > 12:
        caveats.append(
            "Large cluster: community detection merges weakly connected groups, so "
            "members at opposite ends may share nothing directly."
        )
    density = nx.density(internal) if internal.number_of_nodes() > 1 else 0.0
    if density < 0.3 and len(ordered) > 3:
        caveats.append(
            f"Sparse cluster (density {density:.2f}): most member pairs are not "
            "directly linked and were grouped transitively."
        )

    return MechanismCluster(
        cluster_id=cluster_id,
        method=method,
        member_ids=tuple(ordered),
        member_names=tuple(index.by_id[item]["disease_name"] for item in ordered),
        shared_core=tuple(core[:8]),
        internal_edges=internal.number_of_edges(),
        mean_edge_information=round(sum(weights) / len(weights), 2) if weights else 0.0,
        distinguishing=tuple(distinguishing[:10]),
        caveats=tuple(caveats),
    )


def cluster_corpus(
    index: FeatureIndex,
    graph: nx.Graph,
    method: ClusterMethod,
    *,
    min_size: int = 2,
) -> tuple[list[MechanismCluster], list[str]]:
    """Cluster the graph and return clusters plus unclustered diseases."""
    communities = detect(graph, method)
    clusters: list[MechanismCluster] = []
    clustered: set[str] = set()
    for position, members in enumerate(
        sorted(communities, key=lambda item: (-len(item), sorted(item)[0]))
    ):
        if len(members) < min_size:
            continue
        clusters.append(
            describe_cluster(
                index, graph, members, method.value, f"{method.value}-{position:04d}"
            )
        )
        clustered |= members
    unclustered = sorted(set(graph.nodes) - clustered)
    return clusters, unclustered


def compare_methods(index: FeatureIndex, graph: nx.Graph) -> dict[str, object]:
    """Compare methods on interpretability, not modularity alone.

    Modularity measures how well a partition fits the graph. It says nothing
    about whether a group of diseases is biologically coherent, so the figure
    reported alongside it is the share of clusters with a statable shared core.
    """
    report: dict[str, object] = {}
    for method in ClusterMethod:
        clusters, unclustered = cluster_corpus(index, graph, method)
        working = graph.subgraph([n for n in graph if graph.degree(n) > 0])
        communities = detect(graph, method)
        modularity = (
            round(nx.community.modularity(working, communities, weight="weight"), 4)
            if communities
            else 0.0
        )
        with_core = [item for item in clusters if item.has_statable_core]
        sizes = sorted((item.size for item in clusters), reverse=True)
        report[method.value] = {
            "clusters": len(clusters),
            "clustered_diseases": sum(item.size for item in clusters),
            "unclustered_diseases": len(unclustered),
            "modularity": modularity,
            "clusters_with_statable_core": len(with_core),
            "share_with_core": round(len(with_core) / len(clusters), 3) if clusters else 0.0,
            "largest_cluster": sizes[0] if sizes else 0,
            "median_cluster_size": sizes[len(sizes) // 2] if sizes else 0,
            "clusters_over_12_members": sum(1 for size in sizes if size > 12),
        }
    return report


def feature_overlap_between(
    index: FeatureIndex, left_id: str, right_id: str
) -> dict[str, list[str]]:
    """Shared retrievable features between two diseases, grouped by class."""
    left = {
        item["feature_id"]: item
        for item in index.by_id[left_id]["features"]
        if index.is_retrievable(item["feature_id"])
    }
    grouped: defaultdict[str, list[str]] = defaultdict(list)
    for item in index.by_id[right_id]["features"]:
        if item["feature_id"] in left:
            grouped[item["feature_class"]].append(item["label"])
    return {key: sorted(value) for key, value in sorted(grouped.items())}
