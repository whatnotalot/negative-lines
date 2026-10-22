"""Negative Lines · ML & BO studio. Run: streamlit run app/streamlit_app.py"""
import streamlit as st

st.set_page_config(page_title="Negative Lines · ML & BO", page_icon="🧪", layout="wide")

from ui import compliance_sidebar  # noqa: E402

pages = {
    "Overview": [st.Page("views/home.py", title="Overview", icon=":material/home:", default=True),
                 st.Page("views/demo.py", title="Demo tour: PFAS-reduced resist", icon=":material/play_circle:")],
    "Data": [
        st.Page("views/atlas.py", title="Dataset atlas", icon=":material/dataset:"),
        st.Page("views/gaps.py", title="Data gaps & what to mine next", icon=":material/travel_explore:"),
    ],
    "Models": [
        st.Page("views/rls.py", title="RLS frontier & PFAS tax", icon=":material/scatter_plot:"),
        st.Page("views/surrogate.py", title="Surrogate lab", icon=":material/model_training:"),
        st.Page("views/replay.py", title="BO replay", icon=":material/replay:"),
    ],
    "Design": [
        st.Page("views/agent.py", title="Design agent", icon=":material/smart_toy:"),
        st.Page("views/design.py", title="Design studio", icon=":material/science:"),
        st.Page("views/byod.py", title="Bring your own patents", icon=":material/upload_file:"),
        st.Page("views/anions.py", title="PFAS-free PAG anion map", icon=":material/hub:"),
    ],
}
nav = st.navigation(pages)
compliance_sidebar()
nav.run()
