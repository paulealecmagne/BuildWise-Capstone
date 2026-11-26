### 3. Wiring - Streamlit Main App Entry Point (app.py)
import os
import streamlit as st
from buildwise_core import BuildWise
from ui_form import render_project_form
from app_logic import build_dashboard_dict
from ai_explainer import generate_explanation
from dashboard import render_dashboard

st.set_page_config(page_title="BuildWise Capstone", layout="wide")


@st.cache_resource
def load_engine():
    return BuildWise(".")


def main():
    bw = load_engine()
    if getattr(bw, "version_warning", None):
        st.warning(bw.version_warning)

    st.title("BuildWise — Residential Cost & Schedule Estimator")
    st.badge(bw.card["dataset_label"])

    inputs, live_errors, live_warnings, submitted = render_project_form(bw)

    for w in live_warnings:
        st.warning(f"Warning: {w}")

    if submitted:
        if live_errors:
            for err in live_errors:
                st.error(err)
            return

        outcome = build_dashboard_dict(bw, inputs)
        if not outcome["ok"]:
            for err in outcome["errors"]:
                st.error(err)
            return

        data = outcome["data"]
        try:
            api_key = st.secrets.get("ANTHROPIC_API_KEY") or os.getenv("ANTHROPIC_API_KEY")
        except Exception:
            api_key = os.getenv("ANTHROPIC_API_KEY")
        explanation_text, used_fallback, fallback_reason = generate_explanation(data, api_key=api_key)

        st.session_state["last_run"] = {
            "data": data,
            "explanation_text": explanation_text,
            "used_fallback": used_fallback,
            "fallback_reason": fallback_reason,
        }

    if "last_run" not in st.session_state:
        st.info("Fill out the project form above and click **Estimate Cost & Schedule** to generate results.")
        return

    saved = st.session_state["last_run"]
    for w in saved["data"].get("warnings", []):
        st.warning(f"Warning: {w}")

    if saved["used_fallback"]:
        st.info(f"Using deterministic fallback ({saved['fallback_reason']}).")
    render_dashboard(saved["data"], saved["explanation_text"])


if __name__ == "__main__":
    main()