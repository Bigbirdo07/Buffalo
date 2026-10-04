import { useEffect, useMemo, useState } from "react";

import { navigate } from "./components";
import type { BrowseDisease, BrowseIndex, PresentationMode } from "./contract";
import { loadBrowseIndex, searchDiseases } from "./data";

/**
 * Clean, uncluttered Search Screen featuring the 3 core working cases:
 * 1. SCAR16
 * 2. Lafora Disease
 * 3. Ankylosing Spondylitis
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
    () => (index ? index.diseases.filter((item) => item.case_id).slice(0, 3) : []),
    [index],
  );

  const featuredCases = [
    {
      caseId: "scar16",
      name: "Autosomal Recessive Spinocerebellar Ataxia 16 (SCAR16)",
      cause: "Biallelic STUB1 variants affecting CHIP co-chaperone & E3 ligase activity.",
      affected: "Movement, gait balance, cerebellum & pyramidal tract.",
      tag: "Neurological · Corrected Chain",
    },
    {
      caseId: "lafora",
      name: "Lafora Disease",
      cause: "EPM2A or NHLRC1 variants causing polyglucosan inclusion bodies.",
      affected: "Central nervous system, motor control & severe epilepsy.",
      tag: "Neurological · Reverse Cluster Recovery",
    },
    {
      caseId: "ankylosing",
      name: "Ankylosing Spondylitis",
      cause: "HLA-B27 and ERAP1 antigen processing & immune pathway disruption.",
      affected: "Spine, joints, eyes (uveitis) & systemic immune response.",
      tag: "Immunology · 5 of 8 Leads Rejected",
    },
  ];

  function runSearch(text: string) {
    setQuery(text);
    setSubmitted(text);
    setSelected(null);
    setEmptyHint(text.trim().length === 0);
  }

  const searching = submitted.trim().length > 0;

  return (
    <section className={searching ? "search-screen searching" : "search-screen"}>
      {/* Hero Search */}
      <div className="hero-clean">
        <span className="eyebrow">Rare Disease Research Navigator</span>
        <h1>Search a rare disease or gene</h1>
        <p>
          Select one of our 3 working cases or search a disease or gene to trace its biological causes, body system impacts, research connections, open questions, and existing work.
        </p>

        <form
          className="search-form"
          onSubmit={(event) => {
            event.preventDefault();
            runSearch(query);
          }}
        >
          <label htmlFor="disease-search">Disease name or gene symbol</label>
          <div className="search-input-box">
            <input
              id="disease-search"
              type="search"
              autoComplete="off"
              placeholder={index ? "Search a disease (e.g. SCAR16, Lafora, Ankylosing) or gene (STUB1)" : "Loading corpus…"}
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
            <span>Explore a demo story</span>
            {examples.map((item) => (
              <button key={item.id} type="button" onClick={() => runSearch(item.name)}>
                {item.name}
              </button>
            ))}
          </div>
        ) : null}

        <p className="hero-note">
          <span className="status-dot-green" />
          {index
            ? `${index.analysed_case_count} diseases have been through full evidence refinement. Every other disease returns candidate neighbours only.`
            : "Loading the disease corpus…"}
        </p>
      </div>

      {/* The 3 Featured Working Cases */}
      {!searching && (
        <section className="three-cases-section">
          <h2>Our 3 Working Demonstration Cases</h2>
          <div className="three-cases-grid">
            {featuredCases.map((item) => (
              <article key={item.caseId} className="case-selection-card">
                <span className="case-tag-pill">{item.tag}</span>
                <h3>{item.name}</h3>
                <p><strong>Cause:</strong> {item.cause}</p>
                <p><strong>Affected Systems:</strong> {item.affected}</p>
                <button
                  type="button"
                  className="primary-button case-select-btn"
                  onClick={() => navigate(`/disease?case=${item.caseId}`)}
                >
                  Explore {item.caseId.toUpperCase()} Journey →
                </button>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Search Results Display */}
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
              if (disease.case_id) navigate(`/disease?case=${disease.case_id}`);
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
          Candidate neighbours record <strong>shared annotated features</strong> — not a validated relationship.
        </p>
        <p>
          Evidence refinement and capability mapping have been run for five diseases. <strong>{disease.name} is not one of them</strong>,
          so no relationship is claimed here and none of these candidates has been checked against the literature.
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
