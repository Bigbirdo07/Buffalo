import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import { loadContracts } from "./data";

afterEach(() => {
  cleanup();
  window.localStorage.clear();
});

function renderRoute(route: string) {
  window.location.hash = route;
  return render(<App />);
}

describe("frozen UI contract", () => {
  it("validates both authoritative demo files", () => {
    const contract = loadContracts();
    expect(contract.ok).toBe(true);
  });

  it("renders the disease start screen", () => {
    renderRoute("/discover");
    expect(screen.getByRole("heading", { name: /Rare diseases should not/i })).toBeVisible();
    expect(screen.getByDisplayValue("SCAR16")).toBeVisible();
  });

  it("keeps rejected and same-spectrum candidates visible", () => {
    renderRoute("/biology");
    expect(screen.getAllByText("Spinocerebellar Ataxia 48").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Peroxisome Biogenesis Disorder 5B").length).toBeGreaterThan(0);
    expect(screen.getByText("Worked demonstration case")).toBeVisible();
  });

  it("renders retrieval separately from evidence and discloses missing metadata", () => {
    renderRoute("/validate");
    expect(screen.getByText("Why the graph found this")).toBeVisible();
    expect(screen.getByText("What the evidence supports")).toBeVisible();
    expect(
      screen.getByText(/found a real connection, but not for the reason/i),
    ).toBeVisible();
    fireEvent.click(screen.getByText("View evidence"));
    expect(screen.getAllByText("Not supplied by frozen contract").length).toBeGreaterThan(0);
  });

  it("renders both support and refutation criteria", () => {
    renderRoute("/question");
    expect(screen.getByText("Would support the hypothesis")).toBeVisible();
    expect(screen.getByText("Would weaken or refute it")).toBeVisible();
    expect(screen.getByText("SCAR16 model")).toBeVisible();
    expect(screen.getByText("Lafora model")).toBeVisible();
  });

  it("renders missing capability and honest no-asset states", () => {
    renderRoute("/existing-work");
    expect(screen.getAllByText("Secondary molecular profiling").length).toBeGreaterThan(0);
    expect(screen.getByText("No verified reusable asset identified")).toBeVisible();
    expect(screen.getByText("No supported overlap flagged")).toBeVisible();
  });

  it("scientist mode reveals canonical values without changing the conclusion", () => {
    renderRoute("/validate");
    fireEvent.click(screen.getByRole("button", { name: "Scientist" }));
    expect(screen.getAllByText("SHARED_DOWNSTREAM_MECHANISM").length).toBeGreaterThan(0);
    expect(screen.getByText(/found a real connection, but not for the reason/i)).toBeVisible();
    expect(screen.getByText("Evidence lineage")).toBeVisible();
  });
});
