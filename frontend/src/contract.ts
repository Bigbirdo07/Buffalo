import { z } from "zod";

const CandidateSchema = z.object({
  rank: z.number().int().positive(),
  name: z.string().min(1),
  retrieval_reason: z.string().min(1),
  identity: z.string().min(1),
  independent: z.boolean(),
  relationship: z.string().min(1),
  retrieval_validity: z.string().min(1),
  has_bridge: z.boolean(),
});

const RankingDimensionSchema = z.object({
  name: z.string(),
  value: z.number(),
  weight: z.number(),
  contribution: z.number(),
  rationale: z.string(),
});

const RankingCandidateSchema = z.object({
  disease: z.string(),
  relationship_class: z.string(),
  total: z.number(),
  components: z.array(RankingDimensionSchema),
  penalties: z.array(RankingDimensionSchema),
});

const CapabilityCandidateSchema = z.object({
  name: z.string(),
  source: z.string(),
  year: z.number().int(),
  recency: z.string(),
  evidence_scope: z.string(),
  capability_verified: z.boolean(),
  collaboration_willingness: z.string(),
});

const RequiredCapabilitySchema = z.object({
  id: z.string(),
  capability: z.string(),
  why: z.string(),
  status: z.string(),
});

export const FlagshipStorySchema = z.object({
  schema_version: z.literal("flagship-story-v1"),
  software_commit: z.string(),
  starting_disease: z.object({ id: z.string(), name: z.string() }),
  goal1: z.object({
    candidates_retrieved: z.number().int().nonnegative(),
    candidates_evaluated: z.number().int().nonnegative(),
    candidate_neighbors: z.array(CandidateSchema),
    excluded_as_same_entity: z.array(z.string()),
    rejected_examples: z.array(
      z.object({ name: z.string(), outcome: z.string(), why: z.string() }),
    ),
    selected_neighbor: z.object({ id: z.string(), name: z.string() }),
    selection: z.object({
      automated_choice: z.string(),
      selected: z.string(),
      operator_override: z.boolean(),
      override_reason: z.string(),
      ranking_basis: z.string(),
      components: z.array(RankingCandidateSchema),
    }),
    identity_result: z.object({ relation: z.string(), scoped: z.array(z.unknown()) }),
    retrieval_reason: z.object({ types: z.array(z.string()), feature: z.string() }),
    validated_relationship: z.object({
      class: z.string(),
      retrieval_validity: z.string(),
      rationale: z.string(),
      evidence_ids: z.array(z.string()),
    }),
    why_this_matters: z.string(),
  }),
  goal3: z.object({
    mechanistic_bridge: z.object({
      id: z.string(),
      version: z.number().int(),
      supersedes: z.string().nullable(),
      terms: z.array(z.string()),
      display_label: z.string(),
      derived_from: z.array(z.string()),
      derivation_method: z.string(),
      evidence_depth: z.string(),
      full_text_review_completed: z.boolean(),
      refinement_reason: z.string().nullable(),
    }),
    knowledge_gap: z.object({
      id: z.string(),
      question: z.string(),
      why_it_matters: z.string(),
      missing_evidence: z.array(z.string()),
    }),
    experiment: z.object({
      id: z.string(),
      hypothesis: z.string(),
      competing_hypothesis: z.string(),
      model_system: z.string(),
      comparator: z.string(),
      primary_readout: z.string(),
      secondary_readouts: z.array(z.string()),
      limitations: z.array(z.string()),
    }),
    supports_if: z.string(),
    refutes_if: z.string(),
    evidence_limitations: z.array(z.string()),
    review_status: z.string(),
    evidence_status: z.string(),
  }),
  goal2: z.object({
    required_capabilities: z.array(RequiredCapabilitySchema),
    existing_work: z.array(
      z.object({
        capability: z.string(),
        status: z.string(),
        candidates: z.array(CapabilityCandidateSchema),
        verification_gap: z.string(),
      }),
    ),
    assets: z.array(z.unknown()),
    asset_status: z.string(),
    missing_capabilities: z.array(
      z.object({ capability: z.string(), status: z.string(), note: z.string() }),
    ),
    coordination_opportunities: z.array(z.unknown()),
    coordination_note: z.string(),
    execution_topology: z.string(),
    execution_readiness: z.string(),
    collaborator_status: z.string(),
    first_contact: z.object({
      target: z.string(),
      basis: z.string(),
      question: z.string(),
      caveat: z.string(),
    }),
  }),
  provenance: z.object({
    dismech_commit: z.string(),
    hpo_release: z.string(),
    pipeline_version: z.string(),
    selection_version: z.string(),
    software_commit: z.string(),
    generated_from: z.array(z.string()),
  }),
  disclaimer: z.object({
    headline: z.string(),
    not_a_medical_recommendation: z.boolean(),
    not_an_established_mechanism: z.boolean(),
    review_state: z.string(),
    expert_signoff: z.string(),
  }),
});

const GoalStatusSchema = z.object({
  question: z.string(),
  technical_status: z.string(),
  evidence: z.string(),
});

export const GoalsSummarySchema = z.object({
  schema_version: z.literal("goals-summary-v1"),
  software_commit: z.string(),
  goal1: GoalStatusSchema,
  goal3: GoalStatusSchema.extend({
    scientific_review: z.string(),
    evidence_status: z.string(),
  }),
  goal2: GoalStatusSchema.extend({
    execution_readiness: z.string(),
  }),
  ready_for_ui: z.boolean(),
  ready_for_ui_basis: z.string(),
  ui_contract: z.string(),
});

export type FlagshipStory = z.infer<typeof FlagshipStorySchema>;
export type GoalsSummary = z.infer<typeof GoalsSummarySchema>;
export type Candidate = z.infer<typeof CandidateSchema>;
export type RequiredCapability = z.infer<typeof RequiredCapabilitySchema>;
export type PresentationMode = "family" | "scientist";

// --- Multi-case demo contract -------------------------------------------
//
// Three worked cases with deliberately different outcomes. goal3 and goal2 are
// nullable because one case has no defensible connection at all: that is the
// honest result for most disease pairs, and a schema that could not express it
// would quietly force every case to look like a success.

const CaseGoal1Schema = z.object({
  candidates_retrieved: z.number().int().nonnegative(),
  candidates_evaluated: z.number().int().nonnegative(),
  candidate_neighbors: z.array(CandidateSchema),
  excluded_as_same_entity: z.array(z.string()),
  rejected_examples: z.array(
    z.object({ name: z.string(), outcome: z.string(), why: z.string() }),
  ),
  selected_neighbor: z.object({ id: z.string(), name: z.string() }).nullable(),
  selection: z.unknown().optional(),
  identity_result: z
    .object({ relation: z.string().nullable(), scoped: z.array(z.unknown()) })
    .optional(),
  retrieval_reason: z
    .object({ types: z.array(z.string()), feature: z.string().nullable() })
    .optional(),
  validated_relationship: z
    .object({
      class: z.string(),
      retrieval_validity: z.string(),
      rationale: z.string(),
      evidence_ids: z.array(z.string()),
    })
    .optional(),
});

const CaseGoal3Schema = z.object({
  mechanistic_bridge: z.object({
    id: z.string(),
    version: z.number().int().nullable(),
    supersedes: z.string().nullable(),
    terms: z.array(z.string()),
    display_label: z.string().nullable(),
    derived_from: z.array(z.string()),
    evidence_depth: z.string().nullable(),
    full_text_review_completed: z.boolean().nullable(),
  }),
  knowledge_gap: z.object({
    id: z.string(),
    question: z.string(),
    why_it_matters: z.string(),
  }),
  experiment: z.object({
    id: z.string(),
    hypothesis: z.string(),
    competing_hypothesis: z.string(),
    primary_readout: z.string(),
    secondary_readouts: z.array(z.string()),
    limitations: z.array(z.string()),
  }),
  supports_if: z.string(),
  refutes_if: z.string(),
  evidence_limitations: z.array(z.string()),
  review_status: z.string(),
  evidence_status: z.string(),
});

const CaseGoal2Schema = z.object({
  required_capabilities: z.array(
    z.object({
      id: z.string(),
      capability: z.string(),
      why: z.string(),
      status: z.string(),
    }),
  ),
  existing_work: z.array(
    z.object({
      capability: z.string(),
      status: z.string(),
      candidates: z.array(CapabilityCandidateSchema),
      verification_gap: z.string(),
    }),
  ),
  assets: z.array(z.unknown()),
  asset_status: z.string(),
  missing_capabilities: z.array(
    z.object({ capability: z.string(), status: z.string(), note: z.string() }),
  ),
  coordination_opportunities: z.array(z.unknown()),
  execution_topology: z.string(),
  collaborator_status: z.string(),
  first_contact: z.unknown(),
});

export const DemoCaseSchema = z.object({
  case_id: z.string(),
  label: z.string(),
  why_included: z.string(),
  outcome: z.enum(["FULL_CHAIN", "NO_DEFENSIBLE_CONNECTION"]),
  starting_disease: z.object({ id: z.string(), name: z.string() }),
  goal1: CaseGoal1Schema,
  goal3: CaseGoal3Schema.nullable(),
  goal2: CaseGoal2Schema.nullable(),
  no_connection_statement: z.string().optional(),
  provenance: z.object({
    software_commit: z.string(),
    candidates_from: z.string(),
  }),
  disclaimer: z.object({
    headline: z.string(),
    not_a_medical_recommendation: z.literal(true),
    not_an_established_mechanism: z.literal(true),
    review_state: z.string(),
    expert_signoff: z.string(),
  }),
});

export const DemoCasesSchema = z.object({
  schema_version: z.literal("demo-cases-v1"),
  software_commit: z.string(),
  case_count: z.number().int().positive(),
  default_case: z.string(),
  cases: z.array(DemoCaseSchema).min(1),
});

export type DemoCase = z.infer<typeof DemoCaseSchema>;
export type DemoCases = z.infer<typeof DemoCasesSchema>;
