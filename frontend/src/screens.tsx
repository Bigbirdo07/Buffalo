import { useMemo, useState } from "react";
import type { Candidate, FlagshipStory, GoalsSummary, PresentationMode } from "./contract";
import {
  EvidenceDrawer,
  EvidenceLineage,
  Icon,
  NextButton,
  ScientificReviewStatus,
  SectionHeading,
  StatusPill,
  humanize,
  navigate,
  relationshipCopy,
} from "./components";

type ScreenProps = { story: FlagshipStory; goals: GoalsSummary; mode: PresentationMode };

export function SearchScreen({ story, goals }: ScreenProps) {
  const [query, setQuery] = useState("SCAR16");
  const [message, setMessage] = useState("");
  function submit(event: React.FormEvent) {
    event.preventDefault();
    const normalized = query.trim().toLowerCase();
    if (["scar16", "stub1", story.starting_disease.name.toLowerCase()].includes(normalized)) {
      navigate("/biology");
    } else {
      setMessage("The frozen hackathon fixture is available for SCAR16. No result was synthesized for this query.");
    }
  }
  return (
    <main className="screen search-screen">
      <section className="hero">
        <div className="hero-copy">
          <span className="eyebrow">Mechanism-first rare-disease discovery and research action</span>
          <h1>Rare diseases should not have to solve the same biology alone.</h1>
          <p>Discover related disorders, test whether those connections survive evidence review, identify what remains unknown, and see what research capacity already exists to answer it.</p>
          <form className="search-form" onSubmit={submit}>
            <label htmlFor="disease-search">Which rare disease are you working on?</label>
            <div>
              <input id="disease-search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search disease, gene, symptom or mechanism…" />
              <button type="submit">Explore related biology <Icon name="arrow" /></button>
            </div>
            {message && <p className="form-message" role="status">{message}</p>}
          </form>
          <div className="examples"><span>Demo examples</span><button onClick={() => setQuery("SCAR16")}>SCAR16</button><button onClick={() => setQuery("STUB1")}>STUB1</button><button onClick={() => setQuery(story.goal1.selected_neighbor.name)}>Lafora Disease</button></div>
          <p className="hero-note"><span /> The Atlas distinguishes computational similarity from evidence-supported biology.</p>
        </div>
        <aside className="hero-figure" aria-label="Atlas workflow">
          <span className="figure-index">01—05</span>
          {[
            ["Discover", "candidate biology"],
            ["Validate", "the connection"],
            ["Question", "what remains unknown"],
            ["Test", "a falsifiable experiment"],
            ["Act", "existing capacity"],
          ].map(([title, detail], index) => <div key={title}><b>0{index + 1}</b><span><strong>{title}</strong><small>{detail}</small></span></div>)}
        </aside>
      </section>
      <section className="goal-overview" aria-label="Goal status">
        {(["goal1", "goal3", "goal2"] as const).map((goalKey) => {
          const goal = goals[goalKey];
          return <article key={goalKey}><span>{goalKey.replace("goal", "Goal ")}</span><h2>{goal.question}</h2><StatusPill value={goal.technical_status} label="Technically demonstrated" /><p>{goal.evidence}</p></article>;
        })}
      </section>
      <footer className="attribution">Built on integrated biomedical knowledge from upstream sources including <strong>DisMech</strong> and <strong>Monarch</strong>, with an added evidence-refinement and research-action layer.</footer>
    </main>
  );
}

function graphTone(candidate: Candidate) {
  if (!candidate.independent && candidate.identity !== "DISTINCT_DISEASE") return "identity";
  if (candidate.relationship.includes("INSUFFICIENT")) return "rejected";
  if (candidate.relationship.includes("NON_EQUIVALENT") || candidate.relationship.includes("TISSUE")) return "warning";
  if (candidate.independent) return "supported";
  return "neutral";
}

function CandidateGraph({ story, onSelect }: { story: FlagshipStory; onSelect: (candidate: Candidate) => void }) {
  return (
    <div className="neighbor-graph" aria-label="Candidate relationship overview">
      <div className="graph-center"><span>Starting disease</span><strong>SCAR16</strong><small>STUB1</small></div>
      {story.goal1.candidate_neighbors.map((candidate, index) => (
        <button
          key={candidate.name}
          className={`graph-node node-${index + 1} ${graphTone(candidate)}`}
          onClick={() => onSelect(candidate)}
          aria-label={`${candidate.name}: ${humanize(candidate.relationship)}`}
        >
          <i aria-hidden="true" />
          <span>{candidate.name.length > 25 ? candidate.name.split(" ").slice(0, 3).join(" ") + "…" : candidate.name}</span>
        </button>
      ))}
    </div>
  );
}

export function BiologyScreen({ story, goals, mode }: ScreenProps) {
  const [filter, setFilter] = useState("ALL");
  const [selected, setSelected] = useState<Candidate | null>(null);
  const neighbors = useMemo(() => story.goal1.candidate_neighbors.filter((candidate) => {
    if (filter === "ALL") return true;
    if (filter === "INDEPENDENT") return candidate.independent;
    if (filter === "SPECTRUM") return candidate.identity !== "DISTINCT_DISEASE";
    if (filter === "DOWNGRADED") return story.goal1.rejected_examples.some((item) => item.name === candidate.name);
    return true;
  }), [filter, story]);
  const sameSpectrum = story.goal1.candidate_neighbors.filter((candidate) => candidate.identity !== "DISTINCT_DISEASE").length;
  const independent = story.goal1.candidate_neighbors.filter((candidate) => candidate.independent).length;
  const sharedProcess = story.goal1.candidate_neighbors.filter((candidate) => candidate.relationship === "SHARED_CELLULAR_PROCESS_NON_EQUIVALENT").length;
  return (
    <main className="screen">
      <SectionHeading eyebrow="Goal 1 · Candidate discovery" title="Who shares relevant biology with SCAR16?" description="The graph proposes candidates. Evidence review decides what kind of relationship—if any—survives." />
      <ScientificReviewStatus story={story} compact />
      <section className="summary-bar">
        <div><strong>{story.goal1.candidates_evaluated}</strong><span>candidates examined</span><small>from {story.goal1.candidates_retrieved} retrieved</small></div>
        <div><strong>{sameSpectrum}</strong><span>same-spectrum</span><small>not novel discoveries</small></div>
        <div><strong>{story.goal1.rejected_examples.length}</strong><span>rejected / downgraded</span><small>after evidence review</small></div>
        <div><strong>{sharedProcess}</strong><span>shared process only</span><small>not equivalent mechanism</small></div>
        <div><strong>{independent}</strong><span>independent survivors</span><small>provisional</small></div>
      </section>
      <section className="discovery-layout">
        <div>
          <CandidateGraph story={story} onSelect={setSelected} />
          <p className="graph-legend"><span className="supported" /> Independent survivor <span className="identity" /> Same spectrum <span className="warning" /> Shared context <span className="rejected" /> Insufficient</p>
        </div>
        <aside className="goal-callout"><span className="eyebrow">Retrieval is a starting point</span><h2>Failure is useful here.</h2><p>Rejected and downgraded candidates stay visible. The Atlas is designed to show where similarity does not justify a mechanistic claim.</p><blockquote>{goals.goal1.evidence}</blockquote></aside>
      </section>
      <div className="filter-row" role="group" aria-label="Filter candidates">
        {["ALL", "INDEPENDENT", "SPECTRUM", "DOWNGRADED"].map((item) => <button key={item} onClick={() => setFilter(item)} className={filter === item ? "active" : ""}>{humanize(item)}</button>)}
      </div>
      <section className="candidate-grid">
        {neighbors.map((candidate) => {
          const isFlagship = candidate.name === story.goal1.selected_neighbor.name;
          const rejection = story.goal1.rejected_examples.find((item) => item.name === candidate.name);
          return (
            <article className={`candidate-card ${isFlagship ? "flagship" : ""}`} key={candidate.name}>
              <header><span>Rank {candidate.rank}</span>{isFlagship && <b>Worked demonstration case</b>}</header>
              <h2>{candidate.name}</h2>
              <p className="found-by"><span>Found through</span>{candidate.retrieval_reason}</p>
              <div className="candidate-status"><StatusPill value={candidate.relationship} /><StatusPill value={candidate.retrieval_validity} /></div>
              <p>{rejection?.why || relationshipCopy(candidate.relationship)}</p>
              <dl><div><dt>Independent discovery</dt><dd>{candidate.independent ? "Yes" : "No"}</dd></div><div><dt>Review</dt><dd>Awaiting expert signoff</dd></div></dl>
              {mode === "scientist" && <code>{candidate.identity} · {candidate.relationship} · {candidate.retrieval_validity}</code>}
              {isFlagship && <button className="text-button" onClick={() => navigate("/validate")}>Open evidence refinement <Icon name="arrow" /></button>}
            </article>
          );
        })}
      </section>
      {selected && <aside className="selection-toast" role="status"><span><b>{selected.name}</b>{relationshipCopy(selected.relationship)}</span><button onClick={() => setSelected(null)}>Close</button></aside>}
      <section className="override-note"><div><span className="eyebrow">Transparent selection</span><h2>Lafora is the worked demonstration—not the automated winner.</h2></div><p>{story.goal1.selection.override_reason}</p></section>
      <div className="page-action"><NextButton to="/validate">See why the connection survived</NextButton></div>
    </main>
  );
}

export function ValidateScreen({ story, mode }: ScreenProps) {
  const goal1 = story.goal1;
  const goal3 = story.goal3;
  return (
    <main className="screen signature-screen">
      <SectionHeading eyebrow="Evidence refinement · Signature view" title="Why did the Atlas connect these diseases?" description="Candidate retrieval and biological validation are different operations. This pair demonstrates why that distinction matters." />
      <ScientificReviewStatus story={story} />
      <section className="versus-grid">
        <article className="retrieval-panel">
          <span className="panel-index">01</span><span className="eyebrow">Candidate-generation signal</span>
          <h2>Why the graph found this</h2>
          <div className="mechanism-token muted"><small>Broad annotation</small><strong>{goal1.retrieval_reason.feature}</strong></div>
          <p>The graph retrieved SCAR16 and Lafora because both were associated with this broad biological process.</p>
          <div className="panel-verdict"><Icon name="alert" /><span><b>Useful for retrieval</b>Not sufficient evidence of a shared mechanism.</span></div>
          {mode === "scientist" && <div className="scientist-data"><code>{goal1.retrieval_reason.types.join(" · ")}</code><p>Identity: {goal1.identity_result.relation}</p></div>}
        </article>
        <div className="versus-mark" aria-hidden="true">≠</div>
        <article className="evidence-panel">
          <span className="panel-index">02</span><span className="eyebrow">Evidence-supported interpretation</span>
          <h2>What the evidence supports</h2>
          <div className="mechanism-token"><small>More specific bridge</small><strong>{goal3.mechanistic_bridge.display_label}</strong></div>
          <p>{goal1.validated_relationship.rationale}</p>
          <div className="panel-verdict positive"><Icon name="check" /><span><b>The connection remains</b>The original explanation was incomplete.</span></div>
          {mode === "scientist" && <div className="scientist-data"><code>{goal1.validated_relationship.class}</code><p>Bridge method: {goal3.mechanistic_bridge.derivation_method}</p><p>Variant compatibility: not supplied by contract</p></div>}
        </article>
      </section>
      <section className="signature-statement"><span>{humanize(goal1.validated_relationship.retrieval_validity)}</span><h2>The Atlas found a real connection, but not for the reason the graph originally suggested.</h2><p>{goal1.why_this_matters}</p></section>
      <section className="bridge-row"><div><span className="eyebrow">MechanisticBridge</span><h2>{goal3.mechanistic_bridge.display_label}</h2><div className="term-list">{goal3.mechanistic_bridge.terms.map((term) => <span key={term}>{term}</span>)}</div></div><EvidenceDrawer story={story} ids={goal1.validated_relationship.evidence_ids} mode={mode} title="Relationship evidence" /></section>
      <blockquote className="differentiation">Knowledge graphs tell us what is connected. The Atlas asks whether the connection survives evidence review—and what to do with the uncertainty that remains.</blockquote>
      {mode === "scientist" && <section className="scientist-section"><h2>Evidence lineage</h2><EvidenceLineage story={story} /><dl className="provenance-grid"><div><dt>DisMech commit</dt><dd><code>{story.provenance.dismech_commit}</code></dd></div><div><dt>HPO release</dt><dd><code>{story.provenance.hpo_release}</code></dd></div><div><dt>Pipeline</dt><dd><code>{story.provenance.pipeline_version}</code></dd></div><div><dt>Software</dt><dd><code>{story.provenance.software_commit}</code></dd></div></dl></section>}
      <div className="page-action"><NextButton to="/question">Turn the surviving uncertainty into a test</NextButton></div>
    </main>
  );
}

export function QuestionScreen({ story, mode }: ScreenProps) {
  const goal = story.goal3;
  return (
    <main className="screen">
      <SectionHeading eyebrow="Goal 3 · Knowledge gap and experiment" title="What do we still need to learn?" description="A useful connection creates a sharper question—not an automatic conclusion." />
      <ScientificReviewStatus story={story} compact />
      <section className="gap-card"><div><span className="eyebrow">Critical unanswered question</span><StatusPill value={goal.evidence_status} /></div><h2>{goal.knowledge_gap.question}</h2><div className="known-unknown"><article><span>What we know</span><p>The current evidence supports a downstream bridge involving {goal.mechanistic_bridge.display_label}.</p></article><article><span>What we do not know</span><p>{goal.knowledge_gap.missing_evidence[0]}</p></article><article><span>Why it matters</span><p>{goal.knowledge_gap.why_it_matters}</p></article></div>{mode === "scientist" && <code>gap_id: {goal.knowledge_gap.id}</code>}</section>
      <section className="experiment-section">
        <div className="experiment-title"><span className="eyebrow">Falsifiable experiment</span><h2>How could we test the uncertainty?</h2></div>
        <div className="experiment-flow">
          <div className="model-arms"><article><span>Disease arm A</span><b>SCAR16 model</b></article><article><span>Disease arm B</span><b>Lafora model</b></article><article><span>Shared comparator</span><b>Matched control</b></article></div>
          <div className="flow-arrow"><Icon name="arrow" /><span>same conditions</span></div>
          <article className="flow-stage"><span>Model system</span><b>{goal.experiment.model_system}</b></article>
          <div className="flow-arrow"><Icon name="arrow" /><span>one assay</span></div>
          <article className="flow-stage primary"><span>Primary readout</span><b>{goal.experiment.primary_readout}</b></article>
        </div>
      </section>
      <section className="falsification-grid"><article className="supports"><span><Icon name="check" /> Would support the hypothesis</span><p>{goal.supports_if}</p></article><article className="refutes"><span><Icon name="alert" /> Would weaken or refute it</span><p>{goal.refutes_if}</p></article></section>
      <details className="experiment-details"><summary>Experiment details <span>Scientific protocol view</span></summary><div className="details-grid"><article><h3>Hypothesis</h3><p>{goal.experiment.hypothesis}</p></article><article><h3>Competing hypothesis</h3><p>{goal.experiment.competing_hypothesis}</p></article><article><h3>Shared comparator</h3><p>{goal.experiment.comparator}</p></article><article><h3>Secondary readouts</h3><ul>{goal.experiment.secondary_readouts.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Limitations</h3><ul>{goal.experiment.limitations.map((item) => <li key={item}>{item}</li>)}</ul></article><article><h3>Evidence limitations</h3><ul>{goal.evidence_limitations.map((item) => <li key={item}>{item}</li>)}</ul></article></div>{mode === "scientist" && <EvidenceLineage story={story} />}</details>
      <div className="page-action"><NextButton to="/existing-work">Map what already exists</NextButton></div>
    </main>
  );
}

function workForCapability(story: FlagshipStory, capability: string) {
  return story.goal2.existing_work.find((work) => work.capability === capability);
}

export function ExistingWorkScreen({ story, goals, mode }: ScreenProps) {
  const goal = story.goal2;
  return (
    <main className="screen">
      <SectionHeading eyebrow="Goal 2 · Research action" title="What already exists to run this experiment?" description="The Atlas works backward from the experiment to the capabilities and assets it requires." />
      <ScientificReviewStatus story={story} compact />
      <section className="readiness-strip"><div><span>Execution readiness</span><StatusPill value={goal.execution_readiness} /></div><p>{goals.goal2.evidence}</p><code>{goal.execution_topology}</code></section>
      <section className="capability-board"><header><span>Capability</span><span>Status & evidence</span><span>What remains to verify</span></header>{goal.required_capabilities.map((capability) => {
        const work = workForCapability(story, capability.capability);
        return <article key={capability.id} className={capability.status === "UNKNOWN" ? "missing" : ""}><div><small>{capability.id}</small><h2>{capability.capability}</h2><p>{capability.why}</p></div><div><StatusPill value={capability.status} />{work ? <p>{work.candidates.length} publication-linked team candidates</p> : <p>No candidate met the current search definition.</p>}</div><div><p>{work?.verification_gap || goal.missing_capabilities.find((item) => item.capability === capability.capability)?.note || "Verification detail unavailable."}</p>{work && <details><summary>View candidate evidence</summary><ul className="candidate-evidence">{work.candidates.map((candidate) => <li key={`${candidate.name}-${candidate.source}`}><b>{candidate.name}</b><span>{candidate.source} · {candidate.year}</span><small>{humanize(candidate.evidence_scope)} · {humanize(candidate.recency)}</small><em>Willingness: {humanize(candidate.collaboration_willingness)}</em></li>)}</ul></details>}</div>{mode === "scientist" && <code>{capability.status} · capability_verified: {work?.candidates.every((candidate) => candidate.capability_verified) ? "true" : "false"}</code>}</article>;
      })}</section>
      <section className="asset-coordination-grid"><article className="empty-state"><span className="eyebrow">Existing assets</span><h2>No verified reusable asset identified</h2><p>A model or assay appearing in a paper does not automatically mean it is currently available for reuse.</p><StatusPill value={goal.asset_status} /></article><article className="empty-state"><span className="eyebrow">Coordination</span><h2>No supported overlap flagged</h2><p>{goal.coordination_note}</p><small>This is a scoped search result, not proof that no overlapping program exists.</small></article></section>
      <section className="topology"><div><span className="eyebrow">Execution topology</span><h2>{humanize(goal.execution_topology)}</h2><p>The experiment requires several capability blocks. Publication evidence suggests some exist, but no single verified collaborator covers the full design.</p></div><div className="topology-diagram">{goal.required_capabilities.map((capability) => <div key={capability.id} className={capability.status === "UNKNOWN" ? "unknown" : "covered"}><span>{capability.status === "UNKNOWN" ? "?" : "✓"}</span><b>{capability.capability}</b></div>)}<Icon name="arrow" /><article><span>Flagship experiment</span><b>Shared, matched functional comparison</b></article></div></section>
      <section className="milestone"><span className="eyebrow">Proposed next research milestone</span><h2>{story.goal3.experiment.primary_readout}</h2><div><article><span>What is available</span><p>{goal.required_capabilities.filter((item) => item.status !== "UNKNOWN").length} of {goal.required_capabilities.length} capability areas have publication-linked candidates.</p></article><article><span>What is still missing</span><p>{goal.missing_capabilities.map((item) => item.capability).join(", ")}. Candidate capability and willingness remain unverified.</p></article><article><span>Scientific review</span><p>Awaiting expert signoff before scientific or financial action.</p></article></div><StatusPill value={goal.collaborator_status} /><p className="contact-note"><b>Potential verification target: {goal.first_contact.target}</b>{goal.first_contact.caveat}</p></section>
      {mode === "scientist" && <section className="scientist-section"><h2>Full lineage and provenance</h2><EvidenceLineage story={story} /><p className="integrity-note"><Icon name="alert" /> The interface displays stored conclusions only. Candidate willingness, asset availability, and mechanistic equivalence are not inferred.</p></section>}
      <footer className="closing"><p>We don’t just find connections. We determine which ones survive evidence review and turn the surviving uncertainty into a research plan.</p><button onClick={() => navigate("/discover")}>Restart demo</button></footer>
    </main>
  );
}
