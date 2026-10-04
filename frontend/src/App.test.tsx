import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import App from "./App";
import { loadContracts } from "./data";

afterEach(() => { cleanup(); window.localStorage.clear(); });

function renderRoute(route: string) { window.location.hash = route; return render(<App />); }

describe("parent-first frozen demo", () => {
  it("validates scientific and parent presentation contracts", () => { expect(loadContracts().ok).toBe(true); });

  it("explains the selected disease before exposing the graph", () => {
    renderRoute("/disease");
    expect(screen.getByRole("heading", { name: "SCAR16" })).toBeVisible();
    expect(screen.getByText("What causes it?")).toBeVisible();
    expect(screen.getByText("Movement and balance")).toBeVisible();
    // The picker used to be cosmetic: every choice but one produced an apology.
    // It now lists the diseases that were actually analysed, exactly one is
    // selected, and the rest are reachable.
    const picker = screen.getByRole("region", { name: /worked cases/i });
    const choices = within(picker).getAllByRole("button");
    expect(choices.length).toBeGreaterThan(1);
    expect(choices.filter((button) => button.getAttribute("aria-pressed") === "true")).toHaveLength(1);
  });

  it("offers the whole corpus, not only the worked cases", () => {
    renderRoute("/disease");
    expect(screen.getByRole("button", { name: /search all .*diseases/i })).toBeVisible();
  });

  it("shows useful, same-spectrum, downgraded, and rejected connections", () => {
    renderRoute("/connections");
    expect(screen.getByRole("heading", { name: "Lafora Disease" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Spinocerebellar Ataxia 48" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Peroxisome Biogenesis Disorder 5B" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "Autosomal Dominant Cerebellar Ataxia Type I" })).toBeVisible();
    expect(screen.getByText("A negative result is useful")).toBeVisible();
  });

  it("keeps the biology optional and labels every revealed node", () => {
    renderRoute("/connections");
    fireEvent.click(screen.getByRole("button", { name: "See the biology" }));
    expect(screen.getByRole("heading", { name: "STUB1" })).toBeVisible();
    expect(screen.getByRole("heading", { name: "CHIP" })).toBeVisible();
    expect(screen.getByText("Provides instructions for making the CHIP protein.")).toBeVisible();
  });

  it("explains how evidence changed the original connection", () => {
    renderRoute("/evidence");
    expect(screen.getByText("What first connected them")).toBeVisible();
    expect(screen.getByText("What we checked")).toBeVisible();
    expect(screen.getByText("What appears more important")).toBeVisible();
    expect(screen.getByText(/real connection, but not for the reason/i)).toBeVisible();
    expect(screen.getAllByText("Promising but unconfirmed").length).toBeGreaterThan(0);
  });

  it("states the unknown and its present-day limitation", () => {
    renderRoute("/unknown");
    expect(screen.getByText(/whether SCAR16 and Lafora Disease produce the same type/i)).toBeVisible();
    expect(screen.getByText("What does this mean for my child today?")).toBeVisible();
    expect(screen.getByText(/does not identify a treatment/i)).toBeVisible();
  });

  it("shows a test that can support or weaken the hypothesis", () => {
    renderRoute("/experiment");
    expect(screen.getByText("SCAR16 cells")).toBeVisible();
    expect(screen.getByText("Lafora cells")).toBeVisible();
    expect(screen.getByText("If the responses look similar")).toBeVisible();
    expect(screen.getByText("If the responses look different")).toBeVisible();
  });

  it("organizes existing work around capability and preserves honest empty states", () => {
    renderRoute("/existing-work");
    expect(screen.getAllByText("Secondary molecular profiling").length).toBeGreaterThan(0);
    expect(screen.getByText("No verified reusable asset identified")).toBeVisible();
    expect(screen.getByText("No verified geographic map in this contract")).toBeVisible();
  });

  it("creates a printable research discussion summary", () => {
    renderRoute("/next-steps");
    expect(screen.getByText("Research discussion summary")).toBeVisible();
    expect(screen.getByRole("button", { name: /Print/i })).toBeVisible();
    expect(screen.getByText(/not a treatment plan/i)).toBeVisible();
  });

  it("scientist mode reveals canonical values without changing the conclusion", () => {
    renderRoute("/evidence");
    fireEvent.click(screen.getByRole("button", { name: "Scientist" }));
    expect(screen.getAllByText("SHARED_DOWNSTREAM_MECHANISM").length).toBeGreaterThan(0);
    expect(screen.getByText(/real connection, but not for the reason/i)).toBeVisible();
    expect(screen.getByLabelText("Evidence lineage")).toBeVisible();
  });
});
