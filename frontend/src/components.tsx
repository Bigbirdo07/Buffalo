import type { ReactNode } from "react";
import type { FlagshipStory, PresentationMode } from "./contract";

export const ROUTES = [
  { path: "/discover", label: "Start", short: "1", goal: "" },
  { path: "/biology", label: "Discover", short: "2", goal: "Goal 1" },
  { path: "/validate", label: "Validate", short: "3", goal: "Evidence" },
  { path: "/question", label: "Question & test", short: "4", goal: "Goal 3" },
  { path: "/existing-work", label: "Existing work", short: "5", goal: "Goal 2" },
] as const;

export function navigate(path: string) {
  window.location.hash = path;
  window.scrollTo({ top: 0, behavior: "smooth" });
}

export function Icon({ name }: { name: "arrow" | "check" | "book" | "alert" | "external" }) {
  const paths = {
    arrow: <path d="M5 12h14m-5-5 5 5-5 5" />,
    check: <path d="m5 12 4 4L19 6" />,
    book: <><path d="M4 5.5A2.5 2.5 0 0 1 6.5 3H11v16H6.5A2.5 2.5 0 0 0 4 21.5z"/><path d="M20 5.5A2.5 2.5 0 0 0 17.5 3H13v16h4.5a2.5 2.5 0 0 1 2.5 2.5z"/></>,
    alert: <><path d="M12 9v4"/><path d="M12 17h.01"/><path d="m10.3 3.7-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.7-3.3l-8-14a2 2 0 0 0-3.4 0Z"/></>,
    external: <><path d="M15 3h6v6"/><path d="m10 14 11-11"/><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/></>,
  };
  return <svg className="icon" viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export function ModeToggle({ mode, onChange }: { mode: PresentationMode; onChange: (mode: PresentationMode) => void }) {
  return (
    <div className="mode-toggle" aria-label="Presentation mode">
      <button className={mode === "family" ? "active" : ""} onClick={() => onChange("family")}>Family</button>
      <button className={mode === "scientist" ? "active" : ""} onClick={() => onChange("scientist")}>Scientist</button>
    </div>
  );
}

export function GoalProgress({ active }: { active: string }) {
  return (
    <nav className="progress" aria-label="Demo progress">
      {ROUTES.map((route, index) => (
        <button
          key={route.path}
          className={active === route.path ? "active" : ""}
          onClick={() => navigate(route.path)}
          aria-current={active === route.path ? "page" : undefined}
        >
          <span className="progress-number">{route.short}</span>
          <span><b>{route.label}</b>{route.goal && <small>{route.goal}</small>}</span>
          {index < ROUTES.length - 1 && <i aria-hidden="true" />}
        </button>
      ))}
    </nav>
  );
}

export function ScientificReviewStatus({ story, compact = false }: { story: FlagshipStory; compact?: boolean }) {
  return (
    <aside className={`review-status ${compact ? "compact" : ""}`} aria-label="Scientific review status">
      <span className="status-dot amber" aria-hidden="true" />
      <div>
        <strong>Provisional machine synthesis</strong>
        <span>Awaiting expert signoff</span>
        {!compact && <small>{story.disclaimer.headline}</small>}
      </div>
    </aside>
  );
}

export function StatusPill({ value, label }: { value: string; label?: string }) {
  const normalized = value.toLowerCase();
  let tone = "neutral";
  if (normalized.includes("supported") || normalized.includes("correct")) tone = "supported";
  if (normalized.includes("same") || normalized.includes("overlap")) tone = "identity";
  if (normalized.includes("insufficient") || normalized.includes("unresolved") || normalized.includes("unknown")) tone = "missing";
  if (normalized.includes("incorrect") || normalized.includes("rejected")) tone = "rejected";
  if (normalized.includes("awaiting") || normalized.includes("provisional")) tone = "review";
  if (normalized.includes("non_equivalent") || normalized.includes("incomplete")) tone = "warning";
  const plainLabels: Record<string, string> = {
    SHARED_DOWNSTREAM_MECHANISM: "Provisional relationship",
    SHARED_CELLULAR_PROCESS_NON_EQUIVALENT: "Shared process only",
    SHARED_TISSUE_CONTEXT: "Shared tissue context",
    INSUFFICIENT_EVIDENCE: "Insufficient evidence",
    INCORRECT_BUT_CONNECTION_REAL: "Retrieval reason incomplete",
    CORRECT: "Retrieval reason supported",
    UNRESOLVED: "Unresolved",
    INCOMPLETE: "Incomplete",
    COVERED_SUPPORTED: "Publication-supported",
    UNKNOWN: "Unknown",
    PARTIAL: "Partial",
    PROVISIONALLY_SUPPORTED: "Provisionally supported",
    NO_VERIFIED_COLLABORATOR_IDENTIFIED: "No verified collaborator",
    NO_RELEVANT_ASSET_IDENTIFIED: "No verified relevant asset",
  };
  return (
    <span className={`pill ${tone}`} title={value}>
      {label ?? plainLabels[value] ?? humanize(value)}
    </span>
  );
}

export function humanize(value: string) {
  return value.toLowerCase().replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function relationshipCopy(value: string) {
  const copy: Record<string, string> = {
    SAME_ALLELIC_SPECTRUM: "These labels describe the same genetic disease spectrum.",
    SHARED_CELLULAR_PROCESS_NON_EQUIVALENT: "The diseases affect the same broad cellular process, but probably in different ways.",
    INSUFFICIENT_EVIDENCE: "The candidate has not yet survived the evidence threshold.",
    SHARED_TISSUE_CONTEXT: "The diseases affect comparable tissue without a demonstrated molecular relationship.",
    SHARED_DOWNSTREAM_MECHANISM: "Evidence supports a shared downstream biological relationship.",
  };
  return copy[value] ?? humanize(value);
}

export function SectionHeading({ eyebrow, title, description }: { eyebrow: string; title: string; description?: string }) {
  return (
    <header className="section-heading">
      <span className="eyebrow">{eyebrow}</span>
      <h1>{title}</h1>
      {description && <p>{description}</p>}
    </header>
  );
}

export function EvidenceDrawer({ story, ids, mode, title = "Evidence record" }: { story: FlagshipStory; ids: string[]; mode: PresentationMode; title?: string }) {
  const bridge = story.goal3.mechanistic_bridge;
  return (
    <details className="evidence-drawer">
      <summary><Icon name="book" /> View evidence <span>{ids.length}</span></summary>
      <div className="drawer-content">
        <div className="drawer-header"><span className="eyebrow">{title}</span><StatusPill value={story.goal3.evidence_status} /></div>
        {ids.map((id) => (
          <article className="evidence-item" key={id}>
            <div><strong>{id.replace(":", " ")}</strong><span>Primary literature identifier</span></div>
            <dl>
              <div><dt>Evidence role</dt><dd>Relationship rationale describes two independent primary findings; per-source role is not supplied</dd></div>
              <div><dt>Evidence depth</dt><dd>{humanize(bridge.evidence_depth)}</dd></div>
              <div><dt>Full text review</dt><dd>{bridge.full_text_review_completed ? "Completed" : "Not completed"}</dd></div>
              <div><dt>Title</dt><dd>Not supplied by frozen contract</dd></div>
              <div><dt>Exact source span</dt><dd>Not supplied by frozen contract</dd></div>
            </dl>
            {mode === "scientist" && <code>derived_from: {id} · bridge: {bridge.id}</code>}
          </article>
        ))}
        <p className="integrity-note"><Icon name="alert" /> Missing titles and spans are shown as unavailable; the interface does not synthesize them.</p>
      </div>
    </details>
  );
}

export function EvidenceLineage({ story }: { story: FlagshipStory }) {
  const steps = [
    ["Source", story.goal1.validated_relationship.evidence_ids.join(", ")],
    ["Relationship", story.goal1.validated_relationship.class],
    ["Bridge", story.goal3.mechanistic_bridge.id],
    ["Knowledge gap", story.goal3.knowledge_gap.id],
    ["Experiment", story.goal3.experiment.id],
    ["Capabilities", `${story.goal2.required_capabilities.length} requirements`],
  ];
  return (
    <div className="lineage" aria-label="Evidence lineage">
      {steps.map(([label, value], index) => (
        <div key={label}>
          <span>{label}</span><code>{value}</code>
          {index < steps.length - 1 && <Icon name="arrow" />}
        </div>
      ))}
    </div>
  );
}

export function NextButton({ to, children }: { to: string; children: ReactNode }) {
  return <button className="primary-button" onClick={() => navigate(to)}>{children}<Icon name="arrow" /></button>;
}

export function ContractUnavailable({ errors }: { errors: string[] }) {
  return (
    <main className="contract-error">
      <span className="eyebrow">Demo contract unavailable</span>
      <h1>The scientific story could not be loaded safely.</h1>
      <p>The interface will not synthesize missing fields. Correct the frozen contract and reload.</p>
      <ul>{errors.map((error) => <li key={error}><code>{error}</code></li>)}</ul>
    </main>
  );
}
