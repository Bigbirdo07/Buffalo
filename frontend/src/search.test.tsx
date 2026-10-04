import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { loadBrowseIndex, loadCases, searchDiseases } from "./data";
import { SearchScreen } from "./search";

afterEach(cleanup);

describe("corpus search", () => {
  it("the browse index validates and covers the whole corpus", async () => {
    const result = await loadBrowseIndex();
    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.index.diseases).toHaveLength(result.index.disease_count);
    expect(result.index.disease_count).toBeGreaterThan(3000);
  });

  it("marks exactly the analysed diseases, and no others", async () => {
    const result = await loadBrowseIndex();
    const cases = loadCases();
    if (!result.ok || !cases.ok) throw new Error("contracts unavailable");
    const marked = result.index.diseases.filter((item) => item.case_id);
    // The index must agree with the case contract about which diseases have
    // been refined. A disease marked here but absent there would promise depth
    // the app cannot deliver.
    expect(marked).toHaveLength(cases.cases.case_count);
    const caseIds = new Set(cases.cases.cases.map((item) => item.case_id));
    for (const disease of marked) expect(caseIds.has(disease.case_id!)).toBe(true);
  });

  it("finds a disease by name and by gene symbol", async () => {
    const result = await loadBrowseIndex();
    if (!result.ok) return;
    const byName = searchDiseases(result.index, "lafora");
    expect(byName.length).toBeGreaterThan(0);
    expect(byName[0].name.toLowerCase()).toContain("lafora");

    // A visitor is as likely to know the gene as the disease label.
    const byGene = searchDiseases(result.index, "STUB1");
    expect(byGene.length).toBeGreaterThan(0);
    expect(byGene.some((item) => item.genes.includes("STUB1"))).toBe(true);
  });

  it("ignores queries too short to discriminate", async () => {
    const result = await loadBrowseIndex();
    if (!result.ok) return;
    expect(searchDiseases(result.index, "a")).toHaveLength(0);
  });

  it("renders the search box and the worked-case examples", async () => {
    render(<SearchScreen mode="family" />);
    expect(screen.getByRole("searchbox", { name: /disease name or gene/i })).toBeTruthy();
    await waitFor(() => {
      expect(screen.getByText(/diseases have been through full evidence refinement/i)).toBeTruthy();
    });
  });

  it("shows a disease with no deep analysis, and says so", async () => {
    render(<SearchScreen mode="family" />);
    const box = await screen.findByRole("searchbox", { name: /disease name or gene/i });
    await waitFor(() => expect((box as HTMLInputElement).disabled).toBe(false));

    // A disease that is in the corpus but is not one of the worked cases.
    fireEvent.change(box, { target: { value: "Friedreich Ataxia" } });
    const results = await screen.findByText(/match(es)? for/i);
    const list = results.parentElement!;
    fireEvent.click(within(list).getAllByRole("button")[0]);

    // The limitation is the point of this view, not a footnote.
    expect(await screen.findByText(/What this is, and what it is not/i)).toBeTruthy();
    expect(screen.getByText(/not a validated relationship/i)).toBeTruthy();
    expect(screen.getByText(/is not one of them/i)).toBeTruthy();
  });

  it("says plainly when the corpus holds no match", async () => {
    render(<SearchScreen mode="family" />);
    const box = await screen.findByRole("searchbox", { name: /disease name or gene/i });
    await waitFor(() => expect((box as HTMLInputElement).disabled).toBe(false));
    fireEvent.change(box, { target: { value: "zzzzzznotadisease" } });
    expect(
      await screen.findByText(/No disease in the corpus matches/i),
    ).toBeTruthy();
  });

  it("never implies a validated relationship for an unrefined disease", async () => {
    const result = await loadBrowseIndex();
    if (!result.ok) return;
    const unrefined = result.index.diseases.find(
      (item) => !item.case_id && item.neighbours.length > 0,
    )!;
    // Neighbour records carry shared features and axis counts only. If a
    // relationship class or evidence id ever appears here, the index has
    // started asserting something retrieval cannot support.
    for (const neighbour of unrefined.neighbours) {
      expect(Object.keys(neighbour).sort()).toEqual(
        ["axes", "features", "information", "name"],
      );
    }
  });
});
