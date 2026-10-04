import { useState } from "react";

import { navigate } from "./components";
import { type DemoCase } from "./contract";
import { loadCases, selectCase } from "./data";

/**
 * Three worked cases showcase screen (plus null case & extra case).
 *
 * Demonstrates the exact same pipeline run across different starting diseases
 * to prove selectivity, bi-directional cluster recovery, and non-neurological generalizability.
 */
export function CasesScreen() {
  const result = loadCases();
  const [active, setActive] = useState<string | null>(null);

  if (!result.ok) {
    return (
      <section className="screen">
        <h2>Case contract failed validation</h2>
        <ul>
          {result.errors.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      </section>
    );
  }

  const current = selectCase(result.cases, active);

  return (
    <section className="screen cases-screen">
      <header className="cases-header">
        <span className="eyebrow">Evidence-Refined Validation</span>
        <h2>Three worked cases</h2>
        <p className="lede">
          The same pipeline, run from three primary starting diseases. The outcomes differ because the evidence differs — demonstrating that our system filters co-citation noise and rejects unsupported leads.
        </p>
      </header>

      {/* Featured 3-Case Highlight Cards */}
      <div className="cases-summary-bar">
        <div className="summary-card-mini scar16">
          <div className="mini-badge">SCAR16</div>
          <strong>Full Chain</strong>
          <small>Found for wrong reason, corrected to CHIP/HSF1</small>
        </div>
        <div className="summary-card-mini lafora">
          <div className="mini-badge">Lafora</div>
          <strong>Full Chain</strong>
          <small>Recovers same cluster from reverse direction</small>
        </div>
        <div className="summary-card-mini ankylosing">
          <div className="mini-badge">Ankylosing</div>
          <strong>Full Chain</strong>
          <small>Non-neurological, 5 of 8 candidates rejected</small>
        </div>
      </div>

      <nav className="case-tabs" aria-label="Worked cases">
        {result.cases.cases.map((item) => (
          <button
            key={item.case_id}
            type="button"
            className={item.case_id === current.case_id ? "case-tab active" : "case-tab"}
            aria-pressed={item.case_id === current.case_id}
            onClick={() => setActive(item.case_id)}
          >
            <span className="case-tab-disease">{item.starting_disease.name}</span>
            <span
              className={
                item.outcome === "FULL_CHAIN" ? "badge badge-ok" : "badge badge-null"
              }
            >
              {item.outcome === "FULL_CHAIN" ? "full chain" : "no connection"}
            </span>
          </button>
        ))}
      </nav>

      <CaseDetail key={current.case_id} item={current} />
    </section>
  );
}

function CaseDetail({ item }: { item: DemoCase }) {
  const g1 = item.goal1;

  // Highlights for the 3 core cases
  const highlights: Record<string, string> = {
    scar16: "SCAR16 Case Highlight: Broad 'protein ubiquitination' tag was rejected during evidence review and refined into a specific CHIP/HSF1 co-chaperone stress response bridge.",
    lafora: "Lafora Case Highlight: Starting from Lafora Disease independently recovers the STUB1/SCAR16 cluster from the reverse direction, confirming bi-directional consistency.",
    ankylosing: "Ankylosing Spondylitis Highlight: Demonstrates application to immunology. 5 of 8 candidates were rejected because massive paper volume masked true mechanistic relationships.",
  };

  return (
    <article className="case-detail">
      <div className="case-title-row">
        <div>
          <h3>{item.label}</h3>
          <p className="why">{item.why_included}</p>
        </div>
        {item.outcome === "FULL_CHAIN" && (
          <button
            type="button"
            className="primary-button launch-journey-btn"
            onClick={() => navigate(`/disease?case=${item.case_id}`)}
          >
            Launch Interactive Walkthrough →
          </button>
        )}
      </div>

      {highlights[item.case_id] && (
        <div className="case-highlight-banner">
          <span className="banner-icon">★</span>
          <span>{highlights[item.case_id]}</span>
        </div>
      )}

      <dl className="case-stats">
        <div>
          <dt>Candidates retrieved</dt>
          <dd>{g1.candidates_retrieved}</dd>
        </div>
        <div>
          <dt>Evaluated</dt>
          <dd>{g1.candidates_evaluated}</dd>
        </div>
        <div>
          <dt>Rejected or downgraded</dt>
          <dd>{g1.rejected_examples.length}</dd>
        </div>
        <div>
          <dt>Excluded as same entity</dt>
          <dd>{g1.excluded_as_same_entity.length}</dd>
        </div>
      </dl>

      <h4>What came back</h4>
      <table className="case-table">
        <thead>
          <tr>
            <th>#</th>
            <th>Candidate</th>
            <th>Found because</th>
            <th>Evidence says</th>
            <th>Independent?</th>
          </tr>
        </thead>
        <tbody>
          {g1.candidate_neighbors.map((candidate) => (
            <tr key={candidate.name}>
              <td>{candidate.rank}</td>
              <td><strong>{candidate.name}</strong></td>
              <td className="muted">{candidate.retrieval_reason}</td>
              <td>
                <code className="relationship-code">{candidate.relationship}</code>
              </td>
              <td>{candidate.independent ? "yes" : "no"}</td>
            </tr>
          ))}
        </tbody>
      </table>

      {item.outcome === "NO_DEFENSIBLE_CONNECTION" ? (
        <aside className="null-result">
          <h4>No connection was reported</h4>
          <p>{item.no_connection_statement}</p>
        </aside>
      ) : (
        <FullChain item={item} />
      )}

      <footer className="disclaimer">{item.disclaimer.headline}</footer>
    </article>
  );
}

function FullChain({ item }: { item: DemoCase }) {
  if (!item.goal3) return null;
  const bridge = item.goal3.mechanistic_bridge;
  const validated = item.goal1.validated_relationship;
  return (
    <>
      <h4>What the evidence said</h4>
      {validated ? (
        <p>
          Retrieved on <em>{item.goal1.retrieval_reason?.feature}</em>, which the
          evidence judged <code>{validated.retrieval_validity}</code>. The
          relationship is <code>{validated.class}</code>, supported by{" "}
          {validated.evidence_ids.join(", ") || "no sources"}.
        </p>
      ) : null}

      <h4>The bridge actually tested</h4>
      <p className="bridge-tested">
        <strong>{bridge.display_label ?? bridge.terms.join(", ")}</strong>
      </p>
      <p className="muted">
        Evidence depth <code>{bridge.evidence_depth}</code>; full text reviewed:{" "}
        {String(bridge.full_text_review_completed)}.
      </p>

      <h4>What remains unknown</h4>
      <p>{item.goal3.knowledge_gap.question}</p>

      <h4>What would settle it</h4>
      <p className="muted">Primary readout: {item.goal3.experiment.primary_readout}</p>
      <p>
        <strong>Refutes if:</strong> {item.goal3.refutes_if}
      </p>

      {item.goal2 ? (
        <>
          <h4>What already exists</h4>
          <p>
            {item.goal2.existing_work.length} of{" "}
            {item.goal2.required_capabilities.length} required capabilities have a
            published candidate; {item.goal2.missing_capabilities.length} do not.
            Topology <code>{item.goal2.execution_topology}</code>, and{" "}
            <code>{item.goal2.collaborator_status}</code>.
          </p>
        </>
      ) : null}
    </>
  );
}
