"""Standalone entry point for the Negative Lines automated engine."""

import os
import sys

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

st.set_page_config(
    page_title="Negative Lines · Automated Formulation Engine",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)

from dashboard import render_automated_dashboard  # noqa: E402

render_automated_dashboard()
