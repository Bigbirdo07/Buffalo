import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";
import { loadCases } from "./data";

afterEach(cleanup);

function renderAtlas(caseId: string) {
  window.location.hash = `/atlas?case=${caseId}`;
  return render(<App />);
}

describe("goal-structured disease view", () => {
  it("names all three goals as questions", () => {
    renderAtlas("scar16");
    expect(screen.getByText(/Who genuinely shares this disease's biology/i)).toBeTruthy();
    expect(screen.getByText(/What is still unknown/i)).toBeTruthy();
    expect(screen.getByText(/What useful work and capability already exists/i)).toBeTruthy();
  });

  it("shows what was rejected, not only what survived", () => {
    // A goal view that listed only successes would hide the system's main
    // claim: that most of what retrieval finds does not survive.
    renderAtlas("scar16");
    expect(screen.getByText(/excluded — same entity/i)).toBeTruthy();
    expect(screen.getByText(/rejected on evidence/i)).toBeTruthy();
    expect(screen.getByText(/survived/i)).toBeTruthy();
  });

  it("separates why a pair was retrieved from what the evidence says", () => {
    renderAtlas("scar16");
    expect(screen.getByText(/Retrieved because/i)).toBeTruthy();
    expect(screen.getByText(/Evidence says/i)).toBeTruthy();
    expect(screen.getByText(/Was that the reason\?/i)).toBeTruthy();
  });

  it("marks expert review as pending rather than implying approval", () => {
    renderAtlas("scar16");
    expect(screen.getByText(/awaiting expert signoff/i)).toBeTruthy();
  });

  it("shows both outcome branches, including refutation", () => {
    renderAtlas("scar16");
    expect(screen.getByText(/Supports the hypothesis if/i)).toBeTruthy();
    expect(screen.getByText(/Weakens or refutes it if/i)).toBeTruthy();
    expect(screen.getByText(/Hypothesis B — competing/i)).toBeTruthy();
  });

  it("never claims a verified collaborator", () => {
    renderAtlas("scar16");
    expect(screen.getByText(/no verified collaborator identified/i)).toBeTruthy();
  });

  it("renders every case, and says why the empty ones are empty", () => {
    const result = loadCases();
    if (!result.ok) throw new Error("cases unavailable");
    for (const item of result.cases.cases) {
      cleanup();
      expect(() => renderAtlas(item.case_id)).not.toThrow();
      if (item.outcome === "NO_DEFENSIBLE_CONNECTION") {
        // Goals 2 and 3 have no answer here, and must say so rather than
        // render an empty panel.
        expect(screen.getByText(/no connection to test/i)).toBeTruthy();
        expect(screen.getByText(/not applicable/i)).toBeTruthy();
      }
    }
  });
});
