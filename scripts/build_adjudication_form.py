#!/usr/bin/env python3
"""Generate an interactive adjudication form from the blinded worksheet.

Hand-editing a JSON file is friction that costs reviewer attention, so this turns
the worksheet into a page the reviewer clicks through, then copies one JSON blob
out of for scoring.

Built from worksheet.json rather than from the refinement artifacts directly, so
it inherits that file's blinding guarantee: the worksheet is already verified to
contain no engine status, no rule and no critic verdict. This script adds no new
data, and asserts the same before writing.

Work in progress is kept in localStorage so a half-finished adjudication survives
a reload, and the page states that this is per-browser and not sent anywhere.
"""

from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
STATUSES = (
    ("SUPPORTED", "Supported", "Direct evidence supports it; nothing refutes or qualifies it."),
    (
        "PARTIALLY_SUPPORTED",
        "Partly supported",
        "Only qualified or partial direct support.",
    ),
    (
        "CONTEXT_DEPENDENT",
        "Context-dependent",
        "Direct evidence both supports and limits it: true in some contexts.",
    ),
    (
        "INSUFFICIENT_EVIDENCE",
        "Insufficient evidence",
        "Not enough direct evidence to judge either way.",
    ),
    (
        "CONTRADICTED",
        "Contradicted",
        "Direct evidence refutes it, from independent publications.",
    ),
)
CITATION_NOTE = {
    "VERIFIED": "quote located in retrieved text",
    "UPSTREAM_ATTESTED": "paper identified, text not retrievable, quote unconfirmed",
    "SPAN_NOT_LOCATED": "text retrieved and quote NOT in it",
    "NOT_CHECKABLE": "reference form has no resolver",
    "UNRESOLVED": "identifier did not resolve",
    "TITLE_MISMATCH": "title does not match",
}
FORBIDDEN = ("rule_applied", "engine_status", "engine_rationale", "directness", "causal_support")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_item(index: int, item: dict[str, Any]) -> str:
    scope_rows = []
    scope = item["scope"]
    if scope.get("variants"):
        scope_rows.append(("alleles", ", ".join(scope["variants"])))
    if scope.get("allele_class"):
        scope_rows.append(("allele class", scope["allele_class"]))
    if scope.get("cell_type_scope"):
        scope_rows.append(("cell types", ", ".join(scope["cell_type_scope"])))
    scope_rows.append(("disease", ", ".join(scope.get("disease_scope", []))))
    scope_rows.append(
        ("readouts in scope", ", ".join(scope.get("readouts_bearing_on_this_claim", [])))
    )
    scope_html = "".join(
        f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>" for label, value in scope_rows
    )

    evidence_html = []
    for row in item["evidence"]:
        citation = row["citation_status"]
        upstream = ""
        if row.get("upstream_reference_form") and row["upstream_reference_form"] != row["source"]:
            upstream = (
                f'<div class="meta">upstream wrote <code>'
                f'{esc(row["upstream_reference_form"])}</code></div>'
            )
        evidence_html.append(
            f"""<li class="ev">
  <div class="evhead">
    <code>{esc(row["source"])}</code>
    <span class="cite c-{esc(citation.lower())}" title="{esc(CITATION_NOTE.get(citation, ""))}">
      {esc(citation.replace("_", " ").lower())}</span>
  </div>
  {upstream}
  <blockquote>{esc(row["span"].strip())}</blockquote>
  <dl class="meta-grid">
    <div><dt>origin</dt><dd>{esc(row["origin"].replace("_", " ").lower())}</dd></div>
    <div><dt>readout</dt><dd>{esc(row["readout"])}</dd></div>
    <div><dt>effect as extracted</dt><dd><strong>{esc(row["effect_as_extracted"])}</strong></dd></div>
    <div><dt>cell types</dt><dd>{esc(", ".join(row["cell_types"]) or "not stated")}</dd></div>
    <div class="wide"><dt>system</dt><dd>{esc(row["experimental_system"])}</dd></div>
    <div class="wide"><dt>found in</dt><dd>{esc(row["span_location"].replace("_", " "))}</dd></div>
  </dl>
</li>"""
        )
    if not item["evidence"]:
        evidence_html.append('<li class="ev muted">No evidence linked to this claim.</li>')

    options = "".join(
        f"""<label class="opt">
  <input type="radio" name="st-{index}" value="{esc(code)}" data-item="{esc(item["item_id"])}">
  <span class="optlabel">{esc(label)}</span>
  <span class="opthelp">{esc(helptext)}</span>
</label>"""
        for code, label, helptext in STATUSES
    )

    return f"""<section class="item" id="item-{index}" data-item="{esc(item["item_id"])}">
  <div class="itemhead">
    <span class="num">{index + 1} / 9</span>
    <span class="dis">{esc(item["disease"])} <span class="gene">{esc(item["gene"])}</span></span>
    <span class="done" hidden>answered</span>
  </div>
  <p class="context">Curated claim under test:
    <span class="quietq">{esc(item["upstream_edge_claim"])}</span></p>
  <h2>{esc(item["atomic_claim"])}</h2>
  <dl class="scope">{scope_html}</dl>
  <h3>Evidence ({len(item["evidence"])})</h3>
  <ul class="evlist">{"".join(evidence_html)}</ul>
  <fieldset class="verdict">
    <legend>Your verdict</legend>
    <div class="opts">{options}</div>
    <label class="dispute">
      <input type="checkbox" name="dx-{index}" data-item="{esc(item["item_id"])}">
      I reject how this evidence was characterised (an effect label, a system
      description, the claim's scope) rather than disagreeing about the status
    </label>
    <label class="notewrap">
      <span>Note (most useful when you disagree)</span>
      <textarea name="nt-{index}" rows="2" data-item="{esc(item["item_id"])}"></textarea>
    </label>
  </fieldset>
</section>"""


def build(worksheet: dict[str, Any]) -> str:
    items = worksheet["items"]
    sections = "".join(render_item(i, item) for i, item in enumerate(items))
    item_ids = json.dumps([item["item_id"] for item in items])
    return f"""<title>Adjudication Form</title>
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
/* Layout: one claim per card, evidence above the verdict, progress pinned at top. */
:root {{
  --bg: #f5f6f4; --surface: #fff; --surface-2: #ecefea; --fg: #1b2420;
  --fg-dim: #5d6b64; --line: #d4dbd6; --accent: #2f6b4f; --accent-soft: #dceae2;
  --ok: #1f6b45; --ok-soft: #dcefe3; --warn: #8a5a00; --warn-soft: #f7ebd3;
  --bad: #9b2c2c; --bad-soft: #f6e0e0; --neutral: #55636e; --neutral-soft: #e4e9ec;
  --display: "Newsreader", Georgia, serif;
  --ui: "IBM Plex Sans", system-ui, sans-serif;
  --mono: "IBM Plex Mono", ui-monospace, Menlo, monospace;
  color-scheme: light;
}}
@media (prefers-color-scheme: dark) {{
  :root:not([data-theme="light"]) {{
    --bg: #11150f; --surface: #181e18; --surface-2: #202820; --fg: #e8ede8;
    --fg-dim: #9aaaa0; --line: #2d372f; --accent: #6fc49a; --accent-soft: #14301f;
    --ok: #68c795; --ok-soft: #12301f; --warn: #e0b060; --warn-soft: #33260d;
    --bad: #e68a8a; --bad-soft: #351a1a; --neutral: #9aa8b3; --neutral-soft: #1e272e;
    color-scheme: dark;
  }}
}}
:root[data-theme="dark"] {{
  --bg: #11150f; --surface: #181e18; --surface-2: #202820; --fg: #e8ede8;
  --fg-dim: #9aaaa0; --line: #2d372f; --accent: #6fc49a; --accent-soft: #14301f;
  --ok: #68c795; --ok-soft: #12301f; --warn: #e0b060; --warn-soft: #33260d;
  --bad: #e68a8a; --bad-soft: #351a1a; --neutral: #9aa8b3; --neutral-soft: #1e272e;
  color-scheme: dark;
}}
body {{ background: var(--bg); color: var(--fg); font-family: var(--ui); line-height: 1.5; }}
.wrap {{ max-width: 760px; margin: 0 auto; padding-inline: 16px; padding-block: 24px 64px; }}
h1 {{ font-family: var(--display); font-size: clamp(1.6rem, 4.5vw, 2.1rem); margin: 0 0 8px;
  text-wrap: balance; }}
h2 {{ font-family: var(--display); font-size: 1.22rem; margin: 10px 0; text-wrap: balance; }}
h3 {{ font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.07em;
  color: var(--fg-dim); margin: 16px 0 6px; font-weight: 600; }}
p {{ margin: 0 0 10px; }}
code {{ font-family: var(--mono); font-size: 0.85em; }}
.lede {{ color: var(--fg-dim); max-width: 62ch; }}
.note {{ background: var(--accent-soft); border: 1px solid var(--line);
  border-left: 3px solid var(--accent); padding: 11px 13px; border-radius: 4px;
  font-size: 0.88rem; margin-block: 14px; }}

.bar {{ position: sticky; top: env(safe-area-inset-top, 0px); z-index: 5;
  background: var(--bg); border-bottom: 1px solid var(--line);
  padding-block: 10px; margin-bottom: 18px; display: flex; flex-wrap: wrap;
  gap: 10px; align-items: center; justify-content: space-between; }}
.track {{ flex: 1 1 160px; height: 6px; background: var(--surface-2);
  border-radius: 999px; overflow: hidden; min-width: 120px; }}
.fill {{ height: 100%; width: 0%; background: var(--accent); transition: width .2s; }}
.count {{ font-family: var(--mono); font-size: 0.82rem; font-variant-numeric: tabular-nums;
  color: var(--fg-dim); }}
button {{ font: inherit; font-size: 0.86rem; padding: 8px 14px; border-radius: 4px;
  border: 1px solid var(--accent); background: var(--accent); color: #fff; cursor: pointer; }}
button.ghost {{ background: var(--surface); color: var(--fg); border-color: var(--line); }}
button:disabled {{ opacity: .5; cursor: not-allowed; }}

.item {{ background: var(--surface); border: 1px solid var(--line); border-radius: 5px;
  padding: 16px; margin-bottom: 18px; }}
.itemhead {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  justify-content: space-between; font-size: 0.78rem; color: var(--fg-dim); }}
.num {{ font-family: var(--mono); }}
.gene {{ font-family: var(--mono); color: var(--accent); }}
.done {{ color: var(--ok); font-weight: 500; }}
.context {{ font-size: 0.85rem; color: var(--fg-dim); margin-top: 8px; }}
.quietq {{ font-family: var(--display); font-style: italic; }}
dl.scope {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
  gap: 4px 16px; margin: 0; padding: 10px 0; border-block: 1px solid var(--line); }}
dl.scope dt, .meta-grid dt {{ font-size: 0.66rem; text-transform: uppercase;
  letter-spacing: 0.06em; color: var(--fg-dim); }}
dl.scope dd, .meta-grid dd {{ margin: 0; font-size: 0.85rem; }}

.evlist {{ list-style: none; margin: 0; padding: 0; display: flex;
  flex-direction: column; gap: 10px; }}
.ev {{ background: var(--surface-2); border: 1px solid var(--line); border-radius: 4px;
  padding: 10px 12px; min-width: 0; }}
.evhead {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  justify-content: space-between; }}
.cite {{ font-family: var(--mono); font-size: 0.7rem; padding: 2px 7px; border-radius: 3px;
  border: 1px solid var(--line); }}
.c-verified {{ background: var(--ok-soft); color: var(--ok); border-color: var(--ok); }}
.c-upstream_attested {{ background: var(--warn-soft); color: var(--warn); border-color: var(--warn); }}
.c-span_not_located {{ background: var(--bad-soft); color: var(--bad); border-color: var(--bad); }}
.c-not_checkable, .c-unresolved {{ background: var(--neutral-soft); color: var(--neutral); }}
blockquote {{ margin: 8px 0; padding-left: 12px; border-left: 2px solid var(--accent);
  font-family: var(--display); font-size: 0.98rem; }}
.meta {{ font-size: 0.76rem; color: var(--fg-dim); }}
.meta-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 4px 14px; margin: 8px 0 0; }}
.meta-grid .wide {{ grid-column: 1 / -1; }}

fieldset.verdict {{ border: 1px solid var(--line); border-radius: 4px; margin: 16px 0 0;
  padding: 12px 14px; }}
legend {{ font-size: 0.74rem; text-transform: uppercase; letter-spacing: 0.07em;
  color: var(--fg-dim); padding-inline: 6px; }}
.opts {{ display: flex; flex-direction: column; gap: 4px; }}
.opt {{ display: grid; grid-template-columns: auto 1fr; gap: 2px 10px; align-items: start;
  padding: 7px 9px; border: 1px solid transparent; border-radius: 4px; cursor: pointer; }}
.opt:hover {{ background: var(--surface-2); }}
.opt input {{ margin-top: 3px; grid-row: span 2; }}
.optlabel {{ font-weight: 500; font-size: 0.92rem; }}
.opthelp {{ font-size: 0.78rem; color: var(--fg-dim); }}
.opt:has(input:checked) {{ border-color: var(--accent); background: var(--accent-soft); }}
.dispute {{ display: grid; grid-template-columns: auto 1fr; gap: 9px; align-items: start;
  margin-top: 12px; font-size: 0.82rem; color: var(--fg-dim);
  padding-top: 10px; border-top: 1px solid var(--line); }}
.notewrap {{ display: block; margin-top: 10px; font-size: 0.78rem; color: var(--fg-dim); }}
textarea {{ width: 100%; box-sizing: border-box; margin-top: 4px; font: inherit;
  font-size: 0.86rem; padding: 7px 9px; border: 1px solid var(--line); border-radius: 4px;
  background: var(--surface); color: var(--fg); resize: vertical; }}

.out {{ background: var(--surface); border: 1px solid var(--line); border-radius: 5px;
  padding: 16px; }}
.out textarea {{ font-family: var(--mono); font-size: 0.74rem; min-height: 150px; }}
.row {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-top: 10px; }}
.said {{ font-size: 0.82rem; color: var(--ok); }}
.muted {{ color: var(--fg-dim); font-size: 0.88rem; }}
:focus-visible {{ outline: 2px solid var(--accent); outline-offset: 2px; }}
@media (prefers-reduced-motion: reduce) {{ * {{ transition: none !important; }} }}
</style>

<div class="wrap">
  <h1>Adjudication Form</h1>
  <p class="lede">Nine atomic claims from two diseases. Assign a status to each
  <strong>from the evidence shown</strong>. The engine's own verdicts, the rules it
  applied and its per-evidence judgements are not in this page.</p>

  <div class="note">
    Answers stay in this browser until you copy them out; nothing is sent anywhere.
    A reload will not lose your work. When you are done, copy the JSON at the
    bottom and paste it back into the conversation for scoring.
  </div>

  <div class="bar">
    <div class="track"><div class="fill" id="fill"></div></div>
    <span class="count" id="count">0 of 9 answered</span>
    <button class="ghost" id="jump">Next unanswered</button>
  </div>

  {sections}

  <section class="out">
    <h3>Your responses</h3>
    <p class="muted">Copy this and paste it back to be scored. It fills in as you go.</p>
    <textarea id="json" readonly></textarea>
    <div class="row">
      <button id="copy">Copy responses</button>
      <button class="ghost" id="reset">Clear all answers</button>
      <span class="said" id="said" hidden>Copied</span>
    </div>
  </section>
</div>

<script>
(function () {{
  var IDS = {item_ids};
  var KEY = "adjudication.round1";
  var out = document.getElementById("json");
  var fill = document.getElementById("fill");
  var count = document.getElementById("count");
  var said = document.getElementById("said");

  function state() {{
    var rows = IDS.map(function (id, i) {{
      var picked = document.querySelector('input[name="st-' + i + '"]:checked');
      var dx = document.querySelector('input[name="dx-' + i + '"]');
      var nt = document.querySelector('textarea[name="nt-' + i + '"]');
      return {{
        item_id: id,
        reviewer_status: picked ? picked.value : "",
        extraction_disputed: !!(dx && dx.checked),
        note: nt ? nt.value : ""
      }};
    }});
    return {{
      schema_version: "eval-responses-v1",
      reviewer_name: "project domain reviewer",
      reviewer_role: "biologist; rare-disease mechanism and evidence appraisal",
      reviewed_on: new Date().toISOString().slice(0, 10),
      responses: rows
    }};
  }}

  function paint() {{
    var data = state();
    var done = data.responses.filter(function (r) {{ return r.reviewer_status; }}).length;
    out.value = JSON.stringify(data, null, 2);
    fill.style.width = (done / IDS.length * 100) + "%";
    count.textContent = done + " of " + IDS.length + " answered";
    data.responses.forEach(function (r, i) {{
      var section = document.getElementById("item-" + i);
      if (section) {{ section.querySelector(".done").hidden = !r.reviewer_status; }}
    }});
    try {{ localStorage.setItem(KEY, JSON.stringify(data)); }} catch (e) {{ }}
  }}

  function restore() {{
    var raw = null;
    try {{ raw = localStorage.getItem(KEY); }} catch (e) {{ return; }}
    if (!raw) {{ return; }}
    try {{
      var data = JSON.parse(raw);
      (data.responses || []).forEach(function (r) {{
        var i = IDS.indexOf(r.item_id);
        if (i < 0) {{ return; }}
        if (r.reviewer_status) {{
          var input = document.querySelector(
            'input[name="st-' + i + '"][value="' + r.reviewer_status + '"]'
          );
          if (input) {{ input.checked = true; }}
        }}
        var dx = document.querySelector('input[name="dx-' + i + '"]');
        if (dx) {{ dx.checked = !!r.extraction_disputed; }}
        var nt = document.querySelector('textarea[name="nt-' + i + '"]');
        if (nt && r.note) {{ nt.value = r.note; }}
      }});
    }} catch (e) {{ }}
  }}

  document.addEventListener("change", paint);
  document.addEventListener("input", function (event) {{
    if (event.target.tagName === "TEXTAREA" && event.target.id !== "json") {{ paint(); }}
  }});

  document.getElementById("jump").addEventListener("click", function () {{
    for (var i = 0; i < IDS.length; i++) {{
      if (!document.querySelector('input[name="st-' + i + '"]:checked')) {{
        document.getElementById("item-" + i).scrollIntoView({{ block: "start" }});
        return;
      }}
    }}
    document.querySelector(".out").scrollIntoView({{ block: "start" }});
  }});

  document.getElementById("copy").addEventListener("click", function () {{
    var show = function () {{ said.hidden = false; setTimeout(function () {{ said.hidden = true; }}, 2200); }};
    try {{
      navigator.clipboard.writeText(out.value).then(show, function () {{
        out.focus(); out.select(); show();
      }});
    }} catch (e) {{ out.focus(); out.select(); show(); }}
  }});

  document.getElementById("reset").addEventListener("click", function () {{
    document.querySelectorAll('input[type="radio"]').forEach(function (el) {{ el.checked = false; }});
    document.querySelectorAll('input[type="checkbox"]').forEach(function (el) {{ el.checked = false; }});
    document.querySelectorAll('textarea[name^="nt-"]').forEach(function (el) {{ el.value = ""; }});
    try {{ localStorage.removeItem(KEY); }} catch (e) {{ }}
    paint();
  }});

  restore();
  paint();
}})();
</script>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--worksheet", type=Path, default=ROOT / "data/eval/round-1/worksheet.json"
    )
    parser.add_argument(
        "--output", type=Path, default=ROOT / "data/eval/round-1/adjudication_form.html"
    )
    args = parser.parse_args()
    worksheet = json.loads(args.worksheet.read_text(encoding="utf-8"))
    page = build(worksheet)

    # The form must inherit the worksheet's blinding, so assert it afresh here.
    # Count exact radio values: a substring count would over-report, since
    # "SUPPORTED" is contained in "PARTIALLY_SUPPORTED".
    expected = len(worksheet["items"])
    for status, _label, _help in STATUSES:
        occurrences = page.count(f'value="{status}"')
        if occurrences != expected:
            raise SystemExit(
                f"status {status} appears as a value {occurrences} times, expected "
                f"{expected} (one radio per item); a status outside a radio value "
                "would mean the engine's answer leaked in"
            )
    for token in FORBIDDEN:
        if token in page:
            raise SystemExit(f"form leaks {token!r}")

    args.output.write_text(page, encoding="utf-8")
    print(
        json.dumps(
            {
                "output": str(args.output),
                "items": len(worksheet["items"]),
                "bytes": len(page.encode()),
                "blinding_verified": True,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
