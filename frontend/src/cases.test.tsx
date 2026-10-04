import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CasesScreen } from "./cases";
import { loadCases } from "./data";

describe("three worked cases", () => {
  it("the contract validates", () => {
    const result = loadCases();
    expect(result.ok).toBe(true);
  });

  it("carries more than one case, with differing outcomes", () => {
    const result = loadCases();
    if (!result.ok) throw new Error(result.errors.join("; "));
    const outcomes = new Set(result.cases.cases.map((c) => c.outcome));
    // A demo whose cases all end the same way cannot show selectivity.
    expect(result.cases.cases.length).toBeGreaterThan(1);
    expect(outcomes.size).toBeGreaterThan(1);
  });

  it("includes a case where nothing was found", () => {
    const result = loadCases();
    if (!result.ok) throw new Error(result.errors.join("; "));
    const empty = result.cases.cases.find(
      (c) => c.outcome === "NO_DEFENSIBLE_CONNECTION",
    );
    expect(empty).toBeDefined();
    expect(empty?.goal3).toBeNull();
    expect(empty?.no_connection_statement).toBeTruthy();
  });

  it("renders the default case and its candidate table", () => {
    render(<CasesScreen />);
    expect(screen.getByRole("heading", { name: /three worked cases/i })).toBeTruthy();
    expect(screen.getAllByRole("button", { pressed: true }).length).toBe(1);
    expect(screen.getByRole("table")).toBeTruthy();
  });

  it("shows the null case as a result rather than an empty screen", () => {
    render(<CasesScreen />);
    const tabs = screen.getAllByRole("button");
    const nullTab = tabs.find((tab) =>
      within(tab).queryByText(/no connection/i),
    );
    expect(nullTab).toBeDefined();
    fireEvent.click(nullTab!);
    expect(
      screen.getByRole("heading", { name: /no connection was reported/i }),
    ).toBeTruthy();
  });

  it("every case states the disclaimer", () => {
    const result = loadCases();
    if (!result.ok) throw new Error(result.errors.join("; "));
    for (const item of result.cases.cases) {
      expect(item.disclaimer.not_a_medical_recommendation).toBe(true);
      expect(item.disclaimer.headline.toLowerCase()).toContain("expert review");
    }
  });

  it("no case claims collaboration willingness", () => {
    const result = loadCases();
    if (!result.ok) throw new Error(result.errors.join("; "));
    for (const item of result.cases.cases) {
      for (const row of item.goal2?.existing_work ?? []) {
        for (const candidate of row.candidates) {
          expect(candidate.collaboration_willingness).toBe("UNKNOWN");
          expect(candidate.capability_verified).toBe(false);
        }
      }
    }
  });
});
