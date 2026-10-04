import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import App from "./App";

afterEach(cleanup);

function trace(caseId = "scar16") {
  window.location.hash = `/trace?case=${caseId}`;
  return render(<App />);
}

function advance(times: number) {
  for (let i = 0; i < times; i += 1) {
    // SVG elements expose className as an SVGAnimatedString, so match on the
    // attribute rather than the property.
    const next = screen
      .getAllByRole("button")
      .find((button) => button.getAttribute("class")?.includes("primary-button"));
    if (next) fireEvent.click(next);
  }
}

describe("lineage walkthrough", () => {
  it("starts with one node, not a graph", () => {
    trace();
    // Progressive disclosure is the whole point: a complete graph on arrival
    // teaches nobody anything.
    expect(screen.getAllByText("SCAR16").length).toBeGreaterThan(0);
    expect(screen.queryByText("CHIP")).toBeNull();
    expect(screen.queryByText("Lafora Disease")).toBeNull();
  });

  it("grows the gene, then the protein, as the viewer asks", () => {
    trace();
    expect(screen.getByRole("button", { name: /follow the biology/i })).toBeTruthy();
    advance(1);
    expect(screen.getAllByText("STUB1").length).toBeGreaterThan(0);
    advance(1);
    expect(screen.getAllByText("CHIP").length).toBeGreaterThan(0);
  });

  it("every node states its label, type and meaning without hovering", () => {
    trace();
    advance(1);
    expect(screen.getAllByText("STUB1").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/^Gene$/).length).toBeGreaterThan(0);
    expect(screen.getByText(/instructions for making the CHIP protein/i)).toBeTruthy();
  });

  it("keeps the original reason visible after the evidence refines it", () => {
    trace();
    advance(6); // through to the refined stage
    expect(screen.getByText(/not for the reason we expected/i)).toBeTruthy();
    // The broad annotation that surfaced the pair is dimmed, never erased.
    const superseded = document.querySelector(".edge.retrieval.superseded");
    expect(superseded).not.toBeNull();
  });

  it("ends the path at an explicit open question", () => {
    trace();
    advance(7);
    // It appears on the node and in the story panel, which is intended.
    expect(screen.getAllByText(/What researchers still do not know/i).length).toBeGreaterThan(1);
    expect(screen.getByText(/Open question — the path ends here/i)).toBeTruthy();
  });

  it("gives refutation equal weight to support", () => {
    trace();
    advance(8);
    expect(screen.getByText(/Similar response/i)).toBeTruthy();
    expect(screen.getByText(/Different response/i)).toBeTruthy();
  });

  it("says why no map is drawn rather than inventing pins", () => {
    trace();
    advance(9);
    expect(screen.getByText(/no verified current\s+locations/i)).toBeTruthy();
  });

  it("narrates each stage so the demo explains itself", () => {
    trace();
    expect(screen.getByText(/We begin with the disease/i)).toBeTruthy();
    advance(1);
    expect(screen.getByText(/trace the genetic foundation/i)).toBeTruthy();
  });

  it("offers the goal view for a case with no written path", () => {
    trace("scar20");
    expect(screen.getByRole("button", { name: /see the full analysis/i })).toBeTruthy();
  });
});
