#!/usr/bin/env python3
"""Derive a KnowledgeGap and an ExperimentProposal from a completed edge refinement.

Both objects are built from the refinement artifact, so every claim, edge and
evidence ID they cite is one the pipeline actually produced. The scientific text
is authored by the extractor model and is explicitly not expert-reviewed.

A gap is only emitted for an atomic claim whose status leaves the question open
(INSUFFICIENT_EVIDENCE, CONTEXT_DEPENDENT or CONTRADICTED). If the target claim
came out SUPPORTED, the script refuses rather than manufacturing a gap.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from atlas.domain.claims import RefinementStatus
from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import GapPriorityDimensions, GapType, KnowledgeGap
from atlas.domain.refinement import EdgeRefinement

OPEN_STATUSES = {
    RefinementStatus.INSUFFICIENT_EVIDENCE,
    RefinementStatus.CONTEXT_DEPENDENT,
    RefinementStatus.CONTRADICTED,
}

TARGET_CLAIM = "ac4-interdomain-missense"


def build_gap(refinement: EdgeRefinement, claim_id: str) -> KnowledgeGap:
    atomic = next(item for item in refinement.atomic if item.claim.claim_id == claim_id)
    if atomic.status not in OPEN_STATUSES:
        raise SystemExit(
            f"{claim_id} is {atomic.status.value}; refusing to manufacture a gap for a "
            "claim the evidence already settles"
        )
    siblings = {item.claim.claim_id: item for item in refinement.atomic}
    supported = [
        item.claim.normalized_statement
        for item in refinement.atomic
        if item.status is RefinementStatus.SUPPORTED
    ]
    refuting = ", ".join(atomic.direct_refuting) or "none"
    background = ", ".join(atomic.background_only) or "none"
    indirect = ", ".join(atomic.indirect) or "none"
    tpr = siblings["ac3-tpr-missense"]

    return KnowledgeGap(
        gap_id=f"gap:{refinement.upstream_edge_id}:{claim_id}",
        question=(
            "Do the SCAR16 alleles that retain bulk E3 ubiquitin ligase activity in "
            "purified recombinant assays (STUB1 p.Lys145Gln, p.Met211Ile) impair "
            "CHIP-dependent substrate ubiquitination in a substrate-selective or "
            "condition-dependent manner in disease-relevant human neurons, or do they "
            "cause SCAR16 through a mechanism other than reduced ligase output?"
        ),
        gap_type=GapType.UNTESTED_VARIANT_CLASS,
        related_claims=(refinement.upstream_claim.claim_id, claim_id),
        related_edges=(refinement.upstream_edge_id,),
        scope=(
            "Applies to the inter-domain/linker-region SCAR16 missense alleles "
            "p.Lys145Gln and p.Met211Ile. It does not apply to p.Thr246Met or to "
            "U-box-truncating alleles, for which loss of ligase activity is SUPPORTED "
            f"by this run ({'; '.join(supported)})."
        ),
        why_it_matters=(
            "This transition is the first molecular step of the upstream SCAR16 "
            "mechanism, and every downstream node in the imported pathograph depends "
            "on it. Four of the six alleles assayed in PMID:28396517 were not overtly "
            "different from wild type, so the upstream edge as worded does not hold "
            "allele-wide. Whether these patients' disease runs through reduced ligase "
            "output at all determines (a) whether the edge wording can be retained, "
            "(b) whether bulk ubiquitination is a valid assay for allele "
            "interpretation, and (c) whether strategies aimed at restoring ligase "
            "activity are even addressed at the right defect for these genotypes."
        ),
        current_evidence_summary=(
            f"No direct support. Direct refutation ({refuting}): in purified recombinant "
            "CHIP with E1/E2/ubiquitin at 37 C for 1 h, p.Glu28Lys, p.Lys145Gln, "
            "p.Met211Ile and p.Ser236Thr showed ubiquitination activity not overtly "
            "different from wild type. Indirect only "
            f"({indirect}): class-level panels report that SCAR16 mutants recover "
            "activity below their melting temperature, that all tested mutants except "
            "the U-box alleles p.Met240Thr and p.Thr246Met retain some HSP70 "
            "polyubiquitination, and that paper-described TPR and CC allele groups are "
            "not defective "
            "in E2-dependent chain formation. These panel statements do not name the "
            "alleles in scope, so they cannot settle an allele-level claim."
        ),
        contradictory_evidence_summary=(
            f"One background-only citation ({background}) states that p.Lys145Gln impairs "
            "CHIP ligase activity, but it is an introduction sentence in PMID:41851873 "
            "attributing the finding to an earlier study; that paper's own ligase result "
            "is reported for p.Gln118* only. The critic therefore classified it "
            "BACKGROUND_ONLY with causal support NONE, and it does not contribute to "
            "status. The sibling TPR claim is "
            f"{tpr.status.value}: p.Asn65Ser impairs HSC70 polyubiquitin-chain "
            "elongation while retaining self-ubiquitination. Those are distinct readouts; "
            "the experiment shows a processivity/readout-specific defect but does not "
            "establish substrate selectivity. Cross-entity SCA48 work reports TPR "
            "variants retaining intrinsic "
            "ligase activity with impaired substrate ubiquitination. Those are "
            "qualifying, not contradicting: different allele class, or different disease "
            "entity."
        ),
        search_coverage=refinement.search_coverage,
        missing_evidence_type=(
            ("Substrate-resolved ubiquitination measurement (e.g. diGly ubiquitinome or a "
            "defined CHIP client panel) for these specific alleles, rather than bulk "
            "HSC70/self-ubiquitination."),
            ("Measurement at endogenous expression level in a human neuronal cell type, "
            "rather than purified protein or overexpression."),
            ("Assays spanning physiological and proteotoxic-stress conditions, given the "
            "reported temperature dependence of SCAR16 mutant activity."),
            ("Measurement in the patients' actual compound-heterozygous configuration, not "
            "only homozygous single-allele constructs."),
        ),
        required_context=(
            "human cerebellar or cortical neuronal cell type",
            "endogenous STUB1 dosage",
            "compound-heterozygous allele configuration as found in patients",
            "physiological 37 C and proteotoxic-stress conditions",
            "substrate identity (which CHIP clients, not bulk activity)",
        ),
        priority_reason=GapPriorityDimensions(
            causal_centrality=(
                "First molecular step of the imported SCAR16 mechanism; the edge is the "
                "parent of the pathograph's downstream chain."
            ),
            downstream_dependence=(
                "All downstream nodes in the imported entry descend from this transition."
            ),
            evidence_conflict=(
                "A recombinant primary result reports no bulk defect for these alleles "
                "while a secondary citation asserts impairment; the assertion traces to "
                "a study whose own data concern different alleles."
            ),
            translational_relevance=(
                "Determines whether residual-ligase-activity modulation is a coherent "
                "target for these genotypes. No clinical claim is made here."
            ),
            experimental_tractability=(
                "Addressable with existing iPSC, CRISPR knock-in and ubiquitinome "
                "proteomics methods; a SCAR16 patient iPSC line is already reported "
                "(PMID:29679845)."
            ),
            available_assets=(
                "Published SCAR16/Gordon Holmes patient iPSC line; recombinant CHIP "
                "expression and in vitro ubiquitination protocols published in "
                "PMID:28396517 and PMID:31619515."
            ),
            discriminates_competing_hypotheses=(
                "A substrate-resolved, condition-controlled design separates "
                "substrate-selective ligase failure from conditional destabilization and "
                "from non-ligase (co-chaperone) dysfunction."
            ),
        ),
        resolvability=(
            "Experimentally resolvable. The discriminating measurement is substrate-level "
            "ubiquitination in isogenic human neurons carrying these alleles at "
            "endogenous dosage, assayed at 37 C and under proteotoxic stress."
        ),
        proposed_discriminating_test=(
            "Substrate-resolved ubiquitinome comparison of isogenic neurons carrying "
            "p.Lys145Gln or p.Met211Ile against isogenic wild type, with p.Thr246Met as a "
            "bulk-loss comparator, at 37 C and after heat stress."
        ),
        status="OPEN",
    )


def build_experiment(gap: KnowledgeGap) -> ExperimentProposal:
    return ExperimentProposal(
        experiment_id=f"experiment:{gap.gap_id}",
        knowledge_gap_id=gap.gap_id,
        scientific_question=gap.question,
        hypothesis=(
            "STUB1 p.Lys145Gln and p.Met211Ile reduce CHIP-dependent ubiquitination of a "
            "restricted subset of CHIP client proteins in human neurons at endogenous "
            "dosage, and/or lose activity under proteotoxic stress, despite retaining "
            "bulk HSC70 and self-ubiquitination activity in purified recombinant assays."
        ),
        competing_hypothesis=(
            "These alleles do not measurably reduce CHIP-dependent substrate "
            "ubiquitination in neurons under any tested condition, and their "
            "pathogenicity arises from a non-ligase CHIP function (chaperone client "
            "handling or complex assembly) or from reduced protein stability in the "
            "compound-heterozygous state."
        ),
        model_system=(
            "Human iPSC-derived neurons (cerebellar Purkinje-like and cortical "
            "populations differentiated from the same donor background)"
        ),
        sample_type=(
            "Isogenic iPSC lines: CRISPR knock-in STUB1 p.Lys145Gln and p.Met211Ile "
            "(homozygous, and in trans with a U-box-truncating allele to match patient "
            "configuration), p.Thr246Met as a bulk-loss comparator, STUB1 knockout as a "
            "null reference, and the unedited parental line as isogenic wild type; plus "
            "an available SCAR16 patient-derived line where genotype permits"
        ),
        patient_stratification=(
            "inter-domain missense alleles (p.Lys145Gln, p.Met211Ile)",
            "U-box missense comparator (p.Thr246Met)",
            "compound heterozygous missense / U-box-truncating configuration",
        ),
        perturbation=(
            "Endogenous-locus allele knock-in rather than overexpression, assayed at 37 C "
            "and after a defined heat-shock and proteasome-stress challenge"
        ),
        comparator="Isogenic unedited wild-type line differentiated in parallel",
        controls=(
            "isogenic unedited parental line",
            "STUB1 knockout line as a loss-of-function reference",
            "p.Thr246Met knock-in as a characterized bulk-ligase-loss comparator",
            "catalytically dead U-box control (e.g. H260Q) for assay direction",
            ("two or more independently derived clones per genotype to control clonal "
            "variation"),
            ("parallel differentiation batches with blinded sample identity for the "
            "proteomics run"),
        ),
        readouts=(
            ("diGly-enriched ubiquitinome quantifying site-level ubiquitination across "
            "CHIP clients"),
            "targeted immunoblot panel of defined CHIP substrates",
            "CHIP steady-state abundance and thermal stability at endogenous dosage",
            ("CHIP-HSP70/HSC70 co-immunoprecipitation to separate co-chaperone from "
            "ligase function"),
            "substrate turnover rate by cycloheximide chase",
        ),
        primary_endpoint=(
            "Difference in site-level ubiquitination of CHIP client proteins between each "
            "knock-in genotype and the isogenic wild type, at 37 C and after stress, with "
            "a pre-registered substrate-subset analysis"
        ),
        secondary_endpoints=(
            "CHIP abundance and thermal stability per genotype",
            "chaperone co-immunoprecipitation efficiency per genotype",
            "substrate half-life per genotype",
        ),
        expected_result_if_supported=(
            "p.Lys145Gln and p.Met211Ile neurons show reduced ubiquitination of a "
            "defined client subset relative to isogenic wild type, or lose "
            "ubiquitination capacity under stress while matching wild type at 37 C, with "
            "a narrower affected-substrate profile than p.Thr246Met."
        ),
        expected_result_if_refuted=(
            "p.Lys145Gln and p.Met211Ile neurons are indistinguishable from isogenic "
            "wild type in site-level client ubiquitination, substrate turnover and "
            "stress response, while p.Thr246Met shows the expected deficit. That outcome "
            "refutes the substrate-selective ligase hypothesis and redirects the "
            "mechanism to non-ligase CHIP function or to allele-specific protein "
            "instability, and the upstream edge wording would need revision rather than "
            "narrowing."
        ),
        confounders=(
            "clonal variation between iPSC lines independent of genotype",
            ("differentiation efficiency and cell-type composition differences between "
            "batches"),
            "off-target CRISPR edits",
            "nonsense-mediated decay differences in the compound-heterozygous lines",
            ("ubiquitinome coverage bias: unchanged sites may be unmeasured rather than "
            "unaffected"),
            ("assay temperature and handling time, given reported temperature-dependent "
            "recovery of mutant activity"),
            ("CHIP self-ubiquitination altering its own abundance and confounding "
            "per-cell activity normalization"),
        ),
        known_limitations=(
            ("iPSC-derived neurons are immature and may not reproduce adult Purkinje-cell "
            "biology; reported SCAR16 fibroblast-versus-neuron discordance in the heat "
            "shock response (PMID:33097556) is a direct precedent for cell-type-dependent "
            "results."),
            ("A negative ubiquitinome result cannot exclude a defect in an unmeasured "
            "substrate or compartment."),
            ("The design tests a molecular mechanism, not neurodegeneration, and cannot "
            "establish that any measured difference causes Purkinje-cell loss."),
            ("Allele coverage is limited to the two alleles in scope and does not "
            "generalize to untested SCAR16 variants."),
        ),
        required_assets=(
            ("iPSC line with a well-characterized parental background permitting "
            "isogenic editing"),
            ("SCAR16 patient-derived iPSC line (a STUB1/CHIP mutant line from a Gordon "
            "Holmes/SCAR16 patient is reported in PMID:29679845)"),
            "validated CHIP and ubiquitin antibodies for the targeted panel",
            "mass spectrometry access with diGly enrichment capability",
        ),
        required_capabilities=(
            "iPSC maintenance and CRISPR knock-in at the STUB1 locus",
            "directed differentiation to cerebellar and cortical neuronal fates",
            "quantitative ubiquitinome proteomics with diGly enrichment",
            "protein thermal stability and co-immunoprecipitation assays",
            "pre-registered statistical analysis with clone-level random effects",
        ),
        safety_or_ethics_flags=(
            ("Human iPSC work requires consent provenance review and institutional "
            "approval for the patient-derived line."),
        ),
        unjustified_interpretations=(
            ("that a measured ubiquitination difference demonstrates the cause of "
            "Purkinje-cell degeneration"),
            "that an unchanged ubiquitinome proves these alleles are benign",
            "that any result supports a therapeutic strategy or clinical decision",
            "that results generalize to SCAR16 alleles not tested here",
            "that results transfer to the allelic dominant disorder SCA48",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("refinement", type=Path)
    parser.add_argument("--claim", default=TARGET_CLAIM)
    parser.add_argument("--gap-output", type=Path, required=True)
    parser.add_argument("--experiment-output", type=Path, required=True)
    args = parser.parse_args()

    refinement = EdgeRefinement.model_validate_json(args.refinement.read_text())
    gap = build_gap(refinement, args.claim)
    experiment = build_experiment(gap)
    args.gap_output.write_text(gap.model_dump_json(indent=2), encoding="utf-8")
    args.experiment_output.write_text(experiment.model_dump_json(indent=2), encoding="utf-8")
    print(
        json.dumps(
            {
                "gap_id": gap.gap_id,
                "gap_type": gap.gap_type.value,
                "related_claims": list(gap.related_claims),
                "related_edges": list(gap.related_edges),
                "coverage_sources": len(gap.search_coverage.sources),
                "experiment_id": experiment.experiment_id,
                "controls": len(experiment.controls),
                "readouts": len(experiment.readouts),
                "label": experiment.label,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
