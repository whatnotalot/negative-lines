import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from ui import STATUS, STATUS_SYMBOL, gold, page_header, show, status_marker, style, tokens

from neglines.anions import describe, library_table, substitutes

t = tokens()
page_header("PFAS-free PAG anion map",
            "Where fluorinated photoacid-generator anions sit, and which fluorine-free anions come closest. "
            "Every value is computed from the structure. Nothing here is fit to the gold set, because it holds no PAG "
            "structures yet.")

lib = st.cache_data(library_table)()
STATUS_OF = {"PFAS (OECD 2021)": "block", "fluorinated, not PFAS": "watch", "fluorine-free": "clear"}
plot = lib[lib.ewg_pull.notna()].copy()
plot["sev"] = plot.status.map(STATUS_OF)

ref_opts = plot[plot.pfas_oecd].anion.tolist()
c1, c2 = st.columns([2, 1])
ref = c1.selectbox("Fluorinated anion to replace", ref_opts, index=ref_opts.index("nonaflate (PFBS)"))
allow_f = c2.toggle("Allow fluorinated non-PFAS (aryl-F)", value=False)

fig = go.Figure()
for status, sev in STATUS_OF.items():
    grp = plot[plot.sev == sev]
    fig.add_scatter(x=grp.size_ASA, y=grp.ewg_pull, mode="markers", name=status, marker=status_marker(sev, 12),
                    customdata=grp[["anion", "class", "smiles", "note"]],
                    hovertemplate="<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}<br>size %{x:.0f} Å² · "
                                  "pull %{y:.2f}<br>%{customdata[3]}<extra></extra>")
r = plot[plot.anion == ref].iloc[0]
subs = substitutes(lib, ref, k=5, allow_fluorine=allow_f)
for _, s in subs.iterrows():
    fig.add_scatter(x=[r.size_ASA, s.size_ASA], y=[r.ewg_pull, s.ewg_pull], mode="lines",
                    line=dict(color=t["axis"], width=1), hoverinfo="skip", showlegend=False)
labels = pd.concat([plot[plot.anion == ref], subs.head(3)])
offsets = [(0, -34), (70, -46), (-90, -40), (40, 40)]
for (_, s), (ax, ay) in zip(labels.iterrows(), offsets):
    fig.add_annotation(x=s.size_ASA, y=s.ewg_pull, text=s.anion, showarrow=True, arrowhead=0, arrowwidth=1,
                       arrowcolor=t["axis"], ax=ax, ay=ay, bgcolor=t["surface"], borderpad=2,
                       font=dict(color=t["ink"] if s.anion == ref else t["ink2"], size=11))
style(fig, height=460, xaxis_title="Anion size, Labute ASA (Å²): larger diffuses less, better LER",
      yaxis_title="Electron-withdrawing pull at the acid site: stronger acid, faster")
show(fig, plot[["anion", "class", "status", "size_ASA", "ewg_pull", "n_F", "smiles"]], key="anionmap")

gap = r.ewg_pull - subs.ewg_pull.max() if len(subs) else float("nan")
st.markdown(f"**Closest PFAS-free substitutes for {ref}.** The best candidate's acid-site pull is "
            f"{subs.ewg_pull.max():.2f} against {r.ewg_pull:.2f} for {ref}. That gap is the PFAS tax in molecular "
            "terms: expect lower sensitivity unless the cation, quencher loading or an acid amplifier compensates.")
st.dataframe(subs[["anion", "class", "size_ASA", "ewg_pull", "distance", "smiles", "note"]], hide_index=True,
             width="stretch", column_config={"distance": st.column_config.NumberColumn(format="%.2f"),
                                             "size_ASA": st.column_config.NumberColumn("size (Å²)", format="%.0f"),
                                             "ewg_pull": st.column_config.NumberColumn("pull", format="%.2f")})
st.caption("Nitroarene sulfonates absorb strongly and raise their own toxicity questions. Send every candidate "
           "through the compliance agent before testing.")

st.subheader("Screen your own structure")
smi = st.text_input("SMILES of a PAG anion or any component", "CC1(C)C2CCC1(CS(=O)(=O)[O-])C(=O)C2")
dsc = describe(smi) if smi else None
if dsc is None:
    st.warning("RDKit could not parse that SMILES.")
else:
    verdict = "PFAS under the OECD 2021 definition" if dsc["pfas_oecd"] else (
        "fluorinated but not PFAS under OECD 2021" if dsc["n_F"] else "fluorine-free")
    sev = "block" if dsc["pfas_oecd"] else ("watch" if dsc["n_F"] else "clear")
    a, b, c = st.columns(3)
    a.metric("OECD 2021 screen", {"block": "✕ PFAS", "watch": "◆ F, not PFAS", "clear": "✓ fluorine-free"}[sev],
             border=True, help=verdict)
    b.metric("Size (Å²)", f"{dsc['size_ASA']:.0f}", border=True)
    c.metric("Acid-site pull", "n/a" if pd.isna(dsc["ewg_pull"]) else f"{dsc['ewg_pull']:.2f}", border=True)
    st.caption(f"Canonical SMILES: `{dsc['smiles']}` · {dsc['n_F']} F atoms · MW {dsc['mw']:.1f}"
               + (f" · contains {dsc['metal']}" if dsc["metal"] else ""))
