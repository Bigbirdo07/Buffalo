import { useCallback, useEffect, useMemo, useState } from "react";

import { navigate } from "./components";
import type { DemoCase, ParentStory, PresentationMode } from "./contract";

/**
 * The lineage canvas: the product as a traced path rather than a dashboard.
 *
 * One disease enters at the bottom and the biology grows upward, a step at a
 * time, until the path runs out at a question nobody has answered. Nothing is
 * shown before the viewer asks for it, because the whole difficulty of this
 * subject is that everything is connected to everything and a complete graph
 * teaches nobody anything.
 *
 * Every node here comes from the contract. The frontend draws the path; it does
 * not decide what is on it.
 */

type Stage =
  | "root"
  | "gene"
  | "protein"
  | "process"
  | "branch"
  | "retrieval"
  | "refined"
  | "question"
  | "experiment"
  | "capability";

const ORDER: Stage[] = [
  "root", "gene", "protein", "process", "branch",
  "retrieval", "refined", "question", "experiment", "capability",
];

/** One line of narration per stage, so the demo explains itself. */
const NARRATION: Record<Stage, string> = {
  root: "We begin with the disease a family already knows.",
  gene: "First we trace the genetic foundation.",
  protein: "Then the gene becomes the protein it affects.",
  process: "That protein leads to the cellular systems that may be disrupted.",
  branch: "Now we can ask whether another rare disease touches the same biology.",
  retrieval: "This is why the search found it — a broad shared annotation.",
  refined: "But we do not trust that similarity automatically.",
  question: "That leaves one important thing researchers still do not know.",
  experiment: "We turn that uncertainty into a test that could prove the idea wrong.",
  capability: "Finally, we ask whether the pieces to run it already exist.",
};

const STEP_LABEL: Record<Stage, string> = {
  root: "Start", gene: "Trace biology", protein: "Trace biology",
  process: "Trace biology", branch: "Related diseases", retrieval: "Evidence check",
  refined: "Evidence check", question: "Open question", experiment: "Experiment",
  capability: "Existing work",
};

type NodeKind = "DISEASE" | "GENE" | "PROTEIN" | "PROCESS" | "QUESTION";

type LineageNode = {
  id: string;
  label: string;
  kind: NodeKind;
  meaning: string;
  /** Vertical position, 0 at the root. */
  row: number;
  /** Horizontal offset in columns; 0 is the trunk. */
  column: number;
};

export function LineageScreen({
  activeCase,
  parent,
  mode,
}: {
  activeCase: DemoCase | null;
  parent: ParentStory;
  mode: PresentationMode;
}) {
  const [stageIndex, setStageIndex] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const stage = ORDER[stageIndex];

  const hasChain = activeCase?.outcome === "FULL_CHAIN";
  const narrated = !activeCase || activeCase.case_id === "scar16";

  // The spine comes from the contract. Only the narrated case has a written
  // path; others trace as far as their own data supports and say so.
  const spine: LineageNode[] = useMemo(() => {
    if (!narrated) return [];
    return parent.guided_path.map((entry, index) => ({
      id: entry.id,
      label: entry.label,
      kind: entry.entity_type as NodeKind,
      meaning: entry.meaning,
      row: index,
      column: index === parent.guided_path.length - 1 ? 1 : 0,
    }));
  }, [narrated, parent.guided_path]);

  const visibleCount = useMemo(() => {
    switch (stage) {
      case "root": return 1;
      case "gene": return 2;
      case "protein": return 3;
      case "process": return 4;
      default: return spine.length;
    }
  }, [stage, spine.length]);

  const visible = spine.slice(0, visibleCount);
  const selected = spine.find((node) => node.id === selectedId) ?? visible[visible.length - 1];

  const advance = useCallback(() => {
    setStageIndex((current) => Math.min(current + 1, ORDER.length - 1));
  }, []);
  const back = useCallback(() => setStageIndex((current) => Math.max(current - 1, 0)), []);

  // Arrow keys drive the walkthrough so a presenter never hunts for a button.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      if (event.key === "ArrowRight") advance();
      if (event.key === "ArrowLeft") back();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [advance, back]);

  if (!activeCase) {
    return <main className="lineage"><p className="results-count">No case selected.</p></main>;
  }

  if (!narrated) {
    return (
      <main className="lineage">
        <UntracedCase activeCase={activeCase} />
      </main>
    );
  }

  return (
    <main className="lineage">
      <p className="narration" aria-live="polite">{NARRATION[stage]}</p>

      <div className="lineage-body">
        <section className="canvas" aria-label="Biological lineage">
          <Tree
            nodes={visible}
            stage={stage}
            activeCase={activeCase}
            selectedId={selected?.id ?? null}
            onSelect={setSelectedId}
          />
          {stage === "experiment" ? <ExperimentDiagram activeCase={activeCase} /> : null}
          {stage === "capability" ? <CapabilityStrip activeCase={activeCase} /> : null}
        </section>

        <aside className="story-panel">
          <StoryPanel
            stage={stage}
            node={selected}
            activeCase={activeCase}
            mode={mode}
            hasChain={hasChain}
          />
          <div className="story-actions">
            {stageIndex > 0 ? (
              <button type="button" className="text-button" onClick={back}>← Back</button>
            ) : <span />}
            {stageIndex < ORDER.length - 1 ? (
              <button type="button" className="primary-button" onClick={advance}>
                {nextLabel(stage)}
              </button>
            ) : (
              <button type="button" className="text-button" onClick={() => navigate("/search")}>
                Trace another disease →
              </button>
            )}
          </div>
        </aside>
      </div>

      <JourneyBar stage={stage} onJump={(target) => setStageIndex(ORDER.indexOf(target))} />
    </main>
  );
}

function nextLabel(stage: Stage): string {
  switch (stage) {
    case "root": return "Follow the biology";
    case "gene": return "Show the protein";
    case "protein": return "Show what it does in the cell";
    case "process": return "Where else does this biology appear?";
    case "branch": return "Why did we find this?";
    case "retrieval": return "Check this connection";
    case "refined": return "What is still unknown?";
    case "question": return "How could researchers answer it?";
    default: return "Could this experiment be done?";
  }
}

/* ------------------------------------------------------------------ tree */

const ROW_HEIGHT = 108;
const COLUMN_WIDTH = 190;

function Tree({
  nodes, stage, activeCase, selectedId, onSelect,
}: {
  nodes: LineageNode[];
  stage: Stage;
  activeCase: DemoCase;
  selectedId: string | null;
  onSelect: (id: string) => void;
}) {
  const showQuestion = ORDER.indexOf(stage) >= ORDER.indexOf("question");
  const rows = nodes.length + (showQuestion ? 1 : 0);
  const height = rows * ROW_HEIGHT + 60;
  const width = 560;
  const centre = width / 2 - 40;

  // Row 0 sits at the bottom: the path grows upward, like a family tree read
  // from the person you started with.
  const y = (row: number) => height - 50 - row * ROW_HEIGHT;
  const x = (column: number) => centre + column * COLUMN_WIDTH * 0.42;

  const refined = ORDER.indexOf(stage) >= ORDER.indexOf("refined");
  const showRetrieval = ORDER.indexOf(stage) >= ORDER.indexOf("retrieval");

  return (
    <svg className="tree" viewBox={`0 0 ${width} ${height}`} role="img"
         aria-label="Biological lineage from the searched disease upward">
      {/* The broad annotation that first linked the pair. It is never erased:
          the point is that the system records why it looked, separately from
          what the evidence supported. */}
      {showRetrieval && nodes.length > 4 ? (
        <>
          <path
            className={refined ? "edge retrieval superseded" : "edge retrieval"}
            d={`M ${x(0)} ${y(2)} C ${x(0)} ${y(3)}, ${x(1)} ${y(3)}, ${x(1)} ${y(4)}`}
          />
          <text className="edge-label superseded-label" x={x(0) + 14} y={y(3) + 4}>
            {activeCase.goal1.retrieval_reason?.feature ?? "shared annotation"}
          </text>
        </>
      ) : null}

      {nodes.slice(1).map((node, index) => {
        const from = nodes[index];
        const isBranch = node.column !== from.column;
        return (
          <path
            key={`edge-${node.id}`}
            className={isBranch && !refined ? "edge pending" : "edge"}
            d={
              isBranch
                ? `M ${x(from.column)} ${y(from.row)} C ${x(from.column)} ${y(node.row)}, ${x(node.column)} ${y(from.row)}, ${x(node.column)} ${y(node.row)}`
                : `M ${x(from.column)} ${y(from.row)} L ${x(node.column)} ${y(node.row)}`
            }
          />
        );
      })}

      {showQuestion ? (
        <path className="edge" d={`M ${x(1)} ${y(nodes.length - 1)} L ${x(1)} ${y(nodes.length)}`} />
      ) : null}

      {nodes.map((node) => (
        <TreeNode
          key={node.id}
          node={node}
          x={x(node.column)}
          y={y(node.row)}
          selected={node.id === selectedId}
          onSelect={onSelect}
        />
      ))}

      {showQuestion ? (
        <g className="node question" transform={`translate(${x(1)}, ${y(nodes.length)})`}>
          <circle className="shape" r="21" />
          <text className="mark" y="7" textAnchor="middle">?</text>
          <text className="label" x="32" y="-2">What researchers still do not know</text>
          <text className="kind" x="32" y="16">Open question — the path ends here</text>
        </g>
      ) : null}
    </svg>
  );
}

function TreeNode({
  node, x, y, selected, onSelect,
}: {
  node: LineageNode; x: number; y: number; selected: boolean;
  onSelect: (id: string) => void;
}) {
  const shape =
    node.kind === "GENE" ? <polygon className="shape" points="0,-20 17,-10 17,10 0,20 -17,10 -17,-10" />
    : node.kind === "PROTEIN" ? <polygon className="shape" points="0,-20 20,0 0,20 -20,0" />
    : node.kind === "PROCESS" ? <rect className="shape" x="-26" y="-15" width="52" height="30" rx="14" />
    : <circle className="shape" r="19" />;

  return (
    <g
      className={`node ${node.kind.toLowerCase()} ${selected ? "selected" : ""}`}
      transform={`translate(${x}, ${y})`}
      onClick={() => onSelect(node.id)}
      role="button"
      tabIndex={0}
      onKeyDown={(event) => { if (event.key === "Enter") onSelect(node.id); }}
    >
      {shape}
      {/* Label, type and meaning are always drawn: nothing essential hides
          behind a hover. */}
      <text className="label" x="34" y="-6">{node.label}</text>
      <text className="kind" x="34" y="10">{titleCase(node.kind)}</text>
      <text className="meaning" x="34" y="26">{truncate(node.meaning, 46)}</text>
    </g>
  );
}

const titleCase = (value: string) => value.charAt(0) + value.slice(1).toLowerCase();
const truncate = (value: string, max: number) =>
  value.length <= max ? value : `${value.slice(0, max - 1)}…`;

/* ----------------------------------------------------------- story panel */

function StoryPanel({
  stage, node, activeCase, mode, hasChain,
}: {
  stage: Stage; node: LineageNode | undefined; activeCase: DemoCase;
  mode: PresentationMode; hasChain: boolean;
}) {
  if (stage === "retrieval") {
    return (
      <div className="story">
        <h2>Why did we find {activeCase.goal1.selected_neighbor?.name}?</h2>
        <h3>Why we looked at it</h3>
        <p>
          The search linked the two diseases through a broad shared annotation:{" "}
          <b>{activeCase.goal1.retrieval_reason?.feature}</b>. That is a reason to
          investigate, not proof of anything.
        </p>
        <h3>Why it could matter</h3>
        <p>
          Research in another disease may let researchers ask a question that has
          not been tested directly in this one.
        </p>
      </div>
    );
  }

  if (stage === "refined" && hasChain && activeCase.goal3) {
    return (
      <div className="story">
        <h2>A real connection — but not for the reason we expected</h2>
        <p>
          The broad annotation helped find the relationship. The evidence pointed
          to something more specific:{" "}
          <b>{activeCase.goal3.mechanistic_bridge.display_label}</b>.
        </p>
        <h3>How do we know?</h3>
        <p>
          {activeCase.goal3.mechanistic_bridge.derived_from.length} supporting
          findings, read from{" "}
          {activeCase.goal3.mechanistic_bridge.derived_from.join(" and ")}.
        </p>
        <p className="caution">
          Evidence depth{" "}
          <b>{activeCase.goal3.mechanistic_bridge.evidence_depth?.replace(/_/g, " ").toLowerCase()}</b>.
          The full papers were not obtained, so a specialist with access may reach
          a different conclusion.
        </p>
        {mode === "scientist" ? (
          <p className="mono">
            RetrievalValidity: {activeCase.goal1.validated_relationship?.retrieval_validity}
          </p>
        ) : null}
      </div>
    );
  }

  if (stage === "question" && activeCase.goal3) {
    return (
      <div className="story">
        <h2>What researchers still do not know</h2>
        <blockquote>{activeCase.goal3.knowledge_gap.question}</blockquote>
        <h3>Why does this matter?</h3>
        <p>{activeCase.goal3.knowledge_gap.why_it_matters}</p>
        {mode === "scientist" ? (
          <p className="mono">KnowledgeGap {activeCase.goal3.knowledge_gap.id}</p>
        ) : null}
      </div>
    );
  }

  if (stage === "experiment" && activeCase.goal3) {
    return (
      <div className="story">
        <h2>The idea</h2>
        <p>
          Put both disease models through the same challenge and measure the same
          cellular response, against a shared healthy control.
        </p>
        <h3>If they respond similarly</h3>
        <p>{activeCase.goal3.supports_if}</p>
        <h3>If they respond differently</h3>
        <p>{activeCase.goal3.refutes_if}</p>
        {mode === "scientist" ? (
          <details>
            <summary>Experiment details</summary>
            <p><b>Model system.</b> {activeCase.goal3.experiment.model_system}</p>
            <p><b>Comparator.</b> {activeCase.goal3.experiment.comparator}</p>
            <p><b>Primary readout.</b> {activeCase.goal3.experiment.primary_readout}</p>
          </details>
        ) : null}
      </div>
    );
  }

  if (stage === "capability" && activeCase.goal2) {
    const covered = activeCase.goal2.existing_work.length;
    const total = activeCase.goal2.required_capabilities.length;
    return (
      <div className="story">
        <h2>Could this experiment actually be done?</h2>
        <p>
          {covered} of {total} pieces have published evidence that someone has done
          them. {activeCase.goal2.missing_capabilities.length} do not.
        </p>
        <h3>The pieces exist across more than one group</h3>
        <p>
          No single group in the current evidence provides every capability this
          experiment needs.
        </p>
        <p className="caution">
          {activeCase.goal2.collaborator_status.replace(/_/g, " ").toLowerCase()}.
          A published technique shows a team did this once. Current availability
          and willingness to collaborate are unverified.
        </p>
      </div>
    );
  }

  if (!node) return null;
  return (
    <div className="story">
      <h2>{node.label}</h2>
      <p className="entity-kind">{titleCase(node.kind)}</p>
      <h3>What is this?</h3>
      <p>{node.meaning}</p>
      <h3>Why is it here?</h3>
      <p>{whyHere(node)}</p>
    </div>
  );
}

function whyHere(node: LineageNode): string {
  switch (node.kind) {
    case "DISEASE": return node.row === 0
      ? "This is the disease we started from."
      : "This disease appeared because it touches the same biology.";
    case "GENE": return "This is the gene associated with the disease we started from.";
    case "PROTEIN": return "This is the protein the gene provides instructions for.";
    case "PROCESS": return "This is the cellular system that protein takes part in.";
    default: return "";
  }
}

/* ------------------------------------------------------------ experiment */

function ExperimentDiagram({ activeCase }: { activeCase: DemoCase }) {
  if (!activeCase.goal3) return null;
  const neighbour = activeCase.goal1.selected_neighbor?.name ?? "the other disease";
  return (
    <div className="experiment-diagram">
      <div className="arms">
        <span>{activeCase.starting_disease.name} model</span>
        <span>{neighbour} model</span>
        <span>Healthy control</span>
      </div>
      <div className="converge">Same stress challenge</div>
      <div className="converge">Same primary readout</div>
      <div className="outcomes">
        <article><b>Similar response</b><p>Supports a shared downstream mechanism.</p></article>
        <article><b>Different response</b><p>Weakens it. The diseases should be studied separately.</p></article>
      </div>
    </div>
  );
}

/* ----------------------------------------------------------- capability */

function CapabilityStrip({ activeCase }: { activeCase: DemoCase }) {
  if (!activeCase.goal2) return null;
  return (
    <div className="capability-strip">
      <h3>What this experiment needs</h3>
      <ul>
        {activeCase.goal2.required_capabilities.map((capability) => {
          const work = activeCase.goal2!.existing_work.find(
            (item) => item.capability === capability.capability,
          );
          return (
            <li key={capability.id} className={work ? "found" : "missing"}>
              <b>{capability.capability}</b>
              <span>
                {work
                  ? `evidence found — ${work.candidates[0]?.name ?? "published work"}`
                  : "not yet identified"}
              </span>
            </li>
          );
        })}
      </ul>
      <p className="map-note">
        Published affiliations name places, but this build has no verified current
        locations, so no map is drawn. Plotting pins would mean inferring where
        people are now from where a paper was written.
      </p>
    </div>
  );
}

/* ------------------------------------------------------------- untraced */

function UntracedCase({ activeCase }: { activeCase: DemoCase }) {
  return (
    <div className="untraced">
      <h1>{activeCase.starting_disease.name}</h1>
      <p className="lede">{activeCase.label}</p>
      <p>
        {activeCase.outcome === "NO_DEFENSIBLE_CONNECTION"
          ? activeCase.no_connection_statement
          : "A traced lineage has been written for one disease so far. This case has full pipeline output but no hand-written path, so it is shown in the goal view instead."}
      </p>
      <button
        type="button"
        className="primary-button"
        onClick={() => navigate(`/atlas?case=${activeCase.case_id}`)}
      >
        See the full analysis
      </button>
    </div>
  );
}

/* ----------------------------------------------------------- journey bar */

function JourneyBar({ stage, onJump }: { stage: Stage; onJump: (stage: Stage) => void }) {
  const steps: Stage[] = ["root", "gene", "branch", "refined", "question", "experiment", "capability"];
  const currentIndex = ORDER.indexOf(stage);
  return (
    <nav className="journey-bar" aria-label="Journey progress">
      {steps.map((step, index) => (
        <button
          key={step}
          type="button"
          className={ORDER.indexOf(step) <= currentIndex ? "done" : ""}
          aria-current={step === stage ? "step" : undefined}
          onClick={() => onJump(step)}
        >
          <b>{index + 1}</b>
          <span>{STEP_LABEL[step]}</span>
        </button>
      ))}
    </nav>
  );
}
