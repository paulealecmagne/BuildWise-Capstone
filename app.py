import os
import streamlit as st
from buildwise_core import BuildWise
from ui_form import render_project_form
from app_logic import build_dashboard_dict
from ai_explainer import generate_explanation
from dashboard import render_dashboard

st.set_page_config(page_title="BuildWise — Cost & Schedule Estimator", page_icon="🏗️", layout="wide")


def inject_custom_css():
    st.markdown(
        """
        <style>
        /* Page background & typography */
        .stApp {
            background-color: #F8FAFC;
        }

        /* Hero Banner */
        .bw-hero {
            background: linear-gradient(135deg, #1E3A5F 0%, #2B547E 100%);
            padding: 1.5rem 1.75rem;
            border-radius: 14px;
            color: #FFFFFF;
            margin-bottom: 1.25rem;
            box-shadow: 0 4px 14px rgba(30, 58, 95, 0.14);
        }
        .bw-hero h1 {
            color: #FFFFFF !important;
            font-size: 1.85rem;
            margin: 0 0 0.35rem 0;
            font-weight: 700;
        }
        .bw-hero p {
            color: #E2E8F0;
            margin: 0;
            font-size: 0.95rem;
        }
        .bw-badge {
            display: inline-block;
            background: rgba(217, 119, 6, 0.22);
            border: 1px solid #F59E0B;
            color: #FDE68A;
            padding: 0.2rem 0.65rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 0.65rem;
        }

        /* Form container card */
        [data-testid="stForm"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            box-shadow: 0 2px 8px rgba(15, 23, 42, 0.04);
        }

        /* Primary Submit Button */
        div.stFormSubmitButton > button {
            background: linear-gradient(90deg, #D97706 0%, #B45309 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 8px !important;
            padding: 0.55rem 1.4rem !important;
            font-weight: 600 !important;
            transition: transform 0.1s ease, box-shadow 0.15s ease;
        }
        div.stFormSubmitButton > button:hover {
            box-shadow: 0 4px 12px rgba(217, 119, 6, 0.35) !important;
            transform: translateY(-1px);
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-left: 4px solid #1E3A5F;
            padding: 0.85rem 1rem;
            border-radius: 10px;
            box-shadow: 0 1px 4px rgba(15, 23, 42, 0.04);
        }

        /* Explanation highlight box */
        .bw-explainer-box {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-left: 5px solid #D97706;
            border-radius: 10px;
            padding: 1.1rem 1.3rem;
            color: #1E293B;
            line-height: 1.6;
            box-shadow: 0 2px 6px rgba(15, 23, 42, 0.04);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_resource
def load_engine():
    return BuildWise(".")


def main():
    inject_custom_css()
    bw = load_engine()
    if getattr(bw, "version_warning", None):
        st.warning(bw.version_warning)

    st.markdown(
        f"""
        <div class="bw-hero">
            <h1>🏗️ BuildWise — Residential Cost & Schedule Estimator</h1>
            <p>Benchmark-calibrated PHP cost estimation, component breakdown, and illustrative CPM schedule for Philippine residential builds.</p>
            <div class="bw-badge">{bw.card["dataset_label"]}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

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

        with st.spinner("Generating cost & schedule summary..."):
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