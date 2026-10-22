"""Shared theme tokens, chart styling and cached loaders for the Streamlit app."""
from __future__ import annotations

import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402
import plotly.graph_objects as go  # noqa: E402
import streamlit as st  # noqa: E402

# reference palette (dataviz skill references/palette.md); slots 1-3 validate all-pairs in both modes
LIGHT = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
             axis="#c3c2b7", s1="#2a78d6", s2="#eb6834", s3="#1baf7a", band1="rgba(42,120,214,0.16)",
             band2="rgba(235,104,52,0.16)", seq=["#cde2fb", "#86b6ef", "#3987e5", "#1c5cab", "#0d366b"])
DARK = dict(surface="#1a1a19", ink="#f0efec", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
            axis="#383835", s1="#3987e5", s2="#d95926", s3="#199e70", band1="rgba(57,135,229,0.22)",
            band2="rgba(217,89,38,0.22)", seq=["#184f95", "#1c5cab", "#2a78d6", "#5598e7", "#9ec5f4"])
# status palette is reserved for compliance state and always ships with a symbol + label
STATUS = {"block": "#d03b3b", "penalize": "#ec835a", "watch": "#fab219", "clear": "#0ca30c",
          "unverified": "#898781"}
STATUS_LABEL = {"block": "✕ Block: PFAS / restricted", "penalize": "▲ Penalize: SVHC",
                "watch": "◆ Watch", "clear": "✓ Clear", "unverified": "? Structure unverified"}
STATUS_SYMBOL = {"block": "x", "penalize": "triangle-up", "watch": "diamond", "clear": "circle",
                 "unverified": "circle-open"}
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def tokens() -> dict:
    try:
        return DARK if st.context.theme.type == "dark" else LIGHT
    except Exception:
        return LIGHT


def style(fig: go.Figure, height: int = 380, legend: bool = True, **layout) -> go.Figure:
    t = tokens()
    axis = dict(gridcolor=t["grid"], linecolor=t["axis"], zeroline=False, showline=True, automargin=True,
                showticklabels=True, tickfont=dict(color=t["muted"], size=12),
                title_font=dict(color=t["ink2"], size=13), title_standoff=8,
                ticks="outside", tickcolor=t["axis"], ticklen=4)
    fig.update_layout(
        height=height, font=dict(family=FONT, color=t["ink2"], size=13),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=64, r=24, t=40 if legend else 16, b=56),
        hoverlabel=dict(bgcolor=t["surface"], bordercolor=t["axis"], font=dict(color=t["ink"], family=FONT)),
        showlegend=legend,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0, traceorder="normal",
                    font=dict(color=t["ink2"]), bgcolor="rgba(0,0,0,0)"),
        **layout,
    )
    fig.update_xaxes(**axis)
    fig.update_yaxes(**axis)
    return fig


def show(fig: go.Figure, data: pd.DataFrame | None = None, key: str | None = None, caption: str | None = None):
    st.plotly_chart(fig, theme=None, key=key, config={"displaylogo": False, "displayModeBar": "hover"})
    if caption:
        st.caption(caption)
    if data is not None:
        with st.expander("Data table"):
            st.dataframe(data, hide_index=True, width="stretch")


def marker(color: str, size: int = 10, symbol: str = "circle") -> dict:
    return dict(color=color, size=size, symbol=symbol, line=dict(width=2, color=tokens()["surface"]))


def status_marker(sev: str, size: int = 11) -> dict:
    sym = STATUS_SYMBOL.get(sev, "circle")
    m = dict(color=STATUS[sev], size=size, symbol=sym)
    m["line"] = dict(width=2, color=STATUS[sev] if sym.endswith("open") or sym == "x" else tokens()["surface"])
    return m


def page_header(title: str, lede: str):
    st.title(title)
    st.markdown(f"<p style='font-size:1.05rem;opacity:.8;margin-top:-.6rem'>{lede}</p>", unsafe_allow_html=True)


# ---- compliance source (shared by every page) ------------------------------------------------------
def compliance_sidebar():
    with st.sidebar:
        st.markdown("**Compliance rules**")
        up = st.file_uploader("Team compliance agent rules (.csv)", type=["csv"], key="rules_csv",
                              help="Same columns as the template. These rules are checked first; built-in rules "
                                   "cover everything else.")
        if up is not None:
            st.session_state["rules_text"] = up.getvalue().decode("utf-8")
        if st.session_state.get("rules_text"):
            st.caption("Using built-in rules + uploaded team rules.")
            if st.button("Remove uploaded rules", key="rm_rules"):
                st.session_state.pop("rules_text", None)
                st.rerun()
        else:
            st.caption("Using built-in rules.")
        from neglines.compliance import rules_table
        st.download_button("Rules template (.csv)", rules_table().to_csv(index=False),
                           file_name="compliance_rules_template.csv", key="rules_tpl")


def rules_text() -> str:
    """Uploaded rules CSV text if it parses, else '' (built-in rules), with the error shown in the sidebar."""
    text = st.session_state.get("rules_text", "")
    if not text:
        return ""
    try:
        screener_for(text)
        return text
    except ValueError as e:
        st.sidebar.error(f"Rules file rejected, using built-in rules: {e}")
        return ""


@st.cache_resource(show_spinner=False)
def screener_for(text: str):
    """Screener for the given rules CSV text ('' = built-in rules only). Cached per rules text."""
    import io

    from neglines.compliance import DefaultScreener, TableScreener
    return TableScreener(io.StringIO(text)) if text else DefaultScreener()


def active_screener():
    return screener_for(rules_text())


# ---- cached loaders -----------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def gold():
    from neglines.data import load_gold
    return load_gold()


@st.cache_resource(show_spinner=False)
def campaign(key: str):
    from neglines.campaigns import get_campaign
    return get_campaign(key)


@st.cache_data(show_spinner=False)
def record_compliance() -> pd.DataFrame:
    from neglines.compliance import screen_records
    g = gold()
    return screen_records(g.components, g.records)


@st.cache_data(show_spinner=False)
def component_flags() -> pd.DataFrame:
    from neglines.compliance import flag_table
    g = gold()
    return flag_table(g.components, g.records)


@st.cache_data(show_spinner=False)
def replay_traces() -> pd.DataFrame | None:
    p = ROOT / "results" / "replay" / "traces.csv"
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(show_spinner=False)
def replay_summary() -> pd.DataFrame | None:
    p = ROOT / "results" / "replay" / "summary.csv"
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(show_spinner=False)
def cv_metrics() -> pd.DataFrame | None:
    p = ROOT / "results" / "cv" / "metrics.csv"
    return pd.read_csv(p) if p.exists() else None


@st.cache_data(show_spinner=False)
def cv_predictions() -> pd.DataFrame | None:
    p = ROOT / "results" / "cv" / "predictions.csv"
    return pd.read_csv(p) if p.exists() else None


CAMPAIGN_LABELS = {"euv": "EUV · TOK", "ebeam": "E-beam · FUJIFILM", "su8": "SU-8 · FormFactor"}
MODEL_LABELS = {"additive": "GP additive", "additive+int": "GP additive + interactions", "ard": "GP ARD (standard)",
                "rf": "Random forest", "mean": "Mean baseline"}
STRATEGY_LABELS = {"bo": "Bayesian optimization", "random": "Random order", "patent_order": "Patent's own order"}


def bo_savings() -> pd.DataFrame | None:
    s = replay_summary()
    if s is None:
        return None
    med = s.groupby(["campaign", "mode", "strategy"])["experiments_to_target"].median().unstack()
    med["saved_vs_random"] = 1 - med["bo"] / med["random"]
    return med.reset_index()
