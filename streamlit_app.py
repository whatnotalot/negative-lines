"""
Negative Lines · Deep-Tech ML & BO Studio
Entry point for deployment on Streamlit Community Cloud (Madhav-Deep-Tech-track).
Delegates to the 11-page BoTorch / GPyTorch / Design Agent Studio in ml_bo/app/.
"""

import os
import sys
from pathlib import Path
import streamlit as st

# Configure root paths for ml_bo
_REPO_ROOT = Path(__file__).resolve().parent
_ML_BO = _REPO_ROOT / "ml_bo"
_APP_DIR = _ML_BO / "app"

for p in [str(_ML_BO), str(_APP_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

from ui import compliance_sidebar

st.set_page_config(
    page_title="Negative Lines · Deep-Tech ML & BO Studio",
    page_icon="🧪",
    layout="wide"
)

pages = {
    "Overview": [
        st.Page(str(_APP_DIR / "views/home.py"), title="Overview", icon=":material/home:", default=True),
        st.Page(str(_APP_DIR / "views/demo.py"), title="Demo tour: PFAS-reduced resist", icon=":material/play_circle:")
    ],
    "Data": [
        st.Page(str(_APP_DIR / "views/atlas.py"), title="Dataset atlas", icon=":material/dataset:"),
        st.Page(str(_APP_DIR / "views/gaps.py"), title="Data gaps & what to mine next", icon=":material/travel_explore:"),
    ],
    "Models": [
        st.Page(str(_APP_DIR / "views/rls.py"), title="RLS frontier & PFAS tax", icon=":material/scatter_plot:"),
        st.Page(str(_APP_DIR / "views/surrogate.py"), title="Surrogate lab", icon=":material/model_training:"),
        st.Page(str(_APP_DIR / "views/replay.py"), title="BO replay", icon=":material/replay:"),
    ],
    "Design": [
        st.Page(str(_APP_DIR / "views/agent.py"), title="Design agent", icon=":material/smart_toy:"),
        st.Page(str(_APP_DIR / "views/design.py"), title="Design studio", icon=":material/science:"),
        st.Page(str(_APP_DIR / "views/byod.py"), title="Bring your own patents", icon=":material/upload_file:"),
        st.Page(str(_APP_DIR / "views/anions.py"), title="PFAS-free PAG anion map", icon=":material/hub:"),
    ],
}

nav = st.navigation(pages)
compliance_sidebar()
nav.run()
