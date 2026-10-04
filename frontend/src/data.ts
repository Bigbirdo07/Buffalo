import flagshipJson from "../../data/demo/flagship_story.json";
import goalsJson from "../../data/demo/goals_summary.json";
import parentJson from "../../data/demo/parent_story.json";
import {
  FlagshipStorySchema,
  GoalsSummarySchema,
  ParentStorySchema,
  type FlagshipStory,
  type GoalsSummary,
  type ParentStory,
} from "./contract";

type ContractResult =
  | { ok: true; story: FlagshipStory; goals: GoalsSummary; parent: ParentStory }
  | { ok: false; errors: string[] };

export function loadContracts(): ContractResult {
  const story = FlagshipStorySchema.safeParse(flagshipJson);
  const goals = GoalsSummarySchema.safeParse(goalsJson);
  const parent = ParentStorySchema.safeParse(parentJson);
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
  if (!parent.success) {
    errors.push(
      ...parent.error.issues.map(
        (issue) => `parent_story.json: ${issue.path.join(".")} — ${issue.message}`,
      ),
    );
  }
  if (!story.success || !goals.success || !parent.success) return { ok: false, errors };

  if (story.data.software_commit !== goals.data.software_commit) {
    return {
      ok: false,
      errors: ["Demo contracts were generated from different software commits."],
    };
  }
  if (goals.data.ui_contract !== "data/demo/flagship_story.json") {
    return { ok: false, errors: ["Goal summary points to an unexpected UI contract."] };
  }

  return { ok: true, story: story.data, goals: goals.data, parent: parent.data };
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

// --- Browse index --------------------------------------------------------

import { BrowseIndexSchema, type BrowseDisease, type BrowseIndex } from "./contract";

type BrowseResult = { ok: true; index: BrowseIndex } | { ok: false; errors: string[] };

let browseCache: BrowseResult | null = null;

/**
 * Load and validate the corpus-wide index.
 *
 * Dynamically imported so its few megabytes stay out of the initial bundle:
 * the landing screen must paint before this resolves. Cached after the first
 * call because the index never changes within a session.
 */
export async function loadBrowseIndex(): Promise<BrowseResult> {
  if (browseCache) return browseCache;
  try {
    const module = await import("../../data/demo/browse_index.json");
    const parsed = BrowseIndexSchema.safeParse(module.default);
    browseCache = parsed.success
      ? { ok: true, index: parsed.data }
      : {
          ok: false,
          errors: parsed.error.issues.map(
            (issue) => `browse_index.json: ${issue.path.join(".")} — ${issue.message}`,
          ),
        };
  } catch (error) {
    browseCache = {
      ok: false,
      errors: [`browse_index.json could not be loaded: ${String(error)}`],
    };
  }
  return browseCache;
}

/**
 * Rank diseases against a query.
 *
 * Matches the disease name and its causal gene symbols, because a visitor is as
 * likely to know the gene as the disease label. Ordering puts exact and prefix
 * matches first so typing a full name does not bury it under longer names that
 * happen to contain it.
 */
export function searchDiseases(
  index: BrowseIndex,
  query: string,
  limit = 12,
): BrowseDisease[] {
  const needle = query.trim().toLowerCase();
  if (needle.length < 2) return [];
  const scored: Array<{ disease: BrowseDisease; score: number }> = [];
  for (const disease of index.diseases) {
    const name = disease.name.toLowerCase();
    let score = -1;
    if (name === needle) score = 0;
    else if (name.startsWith(needle)) score = 1;
    else if (name.includes(needle)) score = 2;
    else if (disease.genes.some((gene) => gene.toLowerCase() === needle)) score = 3;
    else if (disease.genes.some((gene) => gene.toLowerCase().startsWith(needle))) score = 4;
    if (score >= 0) {
      // Analysed diseases sort ahead of equally good matches: they are the ones
      // that can answer the whole question.
      scored.push({ disease, score: score * 2 + (disease.case_id ? 0 : 1) });
    }
  }
  scored.sort(
    (a, b) => a.score - b.score || a.disease.name.localeCompare(b.disease.name),
  );
  return scored.slice(0, limit).map((item) => item.disease);
}
