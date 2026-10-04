import { useMemo, useState } from "react";
import type { Candidate, DemoCase, FlagshipStory, GoalsSummary, ParentStory, PresentationMode } from "./contract";
import { loadCases } from "./data";
import { EntityLegend, EntityNode, EvidenceDrawer, EvidenceLineage, GuidePanel, Icon, NextButton, ReviewStatus, StatusPill, humanize, navigate } from "./components";

type ScreenProps = {
  story: FlagshipStory;
  goals: GoalsSummary;
  parent: ParentStory;
  mode: PresentationMode;
  /** The disease the visitor selected. Null only if the case contract failed. */
  activeCase: DemoCase | null;
};

function PageIntro({ step, title, description }: { step: string; title: string; description: string }) {
  return <header className="parent-page-intro"><span>{step}</span><h1>{title}</h1><p>{description}</p></header>;
}

function caseSummary(activeCase: DemoCase | null, parent: ParentStory) {
  const isNarrated = !activeCase || activeCase.case_id === "scar16";
  if (isNarrated) {
    return {
      narrated: true,
      shortName: parent.case.short_name,
      fullName: parent.case.full_name,
      cause: parent.case.cause_summary,
      goal: parent.case.research_goal,
      groups: parent.case.phenotype_groups,
      variation: parent.case.variation_note,
    };
  }
  if (activeCase.case_id === "lafora") {
    return {
      narrated: false,
      shortName: "Lafora Disease",
      fullName: "Progressive Myoclonus Epilepsy",
      cause: "Biallelic variants in EPM2A (laforin) or NHLRC1 (malin) resulting in polyglucosan accumulation and proteostasis failure.",
      goal: "Determine if Lafora Disease shares a downstream co-chaperone and stress response defect with STUB1/SCAR16.",
      groups: [
        { label: "Movement and balance", detail: "Severe progressive myoclonus, ataxia, and muscle spasms." },
        { label: "Cognition and mood", detail: "Rapid cognitive decline, dementia, and visual hallucinations." },
      ],
      variation: "Symptoms typically manifest in adolescence.",
    };
  }
  if (activeCase.case_id === "ankylosing") {
    return {
      narrated: false,
      shortName: "Ankylosing Spondylitis",
      fullName: "Inflammatory Spondylarthropathy",
      cause: "HLA-B27 and ERAP1 variants altering antigen presentation and IL-23/IL-17 immune signaling.",
      goal: "Identify whether Ankylosing Spondylitis shares specific immune peptide-processing targets with related inflammatory conditions.",
      groups: [
        { label: "Spine & Joint System", detail: "Chronic inflammation of sacroiliac joints and spinal vertebrae." },
        { label: "Immune & Ocular System", detail: "Systemic inflammation and acute anterior uveitis (eye inflammation)." },
      ],
      variation: "Onset typically occurs in early adulthood.",
    };
  }
  const name = activeCase.starting_disease.name;
  const found = activeCase.goal1.candidates_evaluated;
  const independent = activeCase.goal1.candidate_neighbors.filter((c) => c.independent).length;
  return {
    narrated: false,
    shortName: name,
    fullName: activeCase.label,
    cause: activeCase.why_included,
    goal:
      activeCase.outcome === "FULL_CHAIN"
        ? `Of ${found} candidate diseases examined, ${independent} survived evidence refinement as independent connections.`
        : activeCase.no_connection_statement ??
          "No candidate connection survived evidence refinement for this disease.",
    groups: [],
    variation: "",
  };
}

export function DiseaseScreen({ story, parent, mode, activeCase }: ScreenProps) {
  const casesResult = loadCases();
  const allCases = casesResult.ok ? casesResult.cases.cases : [];
  // Focus on the 3 primary worked cases
  const cases = allCases.filter((c) => ["scar16", "lafora", "ankylosing"].includes(c.case_id));
  const displayCases = cases.length > 0 ? cases : allCases;
  const summary = caseSummary(activeCase, parent);

  return <main className="screen parent-screen">
    <section className="case-start">
      <div>
        <span className="eyebrow">Rare Disease Atlas · research navigation</span>
        <h1>Help me understand my child’s disease—and what researchers could ask next.</h1>
        <p>The Atlas checks related research, keeps uncertainty visible, and turns an unanswered biological question into a testable research path.</p>
      </div>
      <GuidePanel question="What am I looking at?">
        <p>A guided research summary for one disease. It is not a diagnosis or treatment recommendation.</p>
      </GuidePanel>
    </section>

    {/* The 3 worked cases picker */}
    <section className="case-picker" aria-label="Worked cases">
      {displayCases.map((choice) => {
        const active = choice.case_id === (activeCase?.case_id ?? "scar16");
        return <button
          key={choice.case_id}
          className={`case-choice disease ${active ? "active" : ""}`}
          aria-pressed={active}
          onClick={() => navigate(`/disease?case=${choice.case_id}`)}
        >
          <i className="entity-shape disease" />
          <span>
            <small>{choice.outcome === "FULL_CHAIN" ? "Full analysis" : "No connection found"}</small>
            <b>{choice.starting_disease.name}</b>
            <em>{choice.label}</em>
          </span>
          {active && <strong>Selected</strong>}
        </button>;
      })}
    </section>

    <p className="case-notice" role="status">
      Five diseases have been through full evidence refinement.{" "}
      <button type="button" className="text-button" onClick={() => navigate("/search")}>
        Search all 3,289 diseases
      </button>
    </p>

    <section className="disease-summary">
      <div className="disease-title">
        <span className="entity-shape disease" />
        <div>
          <small>Your selected disease</small>
          <h2>{summary.shortName}</h2>
          <p>{summary.fullName}</p>
        </div>
      </div>

      <article className="cause-card">
        <span>{summary.narrated ? "What causes it?" : "Why this case is here"}</span>
        <p>{summary.cause}</p>
        {mode === "scientist" && <code>disease_id: {(activeCase ?? { starting_disease: story.starting_disease }).starting_disease.id}</code>}
      </article>

      {summary.groups.length > 0 && (
        <article className="systems-card">
          <span>What body systems are commonly affected?</span>
          <div className="systems-grid">
            {summary.groups.map((group) => (
              <section key={group.label} className="system-card-item">
                <div className="system-icon-badge">★</div>
                <h3>{group.label}</h3>
                <p>{group.detail}</p>
              </section>
            ))}
          </div>
          {summary.variation && <small className="systems-variation-note">{summary.variation}</small>}
        </article>
      )}

      <article className="research-doorway">
        <span>What are we trying to understand?</span>
        <p>{summary.goal}</p>
      </article>

      {!summary.narrated && (
        <p className="case-notice">
          The plain-language walkthrough was written for {parent.case.short_name}. This
          case shows the same pipeline output without that narration — switch to
          scientist mode for its full detail.
        </p>
      )}
    </section>

    {mode === "scientist" && (
      <details className="source-note">
        <summary>Presentation-source provenance</summary>
        <ul>
          {parent.sources.map((source) => (
            <li key={source.field}>
              <b>{source.field}:</b> <code>{source.reference}</code> at <code>{source.upstream_commit}</code>
            </li>
          ))}
        </ul>
      </details>
    )}

    <div className="page-action">
      <NextButton to="/connections">See what other diseases may teach us</NextButton>
    </div>
  </main>;
}

function relationshipMeaning(candidate: Candidate) {
  if (candidate.identity !== "DISTINCT_DISEASE") return { evidence: "These labels overlap with the same STUB1-related disease spectrum.", matters: "This helps explain the range of the disease, but it is not a new independent research connection." };
  if (candidate.relationship === "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT") return { evidence: "The diseases affect some of the same cellular machinery, but probably in different ways.", matters: "Research tools may still be informative, but researchers should not assume the diseases work the same way." };
  if (candidate.relationship === "SHARED_DOWNSTREAM_MECHANISM") return { evidence: "Evidence suggests the diseases may reach a related downstream cellular problem through different starting points.", matters: "A matched experiment could test whether tools or assays from one disease can help study the other." };
  if (candidate.relationship === "SHARED_TISSUE_CONTEXT") return { evidence: "The diseases affect similar tissue, but a shared molecular mechanism was not demonstrated.", matters: "Similar symptoms or affected tissue alone are not enough to transfer a research approach." };
  return { evidence: "The available evidence did not support a specific biological connection strongly enough.", matters: "Rejecting a weak lead helps avoid spending time on a relationship the evidence does not justify." };
}

function journeyFor(story: FlagshipStory, activeCase: DemoCase | null) {
  if (!activeCase || activeCase.case_id === "scar16") {
    return {
      diseaseName: story.starting_disease.name,
      neighbourName: story.goal1.selected_neighbor.name,
      goal1: story.goal1,
      goal2: story.goal2,
      goal3: story.goal3,
      narrated: true,
    };
  }
  if (!activeCase.goal3 || !activeCase.goal2) return null;
  const g1 = activeCase.goal1;
  return {
    diseaseName: activeCase.starting_disease.name,
    neighbourName: g1.selected_neighbor?.name ?? "",
    goal1: {
      ...g1,
      selected_neighbor: g1.selected_neighbor ?? { id: "", name: "" },
      retrieval_reason: g1.retrieval_reason ?? { types: [], feature: null },
      validated_relationship: g1.validated_relationship ?? {
        class: "UNKNOWN", retrieval_validity: "UNRESOLVED",
        rationale: "", evidence_ids: [],
      },
      why_this_matters: g1.why_this_matters ?? "",
    },
    goal2: activeCase.goal2,
    goal3: activeCase.goal3,
    narrated: false,
  };
}

function NoConnection({ activeCase }: { activeCase: DemoCase | null }) {
  return <main className="screen parent-screen">
    <PageIntro
      step="No connection found"
      title={`No research connection survived review for ${activeCase?.starting_disease.name ?? "this disease"}.`}
      description="This part of the journey only exists when a connection holds up. It did not here, and the Atlas reports that rather than showing the next screen anyway."
    />
    <section className="landscape-notes">
      <article>
        <span>What happened</span>
        <h2>{activeCase?.label ?? "No defensible connection"}</h2>
        <p>{activeCase?.no_connection_statement ?? ""}</p>
      </article>
    </section>
    <div className="page-action"><NextButton to="/disease">Choose another disease</NextButton></div>
  </main>;
}

export function ConnectionsScreen({ story, parent, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  const [showPath, setShowPath] = useState(false);
  const visible = useMemo(() => {
    if (!journey) return [];
    const flagship = journey.goal1.selected_neighbor?.name;
    return [...journey.goal1.candidate_neighbors].sort((a, b) => {
      if (a.name === flagship) return -1;
      if (b.name === flagship) return 1;
      return a.rank - b.rank;
    });
  }, [journey]);

  if (!journey) return <NoConnection activeCase={activeCase} />;

  return <main className="screen parent-screen">
    <PageIntro step="Research connections" title="What other diseases may help us understand this one?" description="The Atlas found several research connections, then checked whether each one meant what the original search suggested." />
    <ReviewStatus story={story} />
    <div className="content-with-guide">
      <section>
        <h2>We found a few research connections worth checking</h2>
        <p className="lede">These are not treatment matches. They are possible research comparisons—and some did not survive closer review.</p>
      </section>
      <GuidePanel question="Why is another disease here?">
        <p>Because it shared a biological annotation, affected tissue, or downstream process with SCAR16. That is only a reason to investigate, not proof of a meaningful connection.</p>
      </GuidePanel>
    </div>

    <section className="connection-cards">
      {visible.map((candidate) => {
        const copy = relationshipMeaning(candidate);
        const flagship = candidate.name === journey.goal1.selected_neighbor.name;
        return <article key={candidate.name} className={`connection-card ${flagship ? "flagship" : ""}`}>
          <header>
            <span className="entity-shape disease" />
            <small>Rare disease</small>
            {flagship && <b>Worked demonstration case</b>}
          </header>
          <h2>{candidate.name}</h2>
          <dl>
            <div>
              <dt>Why it caught our attention</dt>
              <dd>Both disease records mention <strong>{candidate.retrieval_reason}</strong>.</dd>
            </div>
            <div>
              <dt>What the evidence says</dt>
              <dd>{copy.evidence}</dd>
            </div>
            <div>
              <dt>Why it may matter</dt>
              <dd>{copy.matters}</dd>
            </div>
          </dl>
          <StatusPill value={candidate.identity !== "DISTINCT_DISEASE" ? "SAME_ALLELIC_SPECTRUM" : candidate.relationship} />
          {mode === "scientist" && <code>rank {candidate.rank} · {candidate.identity} · {candidate.relationship} · {candidate.retrieval_validity}</code>}
          {flagship && <button className="text-button" onClick={() => navigate("/evidence")}>Follow this worked example <Icon name="arrow" /></button>}
        </article>;
      })}
    </section>

    <section className="negative-case">
      <Icon name="check" />
      <div>
        <h2>A negative result is useful</h2>
        <p>The separate SCAR20 case found similarities, but none were strong enough to support a shared molecular mechanism. The Atlas reports that rather than promoting the least-weak lead.</p>
      </div>
    </section>

    <section className="guided-biology">
      <header>
        <div>
          <span className="eyebrow">Optional biology view</span>
          <h2>How might SCAR16 and Lafora Disease be connected?</h2>
        </div>
        <button onClick={() => setShowPath(!showPath)}>{showPath ? "Hide the biology" : "See the biology"}</button>
      </header>
      {showPath && (
        <>
          <EntityLegend />
          <div className="guided-path">
            {parent.guided_path.map((node, index) => (
              <div key={node.id} className="path-step">
                <EntityNode node={node} active={index === 2 || index === 3} />
                {index < parent.guided_path.length - 1 && <span className="path-arrow">↓</span>}
              </div>
            ))}
          </div>
          <p className="path-caption">This highlights one evidence-supported route. It does not mean the two diseases are the same.</p>
        </>
      )}
    </section>

    <div className="page-action">
      <NextButton to="/evidence">See what changed after evidence review</NextButton>
    </div>
  </main>;
}

export function EvidenceScreen({ story, parent, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  if (!journey) return <NoConnection activeCase={activeCase} />;
  return <main className="screen parent-screen">
    <PageIntro step="Evidence review" title="The first connection was not the whole story" description="The search found a useful relationship, but closer review changed the explanation for why it may matter." />
    <ReviewStatus story={story} />
    <div className="content-with-guide">
      <section className="three-step-evidence">
        <article>
          <b>1</b>
          <span>What first connected them</span>
          <p>Both diseases were tagged with the broad process <strong>{journey.goal1.retrieval_reason.feature}</strong>.</p>
        </article>
        <article>
          <b>2</b>
          <span>What we checked</span>
          <p>We reviewed whether that broad tag was actually the biological reason the diseases should be compared.</p>
        </article>
        <article>
          <b>3</b>
          <span>What appears more important</span>
          <p>The evidence points to a more specific link involving CHIP-associated chaperone and stress-response biology.</p>
        </article>
      </section>
      <GuidePanel question="How do we know this?">
        <p>Two independent primary findings support the refined relationship. The frozen demo has abstract-level evidence and has not completed full-text review.</p>
      </GuidePanel>
    </div>

    <section className="changed-conclusion">
      <span>Why this matters</span>
      <h2>The Atlas found a real connection, but not for the reason the original search suggested.</h2>
      <p>The search was useful for finding the pair. Evidence review made the proposed biological explanation more specific—and kept the original explanation from being overstated.</p>
    </section>

    <section className="certainty-card">
      <div>
        <span>How sure are we?</span>
        <h2>{parent.parent_certainty.label}</h2>
        <p>{parent.parent_certainty.explanation}</p>
      </div>
      <aside>
        <b>Expert review status</b>
        <p>{parent.parent_certainty.expert_review}</p>
      </aside>
    </section>

    <EvidenceDrawer story={story} mode={mode} />

    {mode === "scientist" && (
      <section className="scientist-details">
        <h2>Scientific details</h2>
        <dl>
          <div><dt>RetrievalReason</dt><dd><code>{journey.goal1.retrieval_reason.feature}</code></dd></div>
          <div><dt>RetrievalValidity</dt><dd><code>{journey.goal1.validated_relationship.retrieval_validity}</code></dd></div>
          <div><dt>Relationship class</dt><dd><code>{journey.goal1.validated_relationship.class}</code></dd></div>
          <div><dt>MechanisticBridge</dt><dd>{journey.goal3.mechanistic_bridge.display_label}</dd></div>
        </dl>
        <EvidenceLineage story={story} />
      </section>
    )}

    <div className="page-action">
      <NextButton to="/unknown">See what researchers still need to know</NextButton>
    </div>
  </main>;
}

export function UnknownScreen({ story, parent, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  if (!journey) return <NoConnection activeCase={activeCase} />;
  return <main className="screen parent-screen">
    <PageIntro step="The open question" title="What do researchers still need to know?" description="A promising biological link is useful only if we are clear about what the evidence has not yet shown." />
    <div className="content-with-guide">
      <section className="big-question">
        <span>Critical unanswered question</span>
        <h2>{parent.parent_gap}</h2>
        <h3>Why that question matters</h3>
        <p>{parent.parent_gap_importance}</p>
      </section>
      <GuidePanel question="What is still uncertain?">
        <p>Whether the shared downstream biology produces the same measurable functional failure in both disease models.</p>
      </GuidePanel>
    </div>

    <section className="know-grid">
      <article>
        <span>What we know</span>
        <p>Evidence supports a downstream connection involving CHIP, chaperones and cellular stress response.</p>
      </article>
      <article>
        <span>What we do not know</span>
        <p>The two diseases have not been compared with the same functional readout under matched conditions.</p>
      </article>
      <article>
        <span>What would resolve it</span>
        <p>A direct, side-by-side experiment using both disease models and a shared control.</p>
      </article>
    </section>

    <section className="child-today">
      <Icon name="alert" />
      <div>
        <h2>What does this mean for my child today?</h2>
        <p><strong>This does not identify a treatment or change your child’s medical care today.</strong></p>
        <p>It identifies a research question that may help scientists understand the disease more clearly and potentially reuse work from a related condition.</p>
      </div>
    </section>

    <section className="questions-list">
      <span>Questions you could bring to a care or research team</span>
      <ol>
        {parent.discussion_questions.map((question) => <li key={question}>{question}</li>)}
      </ol>
      <small>These are discussion prompts, not medical recommendations.</small>
    </section>

    {mode === "scientist" && (
      <details className="scientist-details">
        <summary>Canonical KnowledgeGap</summary>
        <p>{journey.goal3.knowledge_gap.question}</p>
        <code>{journey.goal3.knowledge_gap.id}</code>
        <ul>
          {journey.goal3.knowledge_gap.missing_evidence.map((item) => <li key={item}>{item}</li>)}
        </ul>
      </details>
    )}

    <div className="page-action">
      <NextButton to="/experiment">See how researchers could test it</NextButton>
    </div>
  </main>;
}

export function ExperimentScreen({ story, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  if (!journey) return <NoConnection activeCase={activeCase} />;
  const experiment = journey.goal3.experiment;
  return <main className="screen parent-screen">
    <PageIntro step="A falsifiable test" title="How could researchers test this?" description="Use the same stress test and the same primary readout across both disease models and healthy comparison cells." />
    <div className="content-with-guide">
      <section className="simple-experiment">
        <div className="experiment-inputs">
          <article><span className="entity-shape disease" /><b>SCAR16 cells</b></article>
          <article><span className="entity-shape disease" /><b>Lafora cells</b></article>
          <article><i className="control-shape" /><b>Healthy comparison cells</b></article>
        </div>
        <div className="experiment-test">
          <Icon name="flask" />
          <b>Same standardized stress test</b>
        </div>
        <div className="experiment-output">
          <b>Compare the same cellular response</b>
          <small>{experiment.primary_readout}</small>
        </div>
      </section>
      <GuidePanel question="What would this test tell us?">
        <p>Whether the two disease models show the same kind of failure at the proposed stress-response step—or only look related at a broad level.</p>
      </GuidePanel>
    </div>

    <section className="outcome-grid">
      <article className="supports">
        <span>If the responses look similar</span>
        <p>That would strengthen the idea that the diseases share part of the same downstream biology.</p>
        <details><summary>Exact support rule</summary><p>{journey.goal3.supports_if}</p></details>
      </article>
      <article className="refutes">
        <span>If the responses look different</span>
        <p>That would tell researchers the diseases may only look similar at a broad level and should not be treated as functionally equivalent.</p>
        <details><summary>Exact weakening/refutation rule</summary><p>{journey.goal3.refutes_if}</p></details>
      </article>
    </section>

    <section className="falsifiable-note">
      <Icon name="check" />
      <p><strong>This experiment is allowed to fail.</strong> A different response across the models would be useful evidence against the shared-function hypothesis.</p>
    </section>

    {mode === "scientist" && (
      <details className="experiment-details" open>
        <summary>Scientist protocol view</summary>
        <div className="details-grid">
          <article><h3>Hypothesis</h3><p>{experiment.hypothesis}</p></article>
          <article><h3>Competing hypothesis</h3><p>{experiment.competing_hypothesis}</p></article>
          <article><h3>Model system</h3><p>{experiment.model_system}</p></article>
          <article><h3>Comparator</h3><p>{experiment.comparator}</p></article>
          <article><h3>Secondary readouts</h3><ul>{experiment.secondary_readouts.map((item) => <li key={item}>{item}</li>)}</ul></article>
          <article><h3>Limitations</h3><ul>{experiment.limitations.map((item) => <li key={item}>{item}</li>)}</ul></article>
        </div>
        <EvidenceLineage story={story} />
      </details>
    )}

    <div className="page-action">
      <NextButton to="/existing-work">See what work already exists</NextButton>
    </div>
  </main>;
}

type JourneyGoal2 = NonNullable<ReturnType<typeof journeyFor>>["goal2"];
function workForCapability(goal2: JourneyGoal2, capability: string) {
  return goal2.existing_work.find((item) => item.capability === capability);
}

export function ExistingWorkScreen({ story, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  if (!journey) return <NoConnection activeCase={activeCase} />;
  return <main className="screen parent-screen">
    <PageIntro step="Research landscape" title="What work already exists?" description="We looked at what the proposed experiment would require and searched for teams that have already demonstrated parts of those capabilities." />
    <div className="content-with-guide">
      <section>
        <h2>What the experiment needs</h2>
        <p className="lede">This is organized around research capability—not around famous people or a directory of possible collaborators.</p>
      </section>
      <GuidePanel question="What already exists?">
        <p>Published work provides evidence that several parts of the experiment have been done somewhere. Availability and willingness were not verified.</p>
      </GuidePanel>
    </div>

    <section className="parent-capability-board">
      {journey.goal2.required_capabilities.map((capability) => {
        const work = workForCapability(journey.goal2, capability.capability);
        const found = capability.status !== "UNKNOWN";
        return <article key={capability.id} className={found ? "found" : "missing"}>
          <header>
            <span>{found ? "Found in published work" : "Not yet found"}</span>
            <StatusPill value={capability.status} />
          </header>
          <h2>{capability.capability}</h2>
          <p>{capability.why}</p>
          <div>
            <b>What still needs confirmation</b>
            <p>{work?.verification_gap ?? journey.goal2.missing_capabilities.find((item) => item.capability === capability.capability)?.note ?? "Current access and exact experimental fit remain unverified."}</p>
          </div>
          {work && (
            <details>
              <summary>See the research-team evidence</summary>
              <ul>
                {work.candidates.map((candidate) => (
                  <li key={`${candidate.name}-${candidate.source}`}>
                    <b>{candidate.name}</b>
                    <span>{candidate.source} · {candidate.year}</span>
                    <small>Publication-linked evidence; willingness {humanize(candidate.collaboration_willingness)}</small>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {mode === "scientist" && <code>{capability.id} · {capability.status}</code>}
        </article>;
      })}
    </section>

    <section className="landscape-notes">
      <article>
        <span>Existing assets</span>
        <h2>No verified reusable asset identified</h2>
        <p>A model or assay appearing in a paper does not automatically mean it is currently available for reuse.</p>
      </article>
      <article>
        <span>Where has related research been done?</span>
        <h2>No verified geographic map in this contract</h2>
        <p>The frozen data names publication-linked teams but does not provide verified location records. The UI does not place unverified map pins.</p>
      </article>
      <article>
        <span>Research coordination</span>
        <h2>No supported overlap flagged</h2>
        <p>{journey.goal2.coordination_note}</p>
      </article>
    </section>

    <section className="execution-story">
      <div>
        <span>Execution model</span>
        <h2>{humanize(journey.goal2.execution_topology)}</h2>
        <p>The proposed experiment would need several research teams or capability areas to work together. This does not imply anyone has agreed to participate.</p>
      </div>
      <div>
        {journey.goal2.required_capabilities.map((item) => (
          <span key={item.id} className={item.status === "UNKNOWN" ? "missing" : "found"}>
            {item.status === "UNKNOWN" ? "?" : "✓"} {item.capability}
          </span>
        ))}
        <Icon name="arrow" />
        <b>Proposed experiment</b>
      </div>
    </section>

    <div className="page-action">
      <NextButton to="/next-steps">Build a research discussion summary</NextButton>
    </div>
  </main>;
}

export function NextStepsScreen({ story, parent, mode, activeCase }: ScreenProps) {
  const journey = journeyFor(story, activeCase);
  if (!journey) return <NoConnection activeCase={activeCase} />;
  const covered = journey.goal2.required_capabilities.filter((item) => item.status !== "UNKNOWN").length;
  return <main className="screen parent-screen next-steps-screen">
    <PageIntro step="Research discussion" title="What could happen next?" description="A careful next step begins with expert review, tests the unanswered question, and reuses existing work only where the evidence supports it." />
    <section className="three-next-steps">
      <article>
        <b>1</b>
        <h2>Confirm the biology</h2>
        <p>A disease expert should review whether this proposed connection is scientifically reasonable for your child’s condition.</p>
      </article>
      <article>
        <b>2</b>
        <h2>Test the unanswered question</h2>
        <p>Researchers could compare the two disease models using the same functional stress-response assay.</p>
      </article>
      <article>
        <b>3</b>
        <h2>Reuse what already exists</h2>
        <p>If relevant models or assays are available, researchers may be able to build on them instead of starting from zero.</p>
      </article>
    </section>

    <section className="does-not-mean">
      <h2>What this does not mean</h2>
      <ul>
        <li>It does not mean the diseases are the same.</li>
        <li>It does not identify a treatment.</li>
        <li>It does not replace your child’s medical team.</li>
        <li>It does not mean a research team has agreed to participate.</li>
      </ul>
    </section>

    <section className="discussion-summary" id="research-discussion-summary">
      <header>
        <div>
          <span>Research discussion summary</span>
          <h2>SCAR16</h2>
        </div>
        <button type="button" onClick={() => window.print()}>
          <Icon name="print" /> Print / save PDF
        </button>
      </header>
      <dl>
        <div>
          <dt>Research connection worth asking about</dt>
          <dd>Lafora Disease</dd>
        </div>
        <div>
          <dt>Why</dt>
          <dd>Evidence suggests a possible shared downstream stress-response mechanism involving CHIP and chaperone biology.</dd>
        </div>
        <div>
          <dt>Important uncertainty</dt>
          <dd>{parent.parent_gap}</dd>
        </div>
        <div>
          <dt>Research test</dt>
          <dd>Compare both disease models under the same stress conditions using the same primary functional readout and a shared control.</dd>
        </div>
        <div>
          <dt>What already exists</dt>
          <dd>{covered} of {journey.goal2.required_capabilities.length} capability areas have publication-linked evidence.</dd>
        </div>
        <div>
          <dt>What remains uncertain</dt>
          <dd>Expert review, reusable asset availability, research-team willingness, and functional equivalence.</dd>
        </div>
      </dl>
      <h3>Questions to ask</h3>
      <ol>
        {parent.discussion_questions.map((question) => <li key={question}>{question}</li>)}
      </ol>
      <footer>Research-support prototype. This is not a treatment plan or medical recommendation.</footer>
    </section>

    {mode === "scientist" && (
      <section className="scientist-details">
        <h2>Complete machine-readable lineage</h2>
        <EvidenceLineage story={story} />
        <p><code>{story.provenance.pipeline_version}</code> · <code>{story.provenance.software_commit}</code></p>
      </section>
    )}

    <footer className="closing">
      <p>The Atlas does not just find a link. It checks the reason, preserves what remains uncertain, proposes a test that can fail, and shows which research pieces may already exist.</p>
      <button type="button" onClick={() => navigate("/disease")}>Restart the journey</button>
    </footer>
  </main>;
}
