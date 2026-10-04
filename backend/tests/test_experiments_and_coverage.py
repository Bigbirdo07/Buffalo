from __future__ import annotations

import unittest

from pydantic import ValidationError

from atlas.domain.experiments import ExperimentProposal
from atlas.domain.gaps import CoverageStatus, SearchSourceCoverage


class ExperimentAndCoverageTests(unittest.TestCase):
    def test_experiment_requires_refutation_condition(self) -> None:
        with self.assertRaises(ValidationError):
            ExperimentProposal(
                experiment_id="x1",
                knowledge_gap_id="g1",
                scientific_question="Does X alter Y?",
                hypothesis="X reduces Y.",
                competing_hypothesis="X does not alter Y.",
                model_system="patient-derived neurons",
                sample_type="iPSC neurons",
                perturbation="isogenic correction",
                comparator="uncorrected cells",
                controls=("healthy control",),
                readouts=("Y activity",),
                primary_endpoint="Y activity difference",
                expected_result_if_supported="Correction restores Y activity.",
                expected_result_if_refuted="",
                confounders=("clonal variation",),
                known_limitations=("in vitro model",),
                required_assets=("patient iPSC",),
                required_capabilities=("iPSC differentiation",),
                unjustified_interpretations=("therapeutic efficacy in patients",),
            )

    def test_failed_search_requires_error(self) -> None:
        with self.assertRaises(ValidationError):
            SearchSourceCoverage(source="PubMed", status=CoverageStatus.FAILED)


if __name__ == "__main__":
    unittest.main()

