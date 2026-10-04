import { useEffect, useState } from "react";
import { ContractUnavailable, GoalProgress, ModeToggle, navigate } from "./components";
import type { PresentationMode } from "./contract";
import { CasesScreen } from "./cases";
import { loadContracts } from "./data";
import {
  BiologyScreen,
  ExistingWorkScreen,
  QuestionScreen,
  SearchScreen,
  ValidateScreen,
} from "./screens";

const contract = loadContracts();
const validRoutes = new Set([
  "/discover",
  "/biology",
  "/validate",
  "/question",
  "/existing-work",
  "/cases",
]);

function routeFromHash() {
  const route = window.location.hash.replace(/^#/, "") || "/discover";
  return validRoutes.has(route) ? route : "/discover";
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash);
  const [mode, setMode] = useState<PresentationMode>(() => {
    return window.localStorage.getItem("atlas-mode") === "scientist" ? "scientist" : "family";
  });

  useEffect(() => {
    if (!window.location.hash) navigate("/discover");
    const update = () => setRoute(routeFromHash());
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);

  function updateMode(next: PresentationMode) {
    setMode(next);
    window.localStorage.setItem("atlas-mode", next);
  }

  if (!contract.ok) return <ContractUnavailable errors={contract.errors} />;
  const { story, goals } = contract;
  const props = { story, goals, mode };

  return (
    <div className={`app mode-${mode}`}>
      <header className="app-header">
        <button className="brand" onClick={() => navigate("/discover")} aria-label="Rare Disease Atlas home">
          <span className="brand-mark">RA</span>
          <span><b>Rare Disease Atlas</b><small>Evidence refinement → research action</small></span>
        </button>
        <GoalProgress active={route} />
        <button
          type="button"
          className={route === "/cases" ? "cases-link active" : "cases-link"}
          onClick={() => navigate("/cases")}
        >
          3 worked cases
        </button>
        <ModeToggle mode={mode} onChange={updateMode} />
      </header>
      {route === "/discover" && <SearchScreen {...props} />}
      {route === "/biology" && <BiologyScreen {...props} />}
      {route === "/validate" && <ValidateScreen {...props} />}
      {route === "/question" && <QuestionScreen {...props} />}
      {route === "/existing-work" && <ExistingWorkScreen {...props} />}
      {route === "/cases" && <CasesScreen />}
      <div className="global-disclaimer" role="note">
        Research-support prototype · Not a medical recommendation · Expert review pending
      </div>
    </div>
  );
}
