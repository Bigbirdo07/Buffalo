"""Transparent local graph algorithms used before Neo4j projection."""

from __future__ import annotations

from collections import defaultdict, deque

from atlas.domain.claims import RefinementStatus
from atlas.domain.gaps import (
    GapPriorityDimensions,
    GapType,
    KnowledgeGap,
    pending_search_coverage,
)
from atlas.domain.mechanism import MechanismEdge, MechanismGraph


def downstream_reach(graph: MechanismGraph, edge: MechanismEdge) -> int:
    """Count distinct nodes downstream of an edge's object, including itself."""
    adjacency: dict[str, list[str]] = defaultdict(list)
    for candidate in graph.edges:
        adjacency[candidate.subject_id].append(candidate.object_id)
    seen: set[str] = set()
    queue: deque[str] = deque([edge.object_id])
    while queue:
        node = queue.popleft()
        if node in seen:
            continue
        seen.add(node)
        queue.extend(adjacency[node])
    return len(seen)


def longest_causal_chain(graph: MechanismGraph) -> int:
    """Edge count of the longest simple causal chain (mechanistic depth).

    Edges that would close a cycle on the current path are skipped, so the
    result is defined for cyclic graphs; memoization makes it a lower bound in
    rare multi-cycle shapes, which is acceptable for a visible ranking dimension.
    """
    adjacency: dict[str, list[str]] = defaultdict(list)
    for edge in graph.edges:
        adjacency[edge.subject_id].append(edge.object_id)
    memo: dict[str, int] = {}

    def depth(node: str, on_path: frozenset[str]) -> int:
        if node in memo:
            return memo[node]
        best = 0
        for child in adjacency[node]:
            if child not in on_path:
                best = max(best, 1 + depth(child, on_path | {child}))
        memo[node] = best
        return best

    return max((depth(node, frozenset({node})) for node in list(adjacency)), default=0)


def structural_gap_candidates(graph: MechanismGraph) -> tuple[KnowledgeGap, ...]:
    """Create review candidates for consequential unreviewed/weak causal edges.

    This does not assert an evidence absence. Every candidate receives a pending
    search-coverage scaffold so absence language cannot precede retrieval.
    """
    node_label = {node.id: node.label for node in graph.nodes}
    weak_statuses = {
        RefinementStatus.UNREVIEWED,
        RefinementStatus.PARTIALLY_SUPPORTED,
        RefinementStatus.CONTEXT_DEPENDENT,
        RefinementStatus.INSUFFICIENT_EVIDENCE,
        RefinementStatus.CONTRADICTED,
    }
    result: list[KnowledgeGap] = []
    for edge in graph.edges:
        if edge.status not in weak_statuses:
            continue
        reach = downstream_reach(graph, edge)
        if reach < 2:
            continue
        subject = node_label.get(edge.subject_id, edge.subject_id)
        object_ = node_label.get(edge.object_id, edge.object_id)
        gap_id = f"structural-gap:{edge.id}"
        result.append(
            KnowledgeGap(
                gap_id=gap_id,
                question=f"Does {subject} causally contribute to {object_} in the stated context?",
                gap_type=GapType.UNSUPPORTED_CAUSAL_TRANSITION,
                related_claims=(edge.claim_id,),
                related_edges=(edge.id,),
                scope="Structural review candidate; literature search not yet performed",
                why_it_matters=(
                    f"At least {reach} downstream mechanism node(s) depend on this transition."
                ),
                current_evidence_summary="Edge has not completed independent evidence refinement.",
                contradictory_evidence_summary="Not yet assessed.",
                search_coverage=pending_search_coverage(f"coverage:{gap_id}"),
                missing_evidence_type=("Independent claim-evidence fit review",),
                required_context=edge.contexts,
                priority_reason=GapPriorityDimensions(
                    causal_centrality="candidate bridge in the imported causal path",
                    downstream_dependence=f"{reach} downstream node(s) reachable",
                    evidence_conflict="not assessed",
                    translational_relevance="not assessed",
                    experimental_tractability="not assessed",
                    available_assets="not assessed",
                    discriminates_competing_hypotheses="not assessed",
                ),
                resolvability="Requires evidence refinement before experiment planning",
            )
        )
    return tuple(result)

