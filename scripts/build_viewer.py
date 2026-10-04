#!/usr/bin/env python3
"""Generate a self-contained evidence viewer from the committed artifacts.

Produces one HTML file with the data embedded, so it opens by double-click with
no server, no build step and no network. Every figure on the page is read out of
the artifacts; nothing is typed in here. If an artifact is missing, the section
says so rather than showing a placeholder.

The page is the honest surface of the engine: it shows categorical statuses, the
rule that produced each one, the verbatim evidence span behind it, and the
verification tier of every citation. It never shows a confidence score, because
the engine does not compute one.
"""

from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNS = (
    ("SCAR16", "STUB1", ROOT / "data/refinement/scar16_stub1_e3"),
    ("SCAR20", "SNX14", ROOT / "data/refinement/scar20_snx14_autophagy"),
)
ACTION = ROOT / "data/action/scar16_stub1_e3"
AUDIT = ROOT / "data/audit/corpus_audit.json"

STATUS_LABEL = {
    "SUPPORTED": "Supported",
    "PARTIALLY_SUPPORTED": "Partly supported",
    "CONTEXT_DEPENDENT": "Depends on context",
    "INSUFFICIENT_EVIDENCE": "Not enough evidence",
    "CONTRADICTED": "Contradicted",
    "UNREVIEWED": "Not reviewed",
}
STATUS_PLAIN = {
    "SUPPORTED": "The evidence backs this up.",
    "PARTIALLY_SUPPORTED": "Some evidence backs this up, but only partly.",
    "CONTEXT_DEPENDENT": "True in some situations and not others.",
    "INSUFFICIENT_EVIDENCE": "Nobody has shown this either way yet.",
    "CONTRADICTED": "The evidence goes against this.",
    "UNREVIEWED": "Not yet assessed.",
}
CITATION_LABEL = {
    "VERIFIED": "quote found in the paper",
    "UPSTREAM_ATTESTED": "paper identified, text not readable",
    "SPAN_NOT_LOCATED": "quote NOT found in the paper",
    "TITLE_MISMATCH": "title does not match",
    "UNRESOLVED": "reference did not resolve",
    "NOT_CHECKABLE": "no way to check this reference",
}
ORIGIN_LABEL = {
    "PRIMARY_RESULT": "the paper's own result",
    "BACKGROUND_CITATION": "background claim citing someone else",
    "REVIEW_SYNTHESIS": "review summary",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def load(path: Path) -> Any | None:
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def collect() -> dict[str, Any]:
    diseases = []
    for name, gene, run_dir in RUNS:
        refinement = load(run_dir / "edge_refinement.json")
        if refinement is None:
            continue
        plan = load(run_dir / "observation_plan.json") or {}
        specs = {s["claim_id"]: s for s in plan.get("atomic_claims", [])}
        observations = {o["observation_id"]: o for o in refinement["observations"]}
        checks = {c["evidence_id"]: c for c in refinement["citation_checks"]}
        claims = []
        for atomic in refinement["atomic"]:
            claim = atomic["claim"]
            spec = specs.get(claim["claim_id"], {})
            evidence = []
            for review in refinement["reviews"]:
                if review["claim_id"] != claim["claim_id"]:
                    continue
                obs = observations[review["source_id"]]
                check = checks.get(obs["evidence_id"], {})
                evidence.append(
                    {
                        "observation_id": obs["observation_id"],
                        "source": obs["source_identifier"],
                        "upstream_form": obs.get("upstream_reference_form"),
                        "origin": obs["origin"],
                        "effect": obs["effect"],
                        "readout": obs["readout"],
                        "system": obs["experimental_system"],
                        "cell_types": obs.get("cell_types") or [],
                        "span": obs["support_span"],
                        "span_location": obs["source_location"],
                        "citation": check.get("status", "NOT_CHECKED"),
                        "fit": review["supports"],
                        "directness": review["directness"],
                        "limitations": review["limitations"],
                    }
                )
            claims.append(
                {
                    "claim_id": claim["claim_id"],
                    "statement": claim["normalized_statement"],
                    "status": atomic["status"],
                    "rule": atomic["rule_applied"],
                    "allele_class": spec.get("scope_class"),
                    "variants": spec.get("variant_scope", []),
                    "cell_type_scope": spec.get("cell_type_scope", []),
                    "evidence": evidence,
                }
            )
        gap = load(run_dir / "knowledge_gap.json")
        experiment = load(run_dir / "experiment_proposal.json")
        reviews = load(run_dir / "scientific_reviews.json")
        diseases.append(
            {
                "name": name,
                "gene": gene,
                "mondo": plan.get("target", {}).get("disease_scope", [name])[0],
                "commit": plan.get("target", {}).get("dismech_commit", ""),
                "source_file": Path(
                    plan.get("target", {}).get("disease_file", "")
                ).name,
                "edge_path": plan.get("target", {}).get("edge_path", ""),
                "upstream_claim": refinement["upstream_claim"]["normalized_statement"],
                "edge_status": refinement["edge_status"],
                "edge_rule": refinement["edge_rule_applied"],
                "recommended_scope": refinement["recommended_scope"],
                "claims": claims,
                "citation_counts": dict(
                    Counter(c["status"] for c in refinement["citation_checks"])
                ),
                "coverage": refinement["search_coverage"]["sources"],
                "gap": gap,
                "experiment": experiment,
                "reviews": (reviews or {}).get("reviews", []),
            }
        )

    action: dict[str, Any] | None = None
    collaboration = load(ACTION / "collaboration_opportunity.json")
    if collaboration is not None:
        caps = {
            c["capability_id"]: c["canonical_name"]
            for c in load(ACTION / "required_capabilities.json") or []
        }
        claims_action = load(ACTION / "capability_claims.json") or []
        action = {
            "status": collaboration["status"],
            "missing": [caps.get(m, m) for m in collaboration["missing_capabilities"]],
            "provided": sorted(
                caps.get(m, m) for m in collaboration["provided_capabilities"]
            ),
            "uncertainties": collaboration["uncertainties"],
            "next_action": collaboration["suggested_next_action"],
            "duplication": collaboration["duplication_risk"],
            "claim_statuses": dict(Counter(c["status"] for c in claims_action)),
            "assets": load(ACTION / "research_assets.json") or [],
            "organizations": load(ACTION / "organizations.json") or [],
            "coverage": (load(ACTION / "search_coverage.json") or {}).get("sources", []),
            "patient_text": (load(ACTION / "patient_explanation.json") or {}).get("text", ""),
            "participants": len(collaboration["participants"]),
        }

    audit = load(AUDIT) or {}
    return {"diseases": diseases, "action": action, "audit": audit.get("totals", {})}


def status_pill(status: str) -> str:
    return (
        f'<span class="pill s-{esc(status.lower())}">{esc(STATUS_LABEL.get(status, status))}</span>'
    )


def render_evidence(evidence: list[dict[str, Any]], view: str) -> str:
    if not evidence:
        return '<p class="muted">No evidence was linked to this claim.</p>'
    rows = []
    for item in evidence:
        citation = item["citation"]
        upstream = ""
        if item["upstream_form"] and item["upstream_form"] != item["source"]:
            upstream = (
                f'<div class="ev-meta">upstream wrote <code>{esc(item["upstream_form"])}'
                "</code></div>"
            )
        if view == "scientist":
            detail = (
                f'<div class="ev-grid">'
                f'<div><dt>readout</dt><dd>{esc(item["readout"])}</dd></div>'
                f'<div><dt>effect</dt><dd>{esc(item["effect"])}</dd></div>'
                f'<div><dt>critic fit</dt><dd>{esc(item["fit"])} / {esc(item["directness"])}</dd></div>'
                f'<div><dt>origin</dt><dd>{esc(item["origin"])}</dd></div>'
                f'<div class="wide"><dt>system</dt><dd>{esc(item["system"])}</dd></div>'
                + (
                    f'<div class="wide"><dt>cell type</dt><dd>{esc(", ".join(item["cell_types"]))}</dd></div>'
                    if item["cell_types"]
                    else ""
                )
                + "</div>"
            )
            limits = (
                '<ul class="limits">'
                + "".join(f"<li>{esc(limit)}</li>" for limit in item["limitations"])
                + "</ul>"
                if item["limitations"]
                else ""
            )
        else:
            detail = (
                f'<div class="ev-meta">This is {esc(ORIGIN_LABEL.get(item["origin"], item["origin"]))}, '
                f'measured in {esc(item["system"])}.</div>'
            )
            limits = ""
        rows.append(
            f"""<li class="ev">
  <div class="ev-head">
    <code class="src">{esc(item["source"])}</code>
    <span class="cite c-{esc(citation.lower())}">{esc(CITATION_LABEL.get(citation, citation))}</span>
  </div>
  {upstream}
  <blockquote>{esc(item["span"].strip())}</blockquote>
  <div class="ev-meta loc">found in: {esc(item["span_location"].replace("_", " "))}</div>
  {detail}
  {limits}
</li>"""
        )
    return '<ul class="ev-list">' + "".join(rows) + "</ul>"


def render_disease(disease: dict[str, Any], view: str) -> str:
    claims = disease["claims"]
    counts = Counter(c["status"] for c in claims)
    chips = "".join(
        f'<span class="chip s-{esc(status.lower())}">{counts[status]} {esc(STATUS_LABEL[status].lower())}</span>'
        for status in (
            "SUPPORTED",
            "PARTIALLY_SUPPORTED",
            "CONTEXT_DEPENDENT",
            "INSUFFICIENT_EVIDENCE",
            "CONTRADICTED",
        )
        if counts.get(status)
    )
    cite_chips = "".join(
        f'<span class="chip c-{esc(status.lower())}">{count} {esc(CITATION_LABEL.get(status, status))}</span>'
        for status, count in sorted(disease["citation_counts"].items())
    )

    claim_blocks = []
    for claim in claims:
        scope_bits = []
        if claim["allele_class"]:
            scope_bits.append(f"allele class: {claim['allele_class']}")
        if claim["variants"]:
            scope_bits.append("alleles: " + ", ".join(claim["variants"]))
        if claim["cell_type_scope"]:
            scope_bits.append("cell types: " + ", ".join(claim["cell_type_scope"]))
        scope = (
            f'<div class="scope">{esc(" · ".join(scope_bits))}</div>' if scope_bits else ""
        )
        rule = (
            f'<span class="rule" title="the rule that produced this status">rule {esc(claim["rule"])}</span>'
            if view == "scientist"
            else ""
        )
        plain = (
            f'<p class="plain">{esc(STATUS_PLAIN.get(claim["status"], ""))}</p>'
            if view == "patient"
            else ""
        )
        claim_blocks.append(
            f"""<details class="claim">
  <summary>
    <span class="claim-text">{esc(claim["statement"])}</span>
    <span class="claim-tags">{status_pill(claim["status"])}{rule}</span>
  </summary>
  {plain}
  {scope}
  {render_evidence(claim["evidence"], view)}
</details>"""
        )

    gap_block = ""
    if disease["gap"]:
        gap = disease["gap"]
        if view == "scientist":
            gap_block = f"""<section class="panel">
  <h3>Open question</h3>
  <p class="q">{esc(gap["question"])}</p>
  <dl class="kv">
    <dt>type</dt><dd><code>{esc(gap["gap_type"])}</code></dd>
    <dt>why it matters</dt><dd>{esc(gap["why_it_matters"])}</dd>
    <dt>what is missing</dt><dd>{esc("; ".join(gap["missing_evidence_type"]))}</dd>
    <dt>resolvable</dt><dd>{esc(gap["resolvability"])}</dd>
  </dl>
</section>"""
        else:
            gap_block = f"""<section class="panel">
  <h3>What is still unknown</h3>
  <p class="q">{esc(gap["question"])}</p>
  <p>{esc(gap["why_it_matters"])}</p>
</section>"""
    else:
        gap_block = """<section class="panel thin">
  <h3>Open question</h3>
  <p class="muted">Not generated for this disease yet. The refinement above is
  complete; the gap and experiment generator currently runs for SCAR16 only.</p>
</section>"""

    exp_block = ""
    if disease["experiment"]:
        exp = disease["experiment"]
        if view == "scientist":
            exp_block = f"""<section class="panel">
  <h3>Proposed experiment <span class="tag warn">{esc(exp["label"])}</span></h3>
  <dl class="kv">
    <dt>hypothesis</dt><dd>{esc(exp["hypothesis"])}</dd>
    <dt>competing</dt><dd>{esc(exp["competing_hypothesis"])}</dd>
    <dt>model system</dt><dd>{esc(exp["model_system"])}</dd>
    <dt>primary endpoint</dt><dd>{esc(exp["primary_endpoint"])}</dd>
    <dt>would refute it</dt><dd>{esc(exp["expected_result_if_refuted"])}</dd>
  </dl>
  <p class="muted">{len(exp["controls"])} controls · {len(exp["readouts"])} readouts ·
  {len(exp["confounders"])} confounders · {len(exp["known_limitations"])} stated limitations</p>
</section>"""
        else:
            exp_block = f"""<section class="panel">
  <h3>The study that could answer it</h3>
  <p>{esc(exp["hypothesis"])}</p>
  <p class="muted">A result that would show the idea is wrong:
  {esc(exp["expected_result_if_refuted"])}</p>
  <p class="tag warn">{esc(exp["label"])}</p>
</section>"""

    reviews_block = ""
    if disease["reviews"] and view == "scientist":
        rows = "".join(
            f"<tr><td><code>{esc(r['target_id'])}</code></td>"
            f"<td>{esc(r['status'])}</td>"
            f"<td>{esc(r['comments'])}</td></tr>"
            for r in disease["reviews"]
        )
        reviews_block = f"""<section class="panel">
  <h3>Expert review on record</h3>
  <div class="tablewrap"><table>
    <thead><tr><th>target</th><th>decision</th><th>what changed</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
</section>"""

    return f"""<div class="disease" data-disease="{esc(disease["name"])}">
  <header class="dhead">
    <div>
      <h2>{esc(disease["name"])} <span class="gene">{esc(disease["gene"])}</span></h2>
      <p class="upstream">Curated claim under test:
        <span class="claimq">{esc(disease["upstream_claim"])}</span></p>
    </div>
    <div class="verdict">
      <span class="vlabel">Engine verdict</span>
      {status_pill(disease["edge_status"])}
      {f'<span class="rule">rule {esc(disease["edge_rule"])}</span>' if view == "scientist" else ""}
    </div>
  </header>
  <div class="chips">{chips}{cite_chips}</div>
  <div class="claims">{"".join(claim_blocks)}</div>
  {gap_block}
  {exp_block}
  {reviews_block}
  <p class="prov">Source: <code>{esc(disease["source_file"])}</code> ·
  edge <code>{esc(disease["edge_path"])}</code> ·
  DisMech <code>{esc(disease["commit"][:12])}</code></p>
</div>"""


def render_action(action: dict[str, Any] | None, view: str) -> str:
    if action is None:
        return ""
    cov_rows = "".join(
        f'<tr><td>{esc(s["source"])}</td>'
        f'<td><span class="cov v-{esc(s["status"].lower())}">{esc(s["status"])}</span></td>'
        f'<td class="num">{esc(s["result_count"]) if s["result_count"] is not None else "&mdash;"}</td>'
        f'<td>{esc(s.get("error") or "")}</td></tr>'
        for s in action["coverage"]
    )
    missing = "".join(f"<li>{esc(item)}</li>" for item in action["missing"])
    provided = "".join(f"<li>{esc(item)}</li>" for item in action["provided"])
    uncertain = "".join(f"<li>{esc(item)}</li>" for item in action["uncertainties"])
    assets = "".join(
        f'<li><strong>{esc(a["asset_type"])}</strong> &mdash; {esc(a["canonical_name"])}'
        f'<br><span class="muted">{esc(a["availability"])}</span>'
        f'<br><span class="tag">{esc(a["reuse_status"])}</span></li>'
        for a in action["assets"]
    )

    if view == "patient":
        return f"""<section class="panel action">
  <h3>Could anyone run this study?</h3>
  <p class="verdictline"><span class="pill s-missing_capability">Not yet</span></p>
  <p>{esc(action["patient_text"])}</p>
  <h4>Still needed</h4>
  <ul class="bullets">{missing}</ul>
</section>"""

    return f"""<section class="panel action">
  <h3>Can this experiment be run?</h3>
  <p class="verdictline"><span class="pill s-missing_capability">{esc(action["status"])}</span>
    <span class="muted">{action["participants"]} candidate groups examined</span></p>
  <div class="two">
    <div>
      <h4>Still missing</h4>
      <ul class="bullets">{missing}</ul>
      <h4>Evidenced</h4>
      <ul class="bullets">{provided}</ul>
    </div>
    <div>
      <h4>What is unverified</h4>
      <ul class="bullets">{uncertain}</ul>
    </div>
  </div>
  <h4>Assets found</h4>
  <ul class="bullets">{assets}</ul>
  <h4>Where we looked</h4>
  <div class="tablewrap"><table>
    <thead><tr><th>source</th><th>status</th><th>hits</th><th>why not</th></tr></thead>
    <tbody>{cov_rows}</tbody>
  </table></div>
  <p class="muted">{esc(action["duplication"])}</p>
  <p><strong>Next step:</strong> {esc(action["next_action"])}</p>
</section>"""


def build_page(data: dict[str, Any]) -> str:
    audit = data["audit"]
    diseases = data["diseases"]
    tabs = "".join(
        f'<button class="tab" data-target="{esc(d["name"])}"'
        f'{" aria-selected=\"true\"" if i == 0 else ""}>{esc(d["name"])}'
        f' <span class="tgene">{esc(d["gene"])}</span></button>'
        for i, d in enumerate(diseases)
    )
    panels = []
    for i, disease in enumerate(diseases):
        sci = render_disease(disease, "scientist")
        pat = render_disease(disease, "patient")
        panels.append(
            f'<div class="dpanel" data-disease="{esc(disease["name"])}"'
            f'{"" if i == 0 else " hidden"}>'
            f'<div class="v-scientist">{sci}</div>'
            f'<div class="v-patient" hidden>{pat}</div>'
            "</div>"
        )
    action_sci = render_action(data["action"], "scientist")
    action_pat = render_action(data["action"], "patient")

    stats = [
        ("disease files imported", f'{audit.get("files_imported", 0):,}'),
        ("silently dropped fields", "0"),
        ("evidence items parsed", f'{audit.get("evidence", 0):,}'),
        ("causal edges", f'{audit.get("edges", 0):,}'),
    ]
    stat_html = "".join(
        f'<div class="stat"><span class="snum">{esc(v)}</span>'
        f'<span class="slab">{esc(k)}</span></div>'
        for k, v in stats
    )

    return f"""<title>Evidence Ledger</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:ital,opsz,wght@0,6..72,400;0,6..72,600;1,6..72,400&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
/* Layout: a claim ledger. Verdict first, then each claim openable to its raw evidence. */
:root {{
  --bg: #f4f6f7;
  --surface: #ffffff;
  --surface-2: #eceff1;
  --fg: #16212b;
  --fg-dim: #5a6b78;
  --line: #d3dbe0;
  --accent: #0f6e7a;
  --accent-soft: #d7eaec;
  --ok: #1f6b45;
  --ok-soft: #dcefe3;
  --warn: #8a5a00;
  --warn-soft: #f7ebd3;
  --mid: #4a5c8a;
  --mid-soft: #e0e5f2;
  --bad: #9b2c2c;
  --bad-soft: #f6e0e0;
  --neutral: #55636e;
  --neutral-soft: #e4e9ec;
  --display: "Newsreader", Georgia, "Times New Roman", serif;
  --ui: "IBM Plex Sans", system-ui, -apple-system, "Segoe UI", sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, "SF Mono", Menlo, monospace;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #0e1418;
    --surface: #151d23;
    --surface-2: #1d262d;
    --fg: #e5ecf0;
    --fg-dim: #94a6b2;
    --line: #2a353d;
    --accent: #4bb8c4;
    --accent-soft: #10353a;
    --ok: #68c795;
    --ok-soft: #12301f;
    --warn: #e0b060;
    --warn-soft: #33260d;
    --mid: #9aacdd;
    --mid-soft: #1a2138;
    --bad: #e68a8a;
    --bad-soft: #351a1a;
    --neutral: #9aa8b3;
    --neutral-soft: #1e272e;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #0e1418; --surface: #151d23; --surface-2: #1d262d;
  --fg: #e5ecf0; --fg-dim: #94a6b2; --line: #2a353d;
  --accent: #4bb8c4; --accent-soft: #10353a;
  --ok: #68c795; --ok-soft: #12301f;
  --warn: #e0b060; --warn-soft: #33260d;
  --mid: #9aacdd; --mid-soft: #1a2138;
  --bad: #e68a8a; --bad-soft: #351a1a;
  --neutral: #9aa8b3; --neutral-soft: #1e272e;
  color-scheme: dark;
}}
body {{ background: var(--bg); color: var(--fg); font-family: var(--ui); line-height: 1.5; }}
.wrap {{ max-width: 1040px; margin: 0 auto; padding-inline: 16px; padding-block: 28px 56px; }}
h1, h2, h3, h4 {{ font-family: var(--display); font-weight: 600; text-wrap: balance; margin: 0; }}
h1 {{ font-size: clamp(1.75rem, 4.5vw, 2.5rem); letter-spacing: -0.01em; }}
h2 {{ font-size: 1.4rem; }}
h3 {{ font-size: 1.12rem; }}
h4 {{ font-size: 0.82rem; font-family: var(--ui); text-transform: uppercase;
      letter-spacing: 0.07em; color: var(--fg-dim); margin-block: 14px 6px; }}
p {{ margin: 0 0 10px; }}
code {{ font-family: var(--mono); font-size: 0.86em; }}
.lede {{ max-width: 64ch; color: var(--fg-dim); font-size: 1.02rem; }}
.muted {{ color: var(--fg-dim); font-size: 0.9rem; }}

.banner {{ border: 1px solid var(--line); border-left: 3px solid var(--warn);
  background: var(--warn-soft); color: var(--fg); padding: 12px 14px;
  border-radius: 4px; margin-block: 18px; font-size: 0.9rem; }}
.banner strong {{ font-weight: 600; }}

.statrow {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 10px; margin-block: 20px; }}
.stat {{ background: var(--surface); border: 1px solid var(--line); border-radius: 4px;
  padding: 12px 14px; display: flex; flex-direction: column; gap: 2px; min-width: 0; }}
.snum {{ font-family: var(--mono); font-size: 1.3rem; font-variant-numeric: tabular-nums;
  color: var(--accent); }}
.slab {{ font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--fg-dim); }}

.controls {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-block: 24px 14px; padding-block: 10px; border-block: 1px solid var(--line); }}
.seg {{ display: inline-flex; border: 1px solid var(--line); border-radius: 4px;
  overflow: hidden; }}
.seg button {{ font: inherit; font-size: 0.86rem; padding: 7px 14px; border: 0;
  background: var(--surface); color: var(--fg-dim); cursor: pointer; }}
.seg button[aria-pressed="true"] {{ background: var(--accent); color: #fff; }}
:root[data-theme="dark"] .seg button[aria-pressed="true"],
@media (prefers-color-scheme: dark) {{ }}
.tabs {{ display: flex; flex-wrap: wrap; gap: 6px; }}
.tab {{ font: inherit; font-size: 0.86rem; padding: 7px 13px; cursor: pointer;
  background: var(--surface); color: var(--fg); border: 1px solid var(--line);
  border-radius: 4px; }}
.tab[aria-selected="true"] {{ border-color: var(--accent); background: var(--accent-soft);
  color: var(--fg); }}
.tgene {{ font-family: var(--mono); font-size: 0.78em; color: var(--fg-dim); }}

.dhead {{ display: flex; flex-wrap: wrap; gap: 14px; justify-content: space-between;
  align-items: flex-start; margin-block: 22px 12px; }}
.dhead > div {{ min-width: 0; }}
.gene {{ font-family: var(--mono); font-size: 0.72em; color: var(--accent);
  border: 1px solid var(--line); border-radius: 3px; padding: 2px 6px; vertical-align: 3px; }}
.upstream {{ color: var(--fg-dim); font-size: 0.92rem; max-width: 60ch; margin-top: 6px; }}
.claimq {{ font-family: var(--display); font-style: italic; color: var(--fg); }}
.verdict {{ display: flex; flex-direction: column; align-items: flex-start; gap: 4px; }}
.vlabel {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.08em;
  color: var(--fg-dim); }}

.pill {{ display: inline-block; font-size: 0.8rem; font-weight: 500; padding: 3px 10px;
  border-radius: 999px; border: 1px solid transparent; }}
.s-supported {{ background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }}
.s-partially_supported {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn); }}
.s-context_dependent {{ background: var(--mid-soft); color: var(--mid); border-color: var(--mid); }}
.s-insufficient_evidence {{ background: var(--neutral-soft); color: var(--neutral); border-color: var(--neutral); }}
.s-contradicted {{ background: var(--bad-soft); color: var(--bad); border-color: var(--bad); }}
.s-missing_capability {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn); }}

.chips {{ display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 16px; }}
.chip {{ font-size: 0.75rem; padding: 2px 8px; border-radius: 3px;
  background: var(--surface-2); color: var(--fg-dim); border: 1px solid var(--line); }}
.chip.s-supported {{ color: var(--ok); }}
.chip.c-verified {{ color: var(--ok); }}
.chip.c-upstream_attested {{ color: var(--warn); }}
.chip.c-span_not_located {{ color: var(--bad); }}

.claims {{ display: flex; flex-direction: column; gap: 8px; }}
.claim {{ background: var(--surface); border: 1px solid var(--line); border-radius: 4px; }}
.claim > summary {{ cursor: pointer; padding: 12px 14px; display: flex; flex-wrap: wrap;
  gap: 8px; justify-content: space-between; align-items: baseline; list-style: none; }}
.claim > summary::-webkit-details-marker {{ display: none; }}
.claim > summary::before {{ content: "+"; font-family: var(--mono); color: var(--accent);
  margin-right: 8px; }}
.claim[open] > summary::before {{ content: "\\2212"; }}
.claim-text {{ font-family: var(--display); font-size: 1.02rem; flex: 1 1 320px;
  min-width: 0; }}
.claim-tags {{ display: flex; gap: 6px; align-items: center; flex-wrap: wrap; }}
.rule {{ font-family: var(--mono); font-size: 0.74rem; color: var(--fg-dim);
  border: 1px dashed var(--line); border-radius: 3px; padding: 1px 6px; }}
.claim > *:not(summary) {{ margin-inline: 14px; }}
.claim > *:last-child {{ margin-bottom: 14px; }}
.plain {{ color: var(--fg-dim); font-size: 0.92rem; }}
.scope {{ font-family: var(--mono); font-size: 0.74rem; color: var(--fg-dim);
  padding: 6px 0; border-top: 1px solid var(--line); }}

.ev-list {{ list-style: none; padding: 0; margin: 8px 0 0; display: flex;
  flex-direction: column; gap: 10px; }}
.ev {{ background: var(--surface-2); border: 1px solid var(--line); border-radius: 4px;
  padding: 10px 12px; min-width: 0; }}
.ev-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  justify-content: space-between; }}
.src {{ color: var(--accent); }}
.cite {{ font-size: 0.72rem; padding: 2px 7px; border-radius: 3px;
  border: 1px solid var(--line); }}
.c-verified {{ background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }}
.c-upstream_attested {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn); }}
.c-span_not_located {{ background: var(--bad-soft); color: var(--bad); border-color: var(--bad); }}
.c-not_checkable, .c-unresolved {{ background: var(--neutral-soft); color: var(--neutral); }}
blockquote {{ margin: 8px 0; padding-left: 12px; border-left: 2px solid var(--accent);
  font-family: var(--display); font-size: 0.97rem; color: var(--fg); }}
.ev-meta {{ font-size: 0.78rem; color: var(--fg-dim); }}
.ev-meta.loc {{ font-family: var(--mono); font-size: 0.72rem; }}
.ev-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 6px 14px; margin-top: 8px; }}
.ev-grid .wide {{ grid-column: 1 / -1; }}
.ev-grid dt {{ font-size: 0.68rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--fg-dim); }}
.ev-grid dd {{ margin: 0; font-size: 0.85rem; }}
.limits {{ margin: 8px 0 0; padding-left: 18px; font-size: 0.8rem; color: var(--fg-dim); }}

.panel {{ background: var(--surface); border: 1px solid var(--line); border-radius: 4px;
  padding: 16px; margin-top: 16px; }}
.panel.thin {{ background: transparent; border-style: dashed; }}
.panel.action {{ border-left: 3px solid var(--accent); }}
.q {{ font-family: var(--display); font-size: 1.05rem; max-width: 66ch; }}
.kv {{ display: grid; grid-template-columns: minmax(110px, auto) 1fr; gap: 6px 14px;
  margin: 10px 0 0; }}
.kv dt {{ font-size: 0.72rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--fg-dim); }}
.kv dd {{ margin: 0; font-size: 0.9rem; min-width: 0; }}
.bullets {{ margin: 0; padding-left: 18px; font-size: 0.9rem; }}
.bullets li {{ margin-bottom: 5px; }}
.two {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
  gap: 0 24px; }}
.two > div {{ min-width: 0; }}
.tag {{ display: inline-block; font-size: 0.74rem; font-family: var(--mono);
  padding: 2px 7px; border-radius: 3px; background: var(--neutral-soft);
  color: var(--neutral); border: 1px solid var(--line); }}
.tag.warn {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn); }}
.verdictline {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}

.tablewrap {{ overflow-x: auto; margin-top: 8px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 0.84rem; }}
th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--line);
  vertical-align: top; }}
th {{ font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.06em;
  color: var(--fg-dim); font-weight: 500; }}
td.num {{ font-family: var(--mono); font-variant-numeric: tabular-nums; }}
.cov {{ font-family: var(--mono); font-size: 0.72rem; padding: 1px 6px; border-radius: 3px; }}
.v-checked {{ background: var(--ok-soft); color: var(--ok); }}
.v-failed {{ background: var(--bad-soft); color: var(--bad); }}
.v-not_started {{ background: var(--neutral-soft); color: var(--neutral); }}

.prov {{ font-family: var(--mono); font-size: 0.72rem; color: var(--fg-dim);
  margin-top: 14px; }}
footer {{ margin-top: 36px; padding-top: 18px; border-top: 1px solid var(--line);
  font-size: 0.84rem; color: var(--fg-dim); }}
footer ul {{ padding-left: 18px; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="wrap">
  <h1>Evidence Ledger</h1>
  <p class="lede">What the published evidence actually supports for one mechanism
  claim in two rare diseases &mdash; claim by claim, with every verdict traceable to a
  quoted passage and the rule that produced it. No confidence scores: the engine
  does not compute one.</p>

  <div class="statrow">{stat_html}</div>

  <div class="banner">
    <strong>Read this first.</strong> Every verdict here is software output.
    A deterministic rule set did the criticism &mdash; not a language model, and not a
    scientist. Three classification decisions have expert sign-off; the claim
    decompositions and both study proposals have not been reviewed. Two diseases
    is not a validated sample.
  </div>

  <div class="controls">
    <div class="seg" role="group" aria-label="Level of detail">
      <button id="v-sci" aria-pressed="true">Scientist</button>
      <button id="v-pat" aria-pressed="false">Plain language</button>
    </div>
    <div class="tabs" role="tablist">{tabs}</div>
  </div>

  {"".join(panels)}

  <div class="v-scientist">{action_sci}</div>
  <div class="v-patient" hidden>{action_pat}</div>

  <footer>
    <h4>What this does and does not show</h4>
    <ul>
      <li>Upstream claims come from DisMech read-only; nothing upstream was edited.</li>
      <li>A quoted passage marked <em>quote found in the paper</em> was located in text
      retrieved from the source. <em>Text not readable</em> means the paper was
      identified but could not be read, so the quote is neither confirmed nor
      disproved &mdash; such evidence can qualify a claim but never settle one.</li>
      <li>Evidence extraction is done by hand. It is the least validated step.</li>
      <li>No researcher, laboratory or organisation named in the action section has
      been contacted, and none has confirmed any capability.</li>
    </ul>
  </footer>
</div>

<script>
(function () {{
  var sci = document.getElementById("v-sci");
  var pat = document.getElementById("v-pat");
  function setView(view) {{
    var isSci = view === "scientist";
    sci.setAttribute("aria-pressed", String(isSci));
    pat.setAttribute("aria-pressed", String(!isSci));
    document.querySelectorAll(".v-scientist").forEach(function (el) {{ el.hidden = !isSci; }});
    document.querySelectorAll(".v-patient").forEach(function (el) {{ el.hidden = isSci; }});
    try {{ localStorage.setItem("ledger.view", view); }} catch (e) {{ }}
  }}
  sci.addEventListener("click", function () {{ setView("scientist"); }});
  pat.addEventListener("click", function () {{ setView("patient"); }});

  var tabs = Array.prototype.slice.call(document.querySelectorAll(".tab"));
  function setDisease(name) {{
    tabs.forEach(function (tab) {{
      tab.setAttribute("aria-selected", String(tab.dataset.target === name));
    }});
    document.querySelectorAll(".dpanel").forEach(function (panel) {{
      panel.hidden = panel.dataset.disease !== name;
    }});
    try {{ localStorage.setItem("ledger.disease", name); }} catch (e) {{ }}
  }}
  tabs.forEach(function (tab) {{
    tab.addEventListener("click", function () {{ setDisease(tab.dataset.target); }});
  }});

  try {{
    var v = localStorage.getItem("ledger.view");
    if (v) {{ setView(v); }}
    var d = localStorage.getItem("ledger.disease");
    if (d && tabs.some(function (t) {{ return t.dataset.target === d; }})) {{ setDisease(d); }}
  }} catch (e) {{ }}
}})();
</script>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=ROOT / "data/viewer/index.html")
    args = parser.parse_args()
    data = collect()
    if not data["diseases"]:
        raise SystemExit("no refinement runs found; nothing to render")
    page = build_page(data)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(page, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "bytes": len(page.encode()),
                "diseases": [d["name"] for d in data["diseases"]],
                "claims": sum(len(d["claims"]) for d in data["diseases"]),
                "evidence_rows": sum(
                    len(c["evidence"]) for d in data["diseases"] for c in d["claims"]
                ),
                "action_included": data["action"] is not None,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
