import { useEffect, useMemo, useState } from "react";

import { navigate } from "./components";
import type { BrowseDisease, BrowseIndex, PresentationMode } from "./contract";
import { loadBrowseIndex, searchDiseases } from "./data";

/**
 * The entry point: search the whole corpus, not a shortlist.
 *
 * Five diseases have been through evidence refinement. Every other disease in
 * the corpus still returns something real -- its causal genes and the
 * neighbours retrieval actually finds -- followed by a plain statement that no
 * relationship has been validated for it.
 *
 * That boundary is the point of the screen. A search box that quietly returns
 * nothing for 3,284 of 3,289 diseases would be a worse lie than having no
 * search box at all.
 */
export function SearchScreen({ mode }: { mode: PresentationMode }) {
  const [index, setIndex] = useState<BrowseIndex | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [submitted, setSubmitted] = useState("");
  const [selected, setSelected] = useState<BrowseDisease | null>(null);
  const [emptyHint, setEmptyHint] = useState(false);

  useEffect(() => {
    let active = true;
    loadBrowseIndex().then((result) => {
      if (!active) return;
      if (result.ok) setIndex(result.index);
      else setLoadError(result.errors[0] ?? "index unavailable");
    });
    return () => {
      active = false;
    };
  }, []);

  const results = useMemo(
    () => (index && submitted ? searchDiseases(index, submitted) : []),
    [index, submitted],
  );

  const examples = useMemo(
    () => (index ? index.diseases.filter((item) => item.case_id).slice(0, 5) : []),
    [index],
  );

  function runSearch(text: string) {
    setQuery(text);
    setSubmitted(text);
    setSelected(null);
    setEmptyHint(text.trim().length === 0);
  }

  const searching = submitted.trim().length > 0;

  return (
    <section className={searching ? "search-screen searching" : "search-screen"}>
      <div className="hero">
        <div className="hero-copy">
          <h1>Which diseases share our biology?</h1>
          <p>
            Search {index ? index.disease_count.toLocaleString() : "3,289"} curated
            rare disease mechanisms. The atlas shows why a connection was found,
            whether the evidence supports it, what is still unknown, and who
            already has the capability to test it.
          </p>

          <form
            className="search-form"
            onSubmit={(event) => {
              event.preventDefault();
              runSearch(query);
            }}
          >
            <label htmlFor="disease-search">Disease name or gene symbol</label>
            <div>
              <input
                id="disease-search"
                type="search"
                autoComplete="off"
                placeholder={index ? "e.g. Lafora Disease, or STUB1" : "Loading corpus…"}
                value={query}
                disabled={!index}
                onChange={(event) => {
                  setQuery(event.target.value);
                  setSubmitted(event.target.value);
                  setSelected(null);
                  setEmptyHint(false);
                }}
              />
              <button type="submit" disabled={!index}>
                Search
              </button>
            </div>
            {loadError ? <p className="form-message">{loadError}</p> : null}
            {emptyHint && !loadError ? (
              <p className="form-message">
                Type a disease name or a gene symbol to search the corpus.
              </p>
            ) : null}
          </form>

          {examples.length > 0 && !submitted ? (
            <div className="examples">
              <span>Worked cases</span>
              {examples.map((item) => (
                <button key={item.id} type="button" onClick={() => runSearch(item.name)}>
                  {item.name}
                </button>
              ))}
            </div>
          ) : null}

          <p className="hero-note">
            <span />
            {index
              ? `${index.analysed_case_count} diseases have been through full evidence refinement. Every other disease returns candidate neighbours only.`
              : "Loading the disease corpus…"}
          </p>
        </div>

        <aside className="hero-figure" hidden={searching}>
          <span className="figure-index">What a result contains</span>
          <div>
            <b>1</b>
            <span>
              <strong>Why it was found</strong>
              <small>The annotation that surfaced the pair</small>
            </span>
          </div>
          <div>
            <b>2</b>
            <span>
              <strong>What the evidence says</strong>
              <small>Which may be a different answer</small>
            </span>
          </div>
          <div>
            <b>3</b>
            <span>
              <strong>What is still unknown</strong>
              <small>And the experiment that would settle it</small>
            </span>
          </div>
          <div>
            <b>4</b>
            <span>
              <strong>Who could test it</strong>
              <small>Capabilities and assets that already exist</small>
            </span>
          </div>
        </aside>
      </div>

      {submitted && index ? (
        selected ? (
          <DiseaseBrief
            disease={selected}
            mode={mode}
            onBack={() => setSelected(null)}
          />
        ) : (
          <ResultList
            query={submitted}
            results={results}
            onSelect={(disease) => {
              if (disease.case_id) navigate(`/atlas?case=${disease.case_id}`);
              else setSelected(disease);
            }}
          />
        )
      ) : null}
    </section>
  );
}

function ResultList({
  query,
  results,
  onSelect,
}: {
  query: string;
  results: BrowseDisease[];
  onSelect: (disease: BrowseDisease) => void;
}) {
  if (query.trim().length < 2) return null;
  if (results.length === 0) {
    return (
      <div className="search-results">
        <p className="results-count">
          No disease in the corpus matches “{query}”. The atlas covers curated
          rare disease mechanisms, so many common conditions are absent.
        </p>
      </div>
    );
  }
  return (
    <div className="search-results">
      <p className="results-count">
        {results.length} match{results.length === 1 ? "" : "es"} for “{query}”
      </p>
      <ul>
        {results.map((disease) => (
          <li key={disease.id}>
            <button type="button" onClick={() => onSelect(disease)}>
              <span className="result-name">
                {disease.name}
                {disease.case_id ? (
                  <em className="result-badge analysed">Full analysis</em>
                ) : (
                  <em className="result-badge shallow">Candidates only</em>
                )}
              </span>
              <span className="result-meta">
                {disease.genes.length > 0
                  ? disease.genes.slice(0, 4).join(" · ")
                  : "no causal gene recorded"}
                {" — "}
                {disease.neighbours.length} candidate neighbour
                {disease.neighbours.length === 1 ? "" : "s"}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * What a visitor sees for a disease that has not been refined.
 *
 * It shows real retrieval output, then states exactly what that output is not.
 * The limitation panel is as important as the results: this is where the
 * interface declines to imply a finding it has not earned.
 */
function DiseaseBrief({
  disease,
  mode,
  onBack,
}: {
  disease: BrowseDisease;
  mode: PresentationMode;
  onBack: () => void;
}) {
  return (
    <article className="disease-brief">
      <button type="button" className="text-button" onClick={onBack}>
        ← Back to results
      </button>

      <h2>{disease.name}</h2>
      <dl className="brief-stats">
        <div>
          <dt>Causal genes</dt>
          <dd>{disease.genes.length > 0 ? disease.genes.join(", ") : "none recorded"}</dd>
        </div>
        <div>
          <dt>Phenotypes</dt>
          <dd>{disease.phenotype_count}</dd>
        </div>
      </dl>

      <h3>Candidate neighbours</h3>
      {disease.neighbours.length === 0 ? (
        <p className="muted">
          Retrieval returns no candidate neighbours for this disease. Its
          annotated features are not shared, at a usable level of specificity,
          with any other disease in the corpus.
        </p>
      ) : (
        <table className="brief-table">
          <thead>
            <tr>
              <th>Disease</th>
              <th>Shared features</th>
              <th>Axes</th>
            </tr>
          </thead>
          <tbody>
            {disease.neighbours.map((neighbour) => (
              <tr key={neighbour.name}>
                <td>{neighbour.name}</td>
                <td className="muted">{neighbour.features.join(", ") || "—"}</td>
                <td>{neighbour.axes}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <aside className="depth-limit">
        <h4>What this is, and what it is not</h4>
        <p>
          Candidate neighbours are computed for every disease in the corpus. They
          record <strong>shared annotated features</strong> — not a validated
          relationship.
        </p>
        <p>
          Evidence refinement, the knowledge gap and capability mapping have been
          run for five diseases. <strong>{disease.name} is not one of them</strong>,
          so no relationship is claimed here and none of these candidates has been
          checked against the literature.
        </p>
        {mode === "scientist" ? (
          <p className="muted">
            Retrieval is the hypothesis-generating step. On the analysed cases it
            is wrong about <em>why</em> a pair matters more often than it is right,
            which is why nothing above is presented as a finding.
          </p>
        ) : null}
      </aside>
    </article>
  );
}
