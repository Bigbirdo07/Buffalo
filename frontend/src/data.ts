import flagshipJson from "../../data/demo/flagship_story.json";
import goalsJson from "../../data/demo/goals_summary.json";
import {
  FlagshipStorySchema,
  GoalsSummarySchema,
  type FlagshipStory,
  type GoalsSummary,
} from "./contract";

type ContractResult =
  | { ok: true; story: FlagshipStory; goals: GoalsSummary }
  | { ok: false; errors: string[] };

export function loadContracts(): ContractResult {
  const story = FlagshipStorySchema.safeParse(flagshipJson);
  const goals = GoalsSummarySchema.safeParse(goalsJson);
  const errors: string[] = [];

  if (!story.success) {
    errors.push(
      ...story.error.issues.map(
        (issue) => `flagship_story.json: ${issue.path.join(".")} — ${issue.message}`,
      ),
    );
  }
  if (!goals.success) {
    errors.push(
      ...goals.error.issues.map(
        (issue) => `goals_summary.json: ${issue.path.join(".")} — ${issue.message}`,
      ),
    );
  }
  if (!story.success || !goals.success) return { ok: false, errors };

  if (story.data.software_commit !== goals.data.software_commit) {
    return {
      ok: false,
      errors: ["Demo contracts were generated from different software commits."],
    };
  }
  if (goals.data.ui_contract !== "data/demo/flagship_story.json") {
    return { ok: false, errors: ["Goal summary points to an unexpected UI contract."] };
  }

  return { ok: true, story: story.data, goals: goals.data };
}

// --- Multi-case loading --------------------------------------------------

import casesJson from "../../data/demo/cases.json";
import { DemoCasesSchema, type DemoCase, type DemoCases } from "./contract";

type CasesResult =
  | { ok: true; cases: DemoCases }
  | { ok: false; errors: string[] };

/**
 * Validate the three-case contract.
 *
 * Validated rather than cast, like the single-case contract: a shape mismatch
 * should surface as a named error at load, not as undefined halfway down a
 * screen during a presentation.
 */
export function loadCases(): CasesResult {
  const parsed = DemoCasesSchema.safeParse(casesJson);
  if (!parsed.success) {
    return {
      ok: false,
      errors: parsed.error.issues.map(
        (issue) => `cases.json: ${issue.path.join(".")} — ${issue.message}`,
      ),
    };
  }
  return { ok: true, cases: parsed.data };
}

/** The case a given id names, falling back to the declared default. */
export function selectCase(cases: DemoCases, caseId: string | null): DemoCase {
  return (
    cases.cases.find((item) => item.case_id === caseId) ??
    cases.cases.find((item) => item.case_id === cases.default_case) ??
    cases.cases[0]
  );
}
