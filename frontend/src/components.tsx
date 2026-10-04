import type { ReactNode } from "react";
import type { FlagshipStory, ParentPathNode, PresentationMode } from "./contract";

export const ROUTES = [
  { path: "/disease", family: "1. Your Disease & Causes", scientist: "1. Disease Overview", short: "1" },
  { path: "/connections", family: "2. Connections & Evidence", scientist: "2. Connections & Evidence", short: "2" },
  { path: "/unknown", family: "3. What's Unknown", scientist: "3. What's Unknown & Test", short: "3" },
  { path: "/existing-work", family: "4. Existing Work", scientist: "4. Existing Work & Action", short: "4" },
] as const;

export function navigate(path: string) {
  window.location.hash = path;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

export function Icon({ name }: { name: "arrow" | "check" | "book" | "alert" | "print" | "flask" | "question" }) {
  const paths = {
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    check: <path d="m5 12 4 4L19 6" />,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></>,
    alert: <><path d="M12 9v4"/><path d="M12 17h.01"/><path d="m10.3 3.7-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3.3l-8-14a2 2 0 0 0-3.4 0Z"/></>,
    print: <><path d="M6 9V2h12v7"/><path d="M6 18H4a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2h-2"/><path d="M6 14h12v8H6z"/></>,
    flask: <><path d="M9 3h6"/><path d="M10 3v6l-5 9a2 2 0 0 0 1.7 3h10.6a2 2 0 0 0 1.7-3l-5-9V3"/><path d="M8 15h8"/></>,
    question: <><circle cx="12" cy="12" r="9"/><path d="M9.8 9a2.3 2.3 0 1 1 3.5 2c-.8.5-1.3 1-1.3 2"/><path d="M12 17h.01"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export function ModeToggle({ mode, onChange }: { mode: PresentationMode; onChange: (mode: PresentationMode) => void }) {
  return <div className="mode-toggle" aria-label="Presentation mode"><button className={mode === "family" ? "active" : ""} onClick={() => onChange("family")}>Family</button><button className={mode === "scientist" ? "active" : ""} onClick={() => onChange("scientist")}>Scientist</button></div>;
}

export function JourneyProgress({ active, mode }: { active: string; mode: PresentationMode }) {
  // Map secondary routes to the 4 main tabs if needed
  let normalizedPath = active;
  if (active === "/evidence") normalizedPath = "/connections";
  if (active === "/experiment") normalizedPath = "/unknown";
  if (active === "/next-steps") normalizedPath = "/existing-work";

  return (
    <nav className="journey-progress" aria-label="Research journey">
      {ROUTES.map((route) => (
        <button
          key={route.path}
          className={normalizedPath === route.path ? "active" : ""}
          onClick={() => navigate(route.path)}
          aria-current={normalizedPath === route.path ? "page" : undefined}
        >
          <span>{route.short}</span>
          <b>{mode === "family" ? route.family : route.scientist}</b>
        </button>
      ))}
    </nav>
  );
}

export function GuidePanel({ question, children }: { question: string; children: ReactNode }) {
  return <aside className="guide-panel"><span><Icon name="question" /> Guide</span><h2>{question}</h2><div>{children}</div></aside>;
}

export function EntityLegend() {
  return <aside className="entity-legend" aria-label="Entity legend"><span><i className="entity-shape disease" />Disease</span><span><i className="entity-shape gene" />Gene</span><span><i className="entity-shape protein" />Protein</span><span><i className="entity-shape process" />Biological process</span><span><i className="legend-symbol">?</i>Open question</span><span><Icon name="flask" />Experiment</span></aside>;
}

export function EntityNode({ node, active = false }: { node: ParentPathNode; active?: boolean }) {
  return <article className={`entity-node ${node.entity_type.toLowerCase()} ${active ? "active" : ""}`}><i className={`entity-shape ${node.entity_type.toLowerCase()}`} aria-hidden="true" /><div><small>{humanize(node.entity_type)}</small><h3>{node.label}</h3><p>{node.meaning}</p></div></article>;
}

export function ReviewStatus({ story }: { story: FlagshipStory }) {
  return <aside className="review-status compact" aria-label="Scientific review status"><span className="status-dot amber" aria-hidden="true" /><div><strong>Promising but unconfirmed</strong><span>Awaiting expert signoff</span><small>{humanize(story.goal3.mechanistic_bridge.evidence_depth)} evidence; full text {story.goal3.mechanistic_bridge.full_text_review_completed ? "reviewed" : "not reviewed"}</small></div></aside>;
}

export function StatusPill({ value, label }: { value: string; label?: string }) {
  const normalized = value.toLowerCase();
  let tone = "neutral";
  if (normalized.includes("supported") || normalized.includes("correct")) tone = "supported";
  if (normalized.includes("same") || normalized.includes("spectrum")) tone = "identity";
  if (normalized.includes("insufficient") || normalized.includes("unknown") || normalized.includes("missing")) tone = "missing";
  if (normalized.includes("incorrect") || normalized.includes("rejected")) tone = "rejected";
  if (normalized.includes("provisional") || normalized.includes("unconfirmed")) tone = "review";
  const labels: Record<string, string> = { SHARED_DOWNSTREAM_MECHANISM: "Possible shared downstream biology", SHARED_CELLULAR_PROCESS_NON_EQUIVALENT: "Shared process, likely different effects", SHARED_TISSUE_CONTEXT: "Similar tissue context only", SAME_ALLELIC_SPECTRUM: "Same genetic disease spectrum", INSUFFICIENT_EVIDENCE: "Not supported strongly enough", INCORRECT_BUT_CONNECTION_REAL: "First explanation was incomplete", COVERED_SUPPORTED: "Evidence of this capability found", UNKNOWN: "Not yet found" };
  return <span className={`pill ${tone}`} title={value}>{label ?? labels[value] ?? humanize(value)}</span>;
}

export function humanize(value: string) { return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase()); }

export function NextButton({ to, children }: { to: string; children: ReactNode }) { return <button className="primary-button" onClick={() => navigate(to)}>{children}<Icon name="arrow" /></button>; }

export function EvidenceDrawer({ story, mode }: { story: FlagshipStory; mode: PresentationMode }) {
  return <details className="evidence-drawer"><summary><Icon name="book" /> See the evidence <span>{story.goal1.validated_relationship.evidence_ids.length}</span></summary><div className="drawer-content">{story.goal1.validated_relationship.evidence_ids.map((id) => <article className="evidence-item" key={id}><div><strong>{id}</strong><span>Primary literature identifier</span></div><dl><div><dt>Role</dt><dd>One of two independent primary findings supporting the refined relationship</dd></div><div><dt>Evidence depth</dt><dd>{humanize(story.goal3.mechanistic_bridge.evidence_depth)}</dd></div><div><dt>Full text</dt><dd>{story.goal3.mechanistic_bridge.full_text_review_completed ? "Reviewed" : "Not reviewed"}</dd></div><div><dt>Exact source span</dt><dd>Not supplied by frozen contract</dd></div></dl>{mode === "scientist" && <code>bridge_id: {story.goal3.mechanistic_bridge.id}</code>}</article>)}<p className="integrity-note"><Icon name="alert" /> Missing titles and source spans remain unavailable; this interface does not invent them.</p></div></details>;
}

export function EvidenceLineage({ story }: { story: FlagshipStory }) {
  const steps = [["Sources", story.goal1.validated_relationship.evidence_ids.join(", ")], ["Relationship", story.goal1.validated_relationship.class], ["Bridge", story.goal3.mechanistic_bridge.id], ["Open question", story.goal3.knowledge_gap.id], ["Experiment", story.goal3.experiment.id], ["Capabilities", `${story.goal2.required_capabilities.length} requirements`]];
  return <div className="lineage" aria-label="Evidence lineage">{steps.map(([label, value], index) => <div key={label}><span>{label}</span><code>{value}</code>{index < steps.length - 1 && <Icon name="arrow" />}</div>)}</div>;
}

export function ContractUnavailable({ errors }: { errors: string[] }) { return <main className="contract-error"><span className="eyebrow">Demo contract unavailable</span><h1>The scientific story could not be loaded safely.</h1><p>The interface will not synthesize missing fields.</p><ul>{errors.map((error) => <li key={error}><code>{error}</code></li>)}</ul></main>; }
