"""Agentic RFP Evaluation and Supplier Ranking - Streamlit UI.

Run locally:  streamlit run app.py
"""
from __future__ import annotations

import html
import json
import os
import re
from datetime import date

import altair as alt
import pandas as pd
import streamlit as st

from core import db
from core.evaluation_agent import PROVIDER_PRESETS, LLMConfig, LLMError
from core.orchestrator import InputValidationError, Orchestrator, SupplierInput, validate_inputs
from core.samples import BLANK_SAMPLE, SAMPLE_DIR, SAMPLE_SUPPLIERS

st.set_page_config(page_title="RFP Evaluator", page_icon="📑", layout="wide")

INK, TEAL, AMBER, RED, RULE = "#14213D", "#0F7B6C", "#B7791F", "#B42318", "#D5DCE1"
CRIT_COLORS = ["#14213D", "#0F7B6C", "#5B7A99", "#7FB7AE", "#A9B8C6", "#3D5A80", "#98C1D9"]
STATUS_LABEL = {"ok": "OK", "clipped": "Clipped", "rescaled": "Rescaled", "invalid_score": "Invalid score",
                "missing": "Missing", "ungrounded": "Evidence not found"}

st.markdown(f"""
<style>
  [data-testid="stMetricValue"], .num {{ font-variant-numeric: tabular-nums; }}
  .award {{ background:#fff; border:1px solid {RULE}; border-left:6px solid {TEAL};
           border-radius:6px; padding:22px 26px; margin:4px 0 18px; }}
  .award .kicker {{ color:{TEAL}; font-weight:600; font-size:.95rem; margin:0 0 2px; }}
  .award h2 {{ font-size:2.1rem; line-height:1.15; margin:0 0 10px; padding:0; color:{INK}; }}
  .award .figs {{ display:flex; gap:36px; flex-wrap:wrap; margin:6px 0 12px; }}
  .award .figs div {{ font-size:.85rem; color:#4A5A70; }}
  .award .figs b {{ display:block; font-size:1.6rem; color:{INK}; font-variant-numeric:tabular-nums; }}
  .award .why {{ color:#2B3A52; margin:0; max-width:75ch; }}
  .evidence {{ border-left:3px solid {TEAL}; background:#fff; padding:10px 14px; margin:6px 0 4px;
              border-radius:0 6px 6px 0; font-style:italic; max-width:85ch; }}
  .evidence.bad {{ border-left-color:{AMBER}; }}
  .chip {{ display:inline-block; padding:1px 9px; border-radius:20px; font-size:.8rem; font-weight:600;
          border:1px solid {RULE}; background:#fff; margin-right:6px; }}
  .chip.ok {{ color:{TEAL}; border-color:#9CCFC6; }} .chip.warn {{ color:{AMBER}; border-color:#E6C98F; }}
  .chip.err {{ color:{RED}; border-color:#F0B4AE; }}
</style>""", unsafe_allow_html=True)


@st.cache_resource
def _init_database() -> bool:
    db.init_db(seed=True)
    return True


_init_database()


def _secret(name: str) -> str:
    if not name:
        return ""
    try:
        value = st.secrets.get(name, "")
    except Exception:  # no secrets.toml present
        value = ""
    return value or os.environ.get(name, "")


def _secrets_hint(name: str) -> str:
    """Why the key wasn't found - names only, never values."""
    try:
        found = list(st.secrets.keys())
    except FileNotFoundError as exc:  # Streamlit also raises this for TOML syntax errors
        if "parsing" in str(exc):
            where = re.search(r"\(at line \d+, column \d+\)", str(exc))
            return ("The app's secrets are not valid TOML" + (f" {where.group(0)}" if where else "")
                    + ". Use NAME = \"value\" with straight double quotes.")
        return "No secrets are configured for this app."
    except Exception:
        return "The app's secrets could not be read: check they are valid TOML, e.g. NAME = \"value\" with quotes."
    if not found:
        return "No secrets are configured for this app."
    return f"Secrets contain {', '.join(found)} but not {name}."


def _guess_name(file_name: str) -> str:
    stem = os.path.splitext(file_name)[0]
    stem = re.sub(r"(?i)[_\- ]*(proposal|rfp|response|final|v\d+)$", "", stem)
    return re.sub(r"[_\-]+", " ", stem).strip().title() or stem


def _chip(text: str, kind: str = "") -> str:
    return f'<span class="chip {kind}">{html.escape(text)}</span>'


# ===================================================================== sidebar
with st.sidebar:
    st.subheader("AI evaluator")
    provider = st.selectbox("LLM provider", list(PROVIDER_PRESETS), index=0)
    preset = PROVIDER_PRESETS[provider]
    model = st.text_input("Model", value=preset["model"], disabled=preset["kind"] == "heuristic")
    api_key = ""
    if preset["kind"] != "heuristic":
        api_key = _secret(preset["secret"])
        if api_key:
            st.success(f"Using the API key from secrets ({preset['secret']}).")
        else:
            st.caption(_secrets_hint(preset["secret"]))
            api_key = st.text_input(f"API key ({preset['secret']})", type="password",
                                    help="Kept only in this browser session. For deployment, add it to Streamlit secrets.")
    else:
        st.info("Offline mode scores by keyword coverage so you can try the workflow without a key. "
                "Use a real LLM for genuine evaluations.")
    st.caption("Temperature is fixed at 0. The LLM only judges proposal content; every score, benchmark, "
               "PPI, tie-break and rank is computed by deterministic Python.")
    if "result" in st.session_state:
        r = st.session_state["result"]
        st.divider()
        st.caption("Showing run")
        st.code(r["rfp_run_id"], language=None)

llm_cfg = LLMConfig(provider=provider, kind=preset["kind"], model=model, api_key=api_key,
                    base_url=preset["base_url"], temperature=0.0)

st.title("RFP evaluation and supplier ranking")
st.caption("Upload supplier proposals. The AI scores each one against the live criteria with quoted evidence; "
           "Python validates the scores, benchmarks suppliers against each other and ranks them.")

tabs = st.tabs(["Criteria", "Suppliers", "Leaderboard", "Scorecards", "Run details", "History"])
tab_criteria, tab_eval, tab_board, tab_cards, tab_run, tab_history = tabs
result: dict | None = st.session_state.get("result")


def _no_run() -> None:
    st.info("No evaluation yet. Add proposals on the **Suppliers** tab and run one, "
            "or open a stored run from **History**.")


# ===================================================================== criteria
with tab_criteria:
    active = db.get_active_criteria()
    ok, total = db.check_weights(active)
    c1, c2, c3 = st.columns(3)
    c1.metric("Active criteria", len(active))
    c2.metric("Total weight", f"{total:g}%")
    c3.metric("Ready to evaluate", "Yes" if ok else "No")
    if not ok:
        st.error(f"Active weights total {total:g}%. Adjust them below so they total exactly 100%.")

    if active:
        wdf = pd.DataFrame(active)
        st.altair_chart(
            alt.Chart(wdf).mark_bar(height=34).encode(
                x=alt.X("sum(weight):Q", title="Weight (%)", scale=alt.Scale(domain=[0, max(100, total)])),
                color=alt.Color("name:N", title=None, sort=list(wdf["name"]),
                                scale=alt.Scale(range=CRIT_COLORS),
                                legend=alt.Legend(orient="top", direction="horizontal", labelLimit=220)),
                order=alt.Order("criterion_id:Q"),
                tooltip=["name", "weight", "max_score"],
            ).properties(height=40), width="stretch")

    st.dataframe(
        pd.DataFrame(active)[["criterion_id", "name", "weight", "max_score", "description"]].rename(columns={
            "criterion_id": "ID", "name": "Criterion", "weight": "Weight %", "max_score": "Max score",
            "description": "What the AI inspects"}),
        hide_index=True, width="stretch",
        column_config={"What the AI inspects": st.column_config.TextColumn(width="large")})

    with st.expander("Edit criteria"):
        st.caption("Activate, deactivate or re-weight criteria. Changes are saved to SQLite and the next run "
                   "builds its prompt from them; no code changes needed.")
        all_df = pd.DataFrame(db.get_all_criteria())
        all_df["is_active"] = all_df["is_active"].astype(bool)
        edited = st.data_editor(
            all_df, hide_index=True, width="stretch", num_rows="fixed", key="criteria_editor",
            column_config={
                "criterion_id": st.column_config.NumberColumn("ID", disabled=True),
                "name": st.column_config.TextColumn("Name", required=True),
                "description": st.column_config.TextColumn("Description", width="large", required=True),
                "weight": st.column_config.NumberColumn("Weight %", min_value=0.0, max_value=100.0, step=0.5),
                "max_score": st.column_config.NumberColumn("Max score", min_value=1, max_value=100, step=1),
                "is_active": st.column_config.CheckboxColumn("Active"),
            })
        edited_active = edited[edited["is_active"]]
        e_ok, e_total = db.check_weights(edited_active.to_dict("records"))
        (st.success if e_ok else st.warning)(f"Active weights in the editor total {e_total:g}%"
                                             + ("." if e_ok else " — they must total 100% before you can save."))
        names = edited["name"].str.strip().str.lower()
        if st.button("Save criteria", disabled=not e_ok, type="primary"):
            if names.duplicated().any() or (names == "").any():
                st.error("Criterion names must be unique and not empty.")
            else:
                db.save_criteria(edited.to_dict("records"))
                st.toast("Criteria saved")
                st.rerun()

        with st.form("add_criterion", clear_on_submit=True):
            st.markdown("**Add a criterion.** It starts inactive at 0%; activate it and rebalance above.")
            n_name = st.text_input("Name")
            n_desc = st.text_input("What should the AI inspect?")
            n_max = st.number_input("Max score", 1, 100, 10)
            if st.form_submit_button("Add criterion"):
                existing = db.get_all_criteria()
                if not n_name.strip() or not n_desc.strip():
                    st.error("Enter a name and what the AI should inspect.")
                elif n_name.strip().lower() in {c["name"].lower() for c in existing}:
                    st.error(f"A criterion named '{n_name.strip()}' already exists.")
                else:
                    new_id = max((c["criterion_id"] for c in existing), default=0) + 1
                    db.save_criteria([{"criterion_id": new_id, "name": n_name, "description": n_desc,
                                       "weight": 0.0, "max_score": int(n_max), "is_active": 0}])
                    st.rerun()


# ===================================================================== supplier input
with tab_eval:
    source = st.segmented_control("Proposals", ["Upload PDFs", "Use the bundled sample proposals"],
                                  default="Upload PDFs") or "Upload PDFs"
    suppliers: list[SupplierInput] = []

    if source == "Upload PDFs":
        files = st.file_uploader("Supplier RFP responses (PDF, select several)", type=["pdf"],
                                 accept_multiple_files=True)
        if files:
            st.markdown("**Supplier details**")
            hdr = st.columns([3, 3, 2, 2])
            for col, label in zip(hdr, ["File", "Supplier name", "Submission date", "Experience rating (0–5)"]):
                col.caption(label)
            for i, f in enumerate(files):
                c1, c2, c3, c4 = st.columns([3, 3, 2, 2])
                c1.write(f.name)
                name = c2.text_input("Supplier name", _guess_name(f.name), key=f"n_{i}_{f.name}",
                                     label_visibility="collapsed")
                sub_date = c3.date_input("Submission date", date.today(), key=f"d_{i}_{f.name}",
                                         label_visibility="collapsed", max_value=date(2100, 1, 1))
                rating = c4.number_input("Experience", 0.0, 5.0, 3.0, 0.1, key=f"r_{i}_{f.name}",
                                         label_visibility="collapsed")
                suppliers.append(SupplierInput(name, sub_date.isoformat(), rating, f.name, f.getvalue()))
    else:
        st.caption("Four fictional proposals for the Meridian Regional Water Board, each written with "
                   "different strengths, prices, schedules and gaps.")
        include_blank = st.checkbox("Also include a scanned PDF with no text (shows how errors are handled)")
        rows = SAMPLE_SUPPLIERS + ([BLANK_SAMPLE] if include_blank else [])
        st.dataframe(pd.DataFrame(rows, columns=["Supplier", "Submission date", "Experience rating", "File"]),
                     hide_index=True, width="stretch")
        for name, d, exp, fn in rows:
            with open(os.path.join(SAMPLE_DIR, fn), "rb") as fh:
                suppliers.append(SupplierInput(name, d, exp, fn, fh.read()))

    errors, warns = validate_inputs(suppliers) if suppliers else ([], [])
    active = db.get_active_criteria()
    w_ok, w_total = db.check_weights(active)
    if not w_ok:
        errors.append(f"Active criteria weights total {w_total:g}%. Fix them on the Criteria tab.")
    if llm_cfg.kind != "heuristic" and not llm_cfg.api_key:
        errors.append(f"Enter an API key for {provider} in the sidebar, or choose the offline mode.")
    for e in errors:
        st.error(e)
    for w in warns:
        st.warning(w)

    if st.button("Evaluate suppliers", type="primary", disabled=not suppliers or bool(errors)):
        with st.status("Evaluating…", expanded=True) as status:
            def on_step(step: str, detail: str) -> None:
                st.write(f"**{step}** · {detail}")
            try:
                new = Orchestrator(llm_cfg, on_step=on_step).run(suppliers)
                st.session_state["result"] = new
                status.update(label=f"{new['rfp_run_id']} finished: {new['status'].lower().replace('_', ' ')}",
                              state="complete", expanded=False)
            except InputValidationError as exc:
                status.update(label="Inputs need fixing", state="error")
                for e in exc.errors:
                    st.error(e)
            except LLMError as exc:
                status.update(label="Run stopped: the AI evaluator could not be reached", state="error")
                st.error(f"{exc}\n\nThe run is saved as FAILED. Check the API key and model, then run again.")
            except Exception as exc:  # noqa: BLE001
                status.update(label="Run failed", state="error")
                st.exception(exc)
        if st.session_state.get("result") is not result:
            st.rerun()  # redraw every tab with the new run
    if result:
        leader = result["suppliers"][0]
        st.success(f"{result['rfp_run_id']}: **{leader['supplier_name']}** ranks first "
                   f"(PPI {leader['ppi']:.2f}). Open **Leaderboard** for the full ranking.")


# ===================================================================== leaderboard
with tab_board:
    if not result:
        _no_run()
    else:
        sups = result["suppliers"]
        lead = sups[0]
        why = sups[1]["rank_reason"].split(": ", 1)[1].rstrip(".") if len(sups) > 1 else "only supplier in the run"
        runner = (f"Ahead of {sups[1]['supplier_name']}: {why}." if len(sups) > 1
                  else "Only supplier in this run, so it is compared with itself.")
        st.markdown(f"""
<div class="award">
  <p class="kicker">Recommended for award</p>
  <h2>{html.escape(lead['supplier_name'])}</h2>
  <div class="figs">
    <div><b>{lead['ppi']:.2f}</b>Peer Performance Index</div>
    <div><b>{lead['absolute_score']:.2f}</b>Absolute score / 100</div>
    <div><b>{len(sups)}</b>Suppliers compared</div>
  </div>
  <p class="why">{html.escape(runner)}</p>
</div>""", unsafe_allow_html=True)

        lb = pd.DataFrame([{
            "Rank": s["final_rank"], "Supplier": s["supplier_name"], "Absolute score": s["absolute_score"],
            "PPI": s["ppi"], "Submission date": s["submission_date"], "Experience rating": s["experience_rating"],
            "Why this rank": s.get("rank_reason", ""),
        } for s in sups])
        st.dataframe(lb, hide_index=True, width="stretch", column_config={
            "Absolute score": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100),
            "PPI": st.column_config.ProgressColumn(format="%.2f", min_value=0, max_value=100),
            "Why this rank": st.column_config.TextColumn(width="large"),
        })

        by_abs = [s["supplier_name"] for s in sorted(sups, key=lambda s: -s["absolute_score"])]
        if by_abs != [s["supplier_name"] for s in sups]:
            st.caption("Ranking by absolute score would order these suppliers differently. The brief ranks by PPI, "
                       "which rewards being close to the best offer on each criterion.")

        crit_order = [c["name"] for c in result["criteria"]]
        rows = [{"Supplier": s["supplier_name"], "Criterion": c["name"], "cidx": crit_order.index(c["name"]),
                 "Weighted points": c["weighted_points"],
                 "Relative %": c["relative_pct"], "Score": c["score"], "Benchmark": c["benchmark"]}
                for s in sups for c in s["criteria"]]
        long = pd.DataFrame(rows)
        sup_order = [s["supplier_name"] for s in sups]

        left, right = st.columns(2)
        with left:
            st.markdown("**Where each absolute score comes from**")
            st.altair_chart(alt.Chart(long).mark_bar().encode(
                y=alt.Y("Supplier:N", sort=sup_order, title=None, axis=alt.Axis(labelLimit=200)),
                x=alt.X("sum(Weighted points):Q", title="Weighted points (max 100)", scale=alt.Scale(domain=[0, 100])),
                color=alt.Color("Criterion:N", sort=crit_order, scale=alt.Scale(range=CRIT_COLORS),
                                legend=alt.Legend(orient="bottom", columns=2, title=None, labelLimit=220)),
                order=alt.Order("cidx:Q"),
                tooltip=["Supplier", "Criterion", "Score", "Weighted points"],
            ).properties(height=alt.Step(44)), width="stretch")
        with right:
            st.markdown("**Relative performance by criterion** (100 = best in the field)")
            base = alt.Chart(long).encode(
                x=alt.X("Supplier:N", sort=sup_order, title=None, axis=alt.Axis(
                    labelAngle=0, orient="top", labelOverlap=False, labelFontSize=11,
                    labelExpr="split(datum.label, ' ')")),   # one word per line so names never collide
                y=alt.Y("Criterion:N", sort=crit_order, title=None, axis=alt.Axis(labelLimit=200)))
            heat = base.mark_rect(stroke="#fff", strokeWidth=2).encode(
                color=alt.Color("Relative %:Q", scale=alt.Scale(domain=[0, 100], range=["#F3E3C3", "#7FB7AE", TEAL]),
                                legend=None),
                tooltip=["Supplier", "Criterion", "Score", "Benchmark", "Relative %"])
            text = base.mark_text(fontSize=13).encode(
                text=alt.Text("Relative %:Q", format=".0f"),
                color=alt.condition("datum['Relative %'] > 70", alt.value("#fff"), alt.value(INK)))
            st.altair_chart((heat + text).properties(height=alt.Step(44)), width="stretch")

        st.markdown("**Benchmarks** (best validated score per criterion)")
        st.dataframe(pd.DataFrame([{"Criterion": b["name"], "Benchmark score": b["benchmark_score"],
                                    "Set by": ", ".join(b["leaders"]),
                                    "Note": "No supplier scored above 0; relative % is 0 for everyone"
                                    if b["benchmark_zero"] else ""}
                                   for b in result["benchmarks"]]), hide_index=True, width="stretch")


# ===================================================================== scorecards
with tab_cards:
    if not result:
        _no_run()
    else:
        sups = result["suppliers"]
        names = [s["supplier_name"] for s in sups]
        pick = st.segmented_control("Supplier", names, default=names[0], key="card_pick") or names[0]
        s = next(x for x in sups if x["supplier_name"] == pick)

        a, b, c, d = st.columns(4)
        a.metric("Rank", f"#{s['final_rank']} of {len(sups)}")
        b.metric("PPI", f"{s['ppi']:.2f}")
        c.metric("Absolute score", f"{s['absolute_score']:.2f}")
        d.metric("Pages read", s.get("page_count", "–"))
        st.write(s.get("overall_summary", ""))
        st.caption(s.get("rank_reason", ""))

        st.dataframe(pd.DataFrame([{
            "Criterion": x["name"], "Score": f"{x['score']:g} / {x['max_score']:g}", "Benchmark": x["benchmark"],
            "Gap": x["gap"], "Relative %": x["relative_pct"], "Weight %": x["weight"],
            "Weighted pts": x["weighted_points"], "Validation": STATUS_LABEL.get(x["validation_status"],
                                                                                 x["validation_status"]),
            "Evidence page": x.get("evidence_page") or "–",
        } for x in s["criteria"]]), hide_index=True, width="stretch", column_config={
            "Relative %": st.column_config.ProgressColumn(format="%.0f", min_value=0, max_value=100)})

        st.markdown("**Evidence and reasoning, criterion by criterion**")
        for x in s["criteria"]:
            grounded = x.get("evidence_grounded")
            page = x.get("evidence_page")
            status_kind = "ok" if x["validation_status"] == "ok" else (
                "err" if x["validation_status"] in ("missing", "invalid_score") else "warn")
            with st.expander(f"{x['name']}  ·  {x['score']:g}/{x['max_score']:g}  ·  "
                             f"{x['weighted_points']:g} of {x['weight']:g} pts"):
                st.markdown(
                    _chip(STATUS_LABEL.get(x["validation_status"], x["validation_status"]), status_kind)
                    + _chip(f"Found on page {page}" if grounded and page else
                            ("Found in proposal" if grounded else "Quote not found in proposal"),
                            "ok" if grounded else "warn"), unsafe_allow_html=True)
                st.markdown(f"**Why this score.** {x['justification']}")
                quote = html.escape(x["evidence"]) if x["evidence"] else "No evidence quoted."
                st.markdown(f'<div class="evidence {"" if grounded else "bad"}">“{quote}”</div>',
                            unsafe_allow_html=True)
                st.caption(f"{x['score']:g} ÷ {x['max_score']:g} × {x['weight']:g}% weight = "
                           f"{x['weighted_points']:g} points · benchmark {x['benchmark']:g} "
                           f"({x['relative_pct']:g}% of best) · raw AI score {x.get('raw_score')!r}")

        if s.get("risks"):
            st.markdown("**Risks the evaluator raised**")
            for r in s["risks"]:
                st.markdown(f"- {r}")
        if s.get("warnings"):
            with st.expander(f"Validation notes for {pick} ({len(s['warnings'])})"):
                for w in s["warnings"]:
                    st.write(w)


# ===================================================================== run details
with tab_run:
    if not result:
        _no_run()
    else:
        sups = result["suppliers"]
        st.caption("RFP_RUN_ID")
        st.code(result["rfp_run_id"], language=None)
        m2, m3, m4 = st.columns(3)
        m2.metric("Status", result["status"].replace("_", " ").capitalize())
        m3.metric("Suppliers", len(sups))
        m4.metric("Warnings", len(result.get("warnings", [])))
        st.caption(f"Created {result['created_at']} UTC with {result['llm']['provider']} / "
                   f"{result['llm']['model']} at temperature {result['llm']['temperature']}.")

        d1, d2 = st.columns([1, 1])
        d1.download_button("Download complete result (JSON)", data=json.dumps(result, indent=2),
                           file_name=f"{result['rfp_run_id']}.json", mime="application/json", type="primary")
        d2.download_button("Download leaderboard (CSV)", file_name=f"{result['rfp_run_id']}_leaderboard.csv",
                           mime="text/csv", data=pd.DataFrame([{
                               "rank": s["final_rank"], "supplier": s["supplier_name"], "ppi": s["ppi"],
                               "absolute_score": s["absolute_score"], "submission_date": s["submission_date"],
                               "experience_rating": s["experience_rating"], "rank_reason": s.get("rank_reason")}
                               for s in sups]).to_csv(index=False))

        st.subheader("How ties were broken")
        st.markdown("Sort order: " + "  ›  ".join(f"**{i}.** {r}" for i, r in enumerate(result["tie_break_order"], 1))
                    + ". Ranks are assigned only after this stable sort.")
        for line in result["tie_break_explanation"] or ["Only one supplier, so no comparison was needed."]:
            st.markdown(f"- {line}")

        st.subheader("Warnings")
        if not result.get("warnings"):
            st.success("None. Every AI result passed validation unchanged.")
        for s in sups:
            if s.get("warnings"):
                with st.expander(f"{s['supplier_name']} ({len(s['warnings'])})"):
                    for w in s["warnings"]:
                        st.write(w)
        other = [w for w in result.get("warnings", []) if not any(w in s.get("warnings", []) for s in sups)]
        for w in other:
            st.warning(w)

        st.subheader("Audit trail")
        with st.expander("Workflow steps (each tool call in order)"):
            st.dataframe(pd.DataFrame(result.get("trace", [])), hide_index=True, width="stretch")
        with st.expander("Formulas"):
            st.json(result["formulas"])
        with st.expander("Criteria used for this run"):
            st.dataframe(pd.DataFrame(result["criteria"]), hide_index=True, width="stretch")


# ===================================================================== history
with tab_history:
    runs = db.list_runs()
    if not runs:
        st.info("No runs stored yet. Each evaluation is saved here under its RFP_RUN_ID.")
    else:
        st.dataframe(pd.DataFrame(runs), hide_index=True, width="stretch")
        run_id = st.selectbox("Stored run", [r["rfp_run_id"] for r in runs], key="hist_pick")
        stored = db.get_run_json(run_id)
        if not stored:
            st.warning("This run has no stored result because it did not finish. Its status is shown above.")
        elif st.button("Open this run", type="primary"):
            st.session_state["result"] = stored
            st.rerun()
