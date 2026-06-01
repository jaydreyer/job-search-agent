"""Generate a self-contained HTML dashboard from the digest CSVs.

Aggregates every `data/digests/*.csv`, dedupes by company+title (keeping the
highest score and earliest first-seen date), and writes a single `index.html`
with client-side search / sort / filter and per-row feedback buttons.

Open it directly (read-only), or run `uv run jobsearch-serve` for the interactive
version where Applied / Not-interested / ⭐ buttons persist to data/feedback.json.

    uv run jobsearch-dashboard
"""

from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from pathlib import Path

from .. import feedback
from ..config import ROOT

DIGEST_DIR = ROOT / "data" / "digests"
OUT_FILE = DIGEST_DIR / "index.html"
_DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")


def _file_date(path: Path) -> str:
    m = _DATE_RE.search(path.name)
    return m.group(1) if m else datetime.fromtimestamp(path.stat().st_mtime).date().isoformat()


def _load_rows() -> list[dict]:
    by_key: dict[tuple[str, str], dict] = {}
    for csv_path in sorted(DIGEST_DIR.glob("*.csv")):
        run_date = _file_date(csv_path)
        try:
            reader = csv.DictReader(csv_path.read_text().splitlines())
        except Exception:
            continue
        for r in reader:
            title = (r.get("title") or "").strip()
            company = (r.get("company") or "").strip()
            if not title or not company:
                continue
            try:
                score = int(float(r.get("score") or 0))
            except ValueError:
                score = 0
            key = (company.lower(), title.lower())
            row = {
                "score": score, "title": title, "company": company,
                "location": (r.get("location") or "").strip(),
                "salary": (r.get("salary") or "").strip(),
                "source": (r.get("source") or "").strip(),
                "url": (r.get("url") or "").strip(),
                "verdict": (r.get("verdict") or "").strip(),
                "first_seen": run_date, "last_seen": run_date,
            }
            existing = by_key.get(key)
            if existing is None:
                by_key[key] = row
            else:
                existing["first_seen"] = min(existing["first_seen"], run_date)
                existing["last_seen"] = max(existing["last_seen"], run_date)
                if score > existing["score"]:
                    existing.update({k: row[k] for k in ("score", "location", "salary", "source", "url", "verdict")})
    rows = list(by_key.values())
    rows.sort(key=lambda r: (r["score"], r["last_seen"]), reverse=True)
    return rows


def build_dashboard(out_path: Path = OUT_FILE) -> Path:
    rows = _load_rows()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    html = (
        _HTML_TEMPLATE.replace("__DATA__", json.dumps(rows))
        .replace("__FEEDBACK__", json.dumps(feedback.items()))
        .replace("__PREFS__", json.dumps(feedback.preferences()))
        .replace("__GENERATED__", datetime.now().strftime("%Y-%m-%d %H:%M"))
    )
    out_path.write_text(html)
    return out_path


_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Job Search Dashboard</title>
<style>
  :root { --bg:#0f1115; --card:#181b22; --line:#262b36; --ink:#e6e9ef; --dim:#9aa3b2; --accent:#5b9dff; }
  * { box-sizing: border-box; }
  body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
  header { padding:18px 24px; border-bottom:1px solid var(--line); display:flex; flex-wrap:wrap; gap:14px; align-items:baseline; }
  h1 { font-size:18px; margin:0; }
  .meta { color:var(--dim); font-size:13px; }
  #banner { background:#3a2a12; color:#f6c177; padding:8px 24px; font-size:13px; display:none; }
  .runbar { padding:11px 24px; background:#10241a; color:#4ade80; font-size:14px; border-bottom:1px solid var(--line); }
  .runbar b { color:var(--ink); } .runbar .muted { color:var(--dim); }
  .controls { padding:14px 24px; display:flex; flex-wrap:wrap; gap:12px; align-items:center; border-bottom:1px solid var(--line); position:sticky; top:0; background:var(--bg); z-index:3; }
  input, select { background:var(--card); color:var(--ink); border:1px solid var(--line); border-radius:8px; padding:8px 10px; font-size:14px; }
  input[type=search] { min-width:220px; }
  label { color:var(--dim); font-size:13px; display:flex; gap:6px; align-items:center; }
  details.prefs { padding:10px 24px; border-bottom:1px solid var(--line); }
  details.prefs summary { cursor:pointer; color:var(--dim); font-size:13px; }
  .preflist { display:flex; flex-wrap:wrap; gap:8px; margin:10px 0; }
  .pref { background:var(--card); border:1px solid var(--line); border-radius:20px; padding:4px 10px; font-size:13px; }
  .pref button { background:none; border:none; color:var(--dim); cursor:pointer; margin-left:4px; }
  table { width:100%; border-collapse:collapse; }
  th, td { text-align:left; padding:10px 14px; border-bottom:1px solid var(--line); vertical-align:top; }
  th { color:var(--dim); font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; cursor:pointer; user-select:none; position:sticky; top:55px; background:var(--bg); }
  tr:hover td { background:#1c2029; }
  tr.applied td { opacity:.5; }
  tr.starred td { background:#1a2330; }
  .score { font-weight:700; border-radius:6px; padding:2px 9px; display:inline-block; min-width:34px; text-align:center; color:#0b0d11; }
  .s-hi { background:#4ade80; } .s-mid { background:#fbbf24; } .s-lo { background:#9aa3b2; }
  a { color:var(--accent); text-decoration:none; } a:hover { text-decoration:underline; }
  .company { color:var(--dim); font-size:13px; }
  .verdict { color:var(--dim); font-size:13px; max-width:380px; }
  .src { font-size:11px; color:var(--dim); font-family:ui-monospace,monospace; }
  .new { color:#4ade80; font-size:11px; margin-left:6px; }
  .badge { font-size:10px; padding:1px 6px; border-radius:10px; margin-left:6px; }
  .b-applied { background:#1e3a2a; color:#4ade80; } .b-star { background:#3a3416; color:#fbbf24; }
  .acts { white-space:nowrap; }
  .acts button { background:var(--card); border:1px solid var(--line); color:var(--dim); border-radius:6px; padding:4px 7px; font-size:12px; cursor:pointer; margin-right:3px; }
  .acts button:hover { color:var(--ink); border-color:var(--accent); }
  .acts button.on { color:#0b0d11; }
  .acts button.on.applied { background:#4ade80; } .acts button.on.star { background:#fbbf24; }
  .empty { padding:60px; text-align:center; color:var(--dim); }
  #count { color:var(--dim); font-size:13px; }
</style>
</head>
<body>
<div id="banner">Read-only view — run <code>uv run jobsearch-serve</code> to save Applied / Not-interested / ⭐ feedback.</div>
<header>
  <h1>Job Search Dashboard</h1>
  <span class="meta">generated __GENERATED__</span>
  <span id="count" class="meta"></span>
</header>
<div id="runbar" class="runbar"></div>
<div class="controls">
  <input id="q" type="search" placeholder="Search title, company, location, verdict…">
  <label>Min score <input id="min" type="number" value="70" min="0" max="100" style="width:64px"></label>
  <label>Source <select id="src"><option value="">all</option></select></label>
  <label><input id="newonly" type="checkbox"> New today</label>
  <label><input id="showdismissed" type="checkbox"> Show dismissed</label>
</div>
<details class="prefs">
  <summary>⚙️ Learned preferences (the agent applies these when scoring)</summary>
  <div class="preflist" id="preflist"></div>
  <input id="newpref" type="search" placeholder="e.g. Prefer hands-on AI eng over pure sales; no relocation to SF" style="min-width:420px">
  <button id="addpref" class="acts">Add</button>
</details>
<table>
  <thead><tr>
    <th data-k="score">Score</th>
    <th data-k="title">Role</th>
    <th data-k="location">Location</th>
    <th data-k="first_seen">First seen</th>
    <th data-k="verdict">Verdict</th>
    <th>Actions</th>
  </tr></thead>
  <tbody id="rows"></tbody>
</table>
<div id="empty" class="empty" hidden>No matching postings.</div>
<script>
const DATA = __DATA__;
let FEEDBACK = __FEEDBACK__;
let PREFS = __PREFS__;
const GENERATED = "__GENERATED__";
const today = new Date().toISOString().slice(0,10);
(function(){
  const n = DATA.filter(r => r.first_seen === today).length;
  document.getElementById("runbar").innerHTML =
    `📅 Last run <b>${GENERATED}</b> · ` +
    (n ? `✨ <b>${n}</b> new role${n>1?'s':''} today` : `<span class="muted">no new roles today</span>`);
})();
const API = location.protocol.startsWith("http") ? location.origin : null;
let sortKey = "score", sortAsc = false;
if (!API) document.getElementById("banner").style.display = "block";

const fkey = (c,t) => `${c.trim().toLowerCase()}||${t.trim().toLowerCase()}`;
const statusOf = (c,t) => (FEEDBACK[fkey(c,t)]||{}).status || null;
function esc(s){ return (s||"").replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c])); }
function scoreClass(s){ return s>=85?"s-hi":s>=70?"s-mid":"s-lo"; }

async function mark(c,t,status){
  const cur = statusOf(c,t);
  const next = cur===status ? "clear" : status;
  if (next==="clear") delete FEEDBACK[fkey(c,t)]; else FEEDBACK[fkey(c,t)] = {status:next, company:c, title:t};
  render();
  if (API) await fetch(API+"/api/feedback", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({company:c, title:t, status:next})});
}
async function pref(text, action){
  if (action==="add"){ if(!text||PREFS.includes(text)) return; PREFS.push(text); }
  else PREFS = PREFS.filter(p=>p!==text);
  renderPrefs();
  if (API) await fetch(API+"/api/preference", {method:"POST", headers:{"Content-Type":"application/json"},
    body: JSON.stringify({text, action})});
}

const srcSel = document.getElementById("src");
[...new Set(DATA.map(r=>r.source).filter(Boolean))].sort().forEach(s=>{
  const o=document.createElement("option"); o.value=s; o.textContent=s; srcSel.appendChild(o);
});

function renderPrefs(){
  document.getElementById("preflist").innerHTML = PREFS.length
    ? PREFS.map(p=>`<span class="pref">${esc(p)}<button onclick="pref(${JSON.stringify(p)},'remove')">×</button></span>`).join("")
    : '<span class="meta">None yet — add things you learn about what you want.</span>';
}

function render(){
  const q=document.getElementById("q").value.toLowerCase();
  const min=+document.getElementById("min").value||0;
  const src=srcSel.value;
  const newOnly=document.getElementById("newonly").checked;
  const showDis=document.getElementById("showdismissed").checked;
  let rows=DATA.filter(r=>{
    const st=statusOf(r.company,r.title);
    if (st==="dismissed" && !showDis) return false;
    return r.score>=min && (!src||r.source===src) && (!newOnly||r.first_seen===today) &&
      (!q || (r.title+" "+r.company+" "+r.location+" "+r.verdict).toLowerCase().includes(q));
  });
  rows.sort((a,b)=>{
    const sa=statusOf(a.company,a.title)==="starred"?1:0, sb=statusOf(b.company,b.title)==="starred"?1:0;
    if (sa!==sb) return sb-sa;
    let x=a[sortKey], y=b[sortKey];
    if (typeof x==="string"){ x=x.toLowerCase(); y=(y||"").toLowerCase(); }
    return (x<y?-1:x>y?1:0)*(sortAsc?1:-1);
  });
  document.getElementById("count").textContent = rows.length+" shown · "+DATA.length+" total";
  document.getElementById("empty").hidden = rows.length>0;
  document.getElementById("rows").innerHTML = rows.map(r=>{
    const st=statusOf(r.company,r.title);
    const cj=JSON.stringify(r.company), tj=JSON.stringify(r.title);
    const badge = st==="applied"?'<span class="badge b-applied">APPLIED</span>'
                : st==="starred"?'<span class="badge b-star">★</span>':'';
    return `<tr class="${st==='applied'?'applied':''} ${st==='starred'?'starred':''}">
      <td><span class="score ${scoreClass(r.score)}">${r.score}</span></td>
      <td>${r.url?`<a href="${esc(r.url)}" target="_blank" rel="noopener">${esc(r.title)}</a>`:esc(r.title)}
          ${r.first_seen===today?'<span class="new">NEW</span>':''}${badge}
          <div class="company">${esc(r.company)} · <span class="src">${esc(r.source)}</span></div></td>
      <td>${esc(r.location)}</td>
      <td>${esc(r.first_seen)}</td>
      <td class="verdict">${esc(r.verdict)}</td>
      <td class="acts">
        <button class="${st==='applied'?'on applied':''}" onclick='mark(${cj},${tj},"applied")'>✓ Applied</button>
        <button class="${st==='dismissed'?'on':''}" onclick='mark(${cj},${tj},"dismissed")'>✕ No</button>
        <button class="star ${st==='starred'?'on star':''}" onclick='mark(${cj},${tj},"starred")'>★</button>
      </td></tr>`;
  }).join("");
  document.querySelectorAll("th[data-k]").forEach(th=>th.onclick=()=>{
    if (sortKey===th.dataset.k) sortAsc=!sortAsc; else { sortKey=th.dataset.k; sortAsc=false; }
    render();
  });
}
["q","min","src","newonly","showdismissed"].forEach(id=>document.getElementById(id).addEventListener("input",render));
document.getElementById("addpref").onclick=()=>{ const el=document.getElementById("newpref"); pref(el.value.trim(),"add"); el.value=""; };
renderPrefs(); render();
</script>
</body>
</html>"""


def main() -> None:
    path = build_dashboard()
    print(f"Dashboard written to {path}")
    print(f"Open it: file://{path}")
    print("For clickable feedback: uv run jobsearch-serve")


if __name__ == "__main__":
    main()
