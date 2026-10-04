import { navigate } from "./components";
import type { DemoCase, GoalsSummary, PresentationMode } from "./contract";

/**
 * The product, organised around the three questions it answers.
 *
 * An earlier version told a story about one disease pair, which buried the
 * structure: a reader could not see that Goal 1 rejected most of what it found,
 * or that Goal 2 is honest about what it could not verify. Each goal is now its
 * own panel with its own evidence and its own status, including the statuses
 * that are not successes.
 */
export function GoalsScreen({
  activeCase,
  goals,
  mode,
}: {
  activeCase: DemoCase | null;
  goals: GoalsSummary;
  mode: PresentationMode;
}) {
  if (!activeCase) {
    return (
      <main className="screen goals-screen">
        <p className="results-count">No case selected.</p>
      </main>
    );
  }

  const g1 = activeCase.goal1;
  const independent = g1.candidate_neighbors.filter((c) => c.independent);
  const sameEntity = g1.candidate_neighbors.filter(
    (c) => !c.independent && c.identity !== "DISTINCT_DISEASE",
  );
  const rejected = g1.rejected_examples;
  const hasChain = activeCase.outcome === "FULL_CHAIN";

  return (
    <main className="screen goals-screen">
      <header className="goals-header">
        <div>
          <span className="eyebrow">Disease</span>
          <h1>{activeCase.starting_disease.name}</h1>
          <p>{activeCase.label}</p>
        </div>
        <div className="goals-header-actions">
          <button type="button" className="text-button" onClick={() => navigate("/search")}>
            ← Search another disease
          </button>
          {hasChain ? (
            <button
              type="button"
              className="text-button"
              onClick={() => navigate(`/disease?case=${activeCase.case_id}`)}
            >
              Plain-language walkthrough →
            </button>
          ) : null}
        </div>
      </header>

      {/* ---------------------------------------------------------------- */}
      <GoalPanel
        number={1}
        question="Who genuinely shares this disease's biology?"
        status={goals.goal1.technical_status}
        statusKind="ok"
      >
        <div className="goal-counts">
          <Count value={g1.candidates_retrieved} label="candidates retrieved" />
          <Count value={g1.candidates_evaluated} label="evaluated in depth" />
          <Count value={sameEntity.length} label="excluded — same entity" tone="warn" />
          <Count value={rejected.length} label="rejected on evidence" tone="warn" />
          <Count value={independent.length} label="survived" tone="ok" />
        </div>

        <table className="goal-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Candidate</th>
              <th>Retrieved because</th>
              <th>Evidence says</th>
              <th>Was that the reason?</th>
            </tr>
          </thead>
          <tbody>
            {[...g1.candidate_neighbors]
              .sort((a, b) => a.rank - b.rank)
              .map((candidate) => (
                <tr
                  key={candidate.name}
                  className={candidate.independent ? "survived" : "excluded"}
                >
                  <td>{candidate.rank}</td>
                  <td>
                    <b>{candidate.name}</b>
                    {!candidate.independent && candidate.identity !== "DISTINCT_DISEASE" ? (
                      <small> — {candidate.identity.replace(/_/g, " ").toLowerCase()}</small>
                    ) : null}
                  </td>
                  <td className="muted">{candidate.retrieval_reason}</td>
                  <td>
                    <code>{candidate.relationship}</code>
                  </td>
                  <td>
                    <code
                      className={
                        candidate.retrieval_validity === "CORRECT"
                          ? "validity ok"
                          : candidate.retrieval_validity.startsWith("INCORRECT_BUT")
                            ? "validity notable"
                            : "validity plain"
                      }
                    >
                      {candidate.retrieval_validity}
                    </code>
                  </td>
                </tr>
              ))}
          </tbody>
        </table>

        <p className="goal-note">
          The last two columns are different answers. A candidate can be real while
          the annotation that surfaced it is the wrong explanation —{" "}
          <code>INCORRECT_BUT_CONNECTION_REAL</code> — and an association graph has
          nowhere to record that.
        </p>
      </GoalPanel>

      {/* ---------------------------------------------------------------- */}
      {hasChain && activeCase.goal3 ? (
        <GoalPanel
          number={3}
          question="What is still unknown, and what would settle it?"
          status={goals.goal3.scientific_review}
          statusKind="pending"
        >
          <div className="bridge-block">
            <span className="eyebrow">Validated mechanistic bridge</span>
            <h3>{activeCase.goal3.mechanistic_bridge.display_label}</h3>
            <p className="muted">
              Read from {activeCase.goal3.mechanistic_bridge.derived_from.join(", ")} ·
              evidence depth{" "}
              <code>{activeCase.goal3.mechanistic_bridge.evidence_depth}</code> ·
              full text reviewed:{" "}
              <b>{String(activeCase.goal3.mechanistic_bridge.full_text_review_completed)}</b>
            </p>
          </div>

          <blockquote className="gap-question">
            {activeCase.goal3.knowledge_gap.question}
          </blockquote>

          <div className="hypothesis-pair">
            <article>
              <span>Hypothesis A</span>
              <p>{activeCase.goal3.experiment.hypothesis}</p>
            </article>
            <article>
              <span>Hypothesis B — competing</span>
              <p>{activeCase.goal3.experiment.competing_hypothesis}</p>
            </article>
          </div>

          <dl className="goal-detail">
            <div>
              <dt>Primary readout</dt>
              <dd>{activeCase.goal3.experiment.primary_readout}</dd>
            </div>
            <div>
              <dt>Model system</dt>
              <dd>{activeCase.goal3.experiment.model_system}</dd>
            </div>
            <div>
              <dt>Comparator</dt>
              <dd>{activeCase.goal3.experiment.comparator}</dd>
            </div>
          </dl>

          <div className="outcome-pair">
            <article className="supports">
              <span>Supports the hypothesis if</span>
              <p>{activeCase.goal3.supports_if}</p>
            </article>
            <article className="refutes">
              <span>Weakens or refutes it if</span>
              <p>{activeCase.goal3.refutes_if}</p>
            </article>
          </div>

          <p className="goal-note">
            The refutation clause is enforced in code: a proposal with no refuting
            result, with indistinguishable outcomes, or with an empty primary
            readout raises rather than being returned. The experiment can downgrade
            the relationship, not only confirm it.
          </p>

          {mode === "scientist" ? (
            <details className="goal-details">
              <summary>Stated limitations</summary>
              <ul>
                {activeCase.goal3.evidence_limitations.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </GoalPanel>
      ) : (
        <GoalPanel
          number={3}
          question="What is still unknown, and what would settle it?"
          status="NO_CONNECTION_TO_TEST"
          statusKind="warn"
        >
          <p className="goal-empty">{activeCase.no_connection_statement}</p>
          <p className="goal-note">
            This goal only has an answer when a relationship survives review. It
            did not here, so nothing is proposed.
          </p>
        </GoalPanel>
      )}

      {/* ---------------------------------------------------------------- */}
      {hasChain && activeCase.goal2 ? (
        <GoalPanel
          number={2}
          question="What useful work and capability already exists?"
          status={`${goals.goal2.technical_status} · execution ${goals.goal2.execution_readiness}`}
          statusKind="pending"
        >
          <table className="goal-table">
            <thead>
              <tr>
                <th>Required capability</th>
                <th>Status</th>
                <th>Candidate</th>
                <th>Still to verify</th>
              </tr>
            </thead>
            <tbody>
              {activeCase.goal2.required_capabilities.map((capability) => {
                const work = activeCase.goal2!.existing_work.find(
                  (item) => item.capability === capability.capability,
                );
                const missing = activeCase.goal2!.missing_capabilities.find(
                  (item) => item.capability === capability.capability,
                );
                return (
                  <tr key={capability.id} className={work ? "survived" : "excluded"}>
                    <td>{capability.capability}</td>
                    <td>
                      <code>{capability.status}</code>
                    </td>
                    <td>
                      {work?.candidates[0] ? (
                        <>
                          {work.candidates[0].name}
                          <small>
                            {" "}
                            {work.candidates[0].source} · {work.candidates[0].year}
                          </small>
                        </>
                      ) : (
                        <span className="muted">none found</span>
                      )}
                    </td>
                    <td className="muted">
                      {work?.verification_gap ?? missing?.note ?? "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>

          <div className="goal-counts">
            <Count
              value={activeCase.goal2.existing_work.length}
              label="capabilities with a candidate"
              tone="ok"
            />
            <Count
              value={activeCase.goal2.missing_capabilities.length}
              label="missing or unknown"
              tone="warn"
            />
            <Count
              value={activeCase.goal2.coordination_opportunities.length}
              label="coordination opportunities"
            />
          </div>

          <p className="goal-note">
            <b>{activeCase.goal2.collaborator_status.replace(/_/g, " ")}.</b>{" "}
            Capability is demonstrated by publication only — a team did this once.
            Current availability is unverified and willingness is never inferred.
            Execution topology <code>{activeCase.goal2.execution_topology}</code>:
            no single group is expected to hold every piece.
          </p>
          <p className="goal-note">{activeCase.goal2.asset_status.replace(/_/g, " ")}. {activeCase.goal2.coordination_note}</p>
        </GoalPanel>
      ) : (
        <GoalPanel
          number={2}
          question="What useful work and capability already exists?"
          status="NOT_APPLICABLE"
          statusKind="warn"
        >
          <p className="goal-empty">
            Capability search begins from an experiment. No experiment was
            proposed for this disease, so none was run.
          </p>
        </GoalPanel>
      )}

      <footer className="goals-footer">
        {activeCase.disclaimer.headline}
      </footer>
    </main>
  );
}

function GoalPanel({
  number,
  question,
  status,
  statusKind,
  children,
}: {
  number: number;
  question: string;
  status: string;
  statusKind: "ok" | "warn" | "pending";
  children: React.ReactNode;
}) {
  return (
    <section className="goal-panel">
      <header>
        <span className="goal-number">Goal {number}</span>
        <h2>{question}</h2>
        <span className={`goal-status ${statusKind}`}>{status.replace(/_/g, " ")}</span>
      </header>
      {children}
    </section>
  );
}

function Count({
  value,
  label,
  tone,
}: {
  value: number;
  label: string;
  tone?: "ok" | "warn";
}) {
  return (
    <div className={tone ? `count ${tone}` : "count"}>
      <b>{value}</b>
      <span>{label}</span>
    </div>
  );
}
