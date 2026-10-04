import { useEffect, useState } from "react";
import { CasesScreen } from "./cases";
import { ContractUnavailable, EntityLegend, JourneyProgress, ModeToggle, navigate } from "./components";
import type { PresentationMode } from "./contract";
import { loadCases, loadContracts, selectCase } from "./data";
import {
  ConnectionsScreen,
  DiseaseScreen,
  EvidenceScreen,
  ExperimentScreen,
  ExistingWorkScreen,
  NextStepsScreen,
  UnknownScreen,
} from "./screens";
import { GoalsScreen } from "./goals";
import { SearchScreen } from "./search";

const contract = loadContracts();
const cases = loadCases();
const validRoutes = new Set([
  "/search",
  "/atlas",
  "/disease",
  "/connections",
  "/evidence",
  "/unknown",
  "/experiment",
  "/existing-work",
  "/next-steps",
  "/cases",
]);

/**
 * Split the hash into a route and an optional case id.
 *
 * The case travels in the URL (`#/disease?case=lafora`) so a demo can be deep
 * linked and reloaded without losing which disease is being shown.
 */
function parseHash(): { route: string; caseId: string | null } {
  const raw = window.location.hash.replace(/^#/, "");
  const [path, rest] = raw.split("?");
  const caseId = rest ? new URLSearchParams(rest).get("case") : null;
  return {
    route: validRoutes.has(path) ? path : "/search",
    caseId,
  };
}

export default function App() {
  const initial = parseHash();
  const [route, setRoute] = useState(initial.route);
  const [caseId, setCaseId] = useState<string | null>(() => {
    return initial.caseId ?? window.localStorage.getItem("atlas-case");
  });
  const [mode, setMode] = useState<PresentationMode>(() => {
    return window.localStorage.getItem("atlas-mode") === "scientist" ? "scientist" : "family";
  });

  useEffect(() => {
    if (!window.location.hash) navigate("/search");
    const update = () => {
      const next = parseHash();
      setRoute(next.route);
      // Only a hash that names a case changes the selection, so moving between
      // journey screens keeps the disease the visitor chose.
      if (next.caseId) {
        setCaseId(next.caseId);
        window.localStorage.setItem("atlas-case", next.caseId);
      }
    };
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  function updateMode(next: PresentationMode) {
    setMode(next);
    window.localStorage.setItem("atlas-mode", next);
  }

  if (!contract.ok) return <ContractUnavailable errors={contract.errors} />;
  const { story, goals, parent } = contract;

  // The journey's narrative contract is written for one disease. Other cases
  // supply their own data; `activeCase` is what screens read to know which.
  const activeCase = cases.ok ? selectCase(cases.cases, caseId) : null;
  const props = { story, goals, parent, mode, activeCase };

  const journeyRoute = route !== "/search" && route !== "/cases" && route !== "/atlas";

  return (
    <div className={`app mode-${mode}`}>
      <header className="app-header">
        <button className="brand" onClick={() => navigate("/search")} aria-label="Rare Disease Atlas home">
          <span className="brand-mark">RA</span>
          <span><b>Rare Disease Atlas</b><small>Understand the science. Find the next question.</small></span>
        </button>
        {journeyRoute ? <JourneyProgress active={route} mode={mode} /> : <span className="header-spacer" />}
        <div className="header-actions">
          <button
            type="button"
            className={route === "/cases" ? "cases-link active" : "cases-link"}
            onClick={() => navigate("/cases")}
          >
            {cases.ok ? `${cases.cases.case_count} worked cases` : "Worked cases"}
          </button>
          <ModeToggle mode={mode} onChange={updateMode} />
        </div>
      </header>
      {route === "/search" && <SearchScreen mode={mode} />}
      {route === "/atlas" && <GoalsScreen activeCase={activeCase} goals={goals} mode={mode} />}
      {route === "/cases" && <CasesScreen />}
      {route === "/disease" && <DiseaseScreen {...props} />}
      {route === "/connections" && <ConnectionsScreen {...props} />}
      {route === "/evidence" && <EvidenceScreen {...props} />}
      {route === "/unknown" && <UnknownScreen {...props} />}
      {route === "/experiment" && <ExperimentScreen {...props} />}
      {route === "/existing-work" && <ExistingWorkScreen {...props} />}
      {route === "/next-steps" && <NextStepsScreen {...props} />}
      {journeyRoute && route !== "/disease" && <EntityLegend />}
      <div className="global-disclaimer" role="note">
        Research-support prototype. Not medical advice, diagnosis, or treatment recommendation. Discuss medical decisions with a qualified healthcare professional.
      </div>
    </div>
  );
}
