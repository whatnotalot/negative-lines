import hashlib

import pandas as pd
import streamlit as st

from ui import ROOT, page_header, rules_text, screener_for

from neglines.autocampaign import build_auto_campaign, objective_options, viability
from neglines.data import load_gold
from neglines.paths import GOLD_XLSX

page_header("Bring your own patents",
            "Drop in the extraction agent's latest workbook. Any patent whose examples vary a component or process "
            "setting and report a numeric outcome becomes a campaign automatically: surrogate, validation and BO "
            "proposals, with no new code.")

UPLOADS = ROOT / "data" / "uploads"
up = st.file_uploader("Workbook in the gold-set schema (.xlsx)", type=["xlsx"],
                      help="Needs Documents, Records, Components and Results sheets with the vocab.yaml v3 columns. "
                           "Leave empty to use the current reconciled gold set.")
path = GOLD_XLSX
if up is not None:
    UPLOADS.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(up.getvalue()).hexdigest()[:8]
    path = UPLOADS / f"{digest}_{up.name}"
    if not path.exists():
        path.write_bytes(up.getvalue())


@st.cache_resource(show_spinner="Loading workbook…")
def load(p: str):
    return load_gold(p)


try:
    g = load(str(path))
except ValueError as e:
    st.error(f"Could not load this workbook: {e}")
    st.stop()
st.caption(f"Loaded {path.name}: {g.documents.doc_id.nunique()} documents, {len(g.records)} records. "
           f"{len(g.issues)} data-quality issues found.")


@st.cache_data(show_spinner="Checking which patents can support a campaign…")
def viable(p: str) -> pd.DataFrame:
    return viability(load(p)).merge(load(p).documents[["doc_id", "applicant_or_inventor", "title"]], on="doc_id")


v = viable(str(path))
st.dataframe(v, hide_index=True, width="stretch",
             column_config={"viable": st.column_config.CheckboxColumn(),
                            "objectives_available": "numeric objectives that vary"})
docs = v[v.viable].sort_values(["factors", "experiments"], ascending=False)["doc_id"].tolist()
if not docs:
    st.warning("No patent in this workbook has a numeric outcome that varies with something it controls.")
    st.stop()

doc = st.selectbox("Patent", docs, format_func=lambda d: f"{d} · {v.set_index('doc_id').loc[d, 'applicant_or_inventor']}")
opts = objective_options(g, doc)
chosen = st.multiselect("Objectives", opts.metric_as_written.tolist(), default=opts.metric_as_written.head(2).tolist(),
                        max_selections=3)
dirs = {}
if chosen:
    cols = st.columns(len(chosen))
    for col, m in zip(cols, chosen):
        default = opts.set_index("metric_as_written").loc[m, "direction"]
        dirs[m] = col.segmented_control(m[:40], ["min", "max"], default=default, key=f"dir_{doc}_{m}",
                                        format_func={"min": "minimize", "max": "maximize"}.get) or default
if not chosen:
    st.stop()


@st.cache_resource(show_spinner="Building the campaign…")
def build(p: str, doc: str, chosen: tuple, dirs: tuple):
    return build_auto_campaign(load(p), doc, list(chosen), directions=dict(dirs))


try:
    c = build(str(path), doc, tuple(chosen), tuple(sorted(dirs.items())))
except ValueError as e:
    st.error(str(e))
    st.stop()

a, b, d = st.columns(3)
a.metric("Experiments", len(c.observed), border=True)
b.metric("Factors", len(c.factors), border=True, help=", ".join(f.label for f in c.factors))
d.metric("Candidates", f"{len(c.candidates()):,}", border=True)
with st.expander("Factors and design grid"):
    st.dataframe(pd.DataFrame([{"factor": f.label, "kind": f.kind,
                                "levels / range": ", ".join(map(str, f.levels)) if f.kind == "cat"
                                else f"{f.bounds[0]:g} to {f.bounds[1]:g}"} for f in c.factors]),
                 hide_index=True, width="stretch")


@st.cache_data(show_spinner="Leave-one-out validation…")
def validate(p, doc, chosen, dirs):
    from neglines.gp import loo_gp, transform_y
    cc = build(p, doc, chosen, dirs)
    X = cc.encode(cc.observed)
    rows = []
    for o in cc.objectives:
        r = loo_gp(X, transform_y(cc.y(o.key), o.log), cc.groups(), "additive+int")
        rows.append({"objective": o.label, "direction": o.direction, **{k: round(v, 3) for k, v in r.metrics().items()}})
    return pd.DataFrame(rows)


@st.cache_data(show_spinner="Optimizing the acquisition…")
def proposals(p, doc, chosen, dirs, q, exclude, rules):
    from neglines.bo import propose
    cc = build(p, doc, chosen, dirs)
    return propose(cc, mode="mo" if len(cc.objectives) > 1 else "scalar", q=q, exclude_blocked=exclude,
                   screener=screener_for(rules))


args = (str(path), doc, tuple(chosen), tuple(sorted(dirs.items())))
st.subheader("Surrogate validation")
st.dataframe(validate(*args), hide_index=True, width="stretch")
st.caption("Q² near or below zero means the surrogate cannot rank this objective yet; proposals for it are exploration.")

st.subheader("Proposed batch")
q1, q2 = st.columns([1, 3])
q = q1.number_input("Batch size", 1, 8, 3)
exclude = q2.toggle("Exclude candidates with blocking compliance flags", value=True)
prop = proposals(*args, int(q), exclude, rules_text())
for n in prop.notes:
    st.caption(f"ⓘ {n}")
if prop.batch.empty:
    st.error("No candidate passes the filters.")
else:
    keys = [c.scalar.key] if len(c.objectives) == 1 else [o.key for o in c.objectives]
    show_cols = ["rank"] + [f.name for f in c.factors] + [f"{k}_pred" for k in keys] + ["compliance", "nearest_record"]
    st.dataframe(prop.batch[show_cols].rename(columns={f"{k}_pred": f"{c.objective(k).label} (pred.)" for k in keys}),
                 hide_index=True, width="stretch")
    st.download_button("Proposals (.csv)", prop.batch.to_csv(index=False), file_name=f"proposals_{doc}.csv",
                       icon=":material/download:")
