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
        @keyframes bwFadeSlideUp {
            from {
                opacity: 0;
                transform: translateY(10px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes bwPulseGlow {
            0%, 100% {
                box-shadow: 0 4px 14px rgba(217, 119, 6, 0.28);
            }
            50% {
                box-shadow: 0 6px 20px rgba(217, 119, 6, 0.45);
            }
        }

        /* Higher-contrast architectural slate canvas */
        .stApp, [data-testid="stAppViewContainer"], .main {
            background-color: #E6ECF5 !important;
        }

        /* Hero Banner */
        .bw-hero {
            background: linear-gradient(135deg, #0F2942 0%, #1E3A5F 55%, #2B547E 100%);
            padding: 1.6rem 1.85rem;
            border-radius: 16px;
            color: #FFFFFF;
            margin-bottom: 1.25rem;
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: 0 10px 24px rgba(15, 41, 66, 0.18);
            animation: bwFadeSlideUp 0.45s ease-out both;
        }
        .bw-hero h1 {
            color: #FFFFFF !important;
            font-size: 1.9rem;
            margin: 0 0 0.4rem 0;
            font-weight: 700;
            letter-spacing: -0.01em;
        }
        .bw-hero p {
            color: #DCE6F2;
            margin: 0;
            font-size: 0.96rem;
        }
        .bw-badge {
            display: inline-block;
            background: rgba(245, 158, 11, 0.2);
            border: 1px solid #FBBF24;
            color: #FEF3C7;
            padding: 0.25rem 0.75rem;
            border-radius: 999px;
            font-size: 0.78rem;
            font-weight: 600;
            margin-top: 0.75rem;
        }

        /* Form container card */
        [data-testid="stForm"] {
            background-color: #FFFFFF;
            border: 1.5px solid #CBD5E1;
            border-radius: 14px;
            padding: 1.35rem 1.6rem;
            box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
            animation: bwFadeSlideUp 0.55s ease-out both;
        }

        /* Primary Submit Button */
        div.stFormSubmitButton > button {
            background: linear-gradient(90deg, #D97706 0%, #B45309 100%) !important;
            color: #FFFFFF !important;
            border: none !important;
            border-radius: 9px !important;
            padding: 0.6rem 1.5rem !important;
            font-weight: 600 !important;
            animation: bwPulseGlow 2.8s infinite ease-in-out;
            transition: transform 0.15s ease, filter 0.15s ease;
        }
        div.stFormSubmitButton > button:hover {
            transform: translateY(-2px) scale(1.01);
            filter: brightness(1.06);
        }

        /* Metric cards */
        [data-testid="stMetric"] {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-left: 5px solid #1E3A5F;
            padding: 0.9rem 1.05rem;
            border-radius: 12px;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.06);
            animation: bwFadeSlideUp 0.5s ease-out both;
            transition: transform 0.15s ease, box-shadow 0.15s ease;
        }
        [data-testid="stMetric"]:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 18px rgba(15, 23, 42, 0.1);
        }

        /* Tab & dataframe containers */
        [data-testid="stDataFrame"], .stPlotlyChart {
            background-color: #FFFFFF;
            border: 1px solid #CBD5E1;
            border-radius: 12px;
            padding: 0.5rem;
            box-shadow: 0 4px 12px rgba(15, 23, 42, 0.05);
            animation: bwFadeSlideUp 0.55s ease-out both;
        }

        /* Explanation highlight box */
        .bw-explainer-box {
            background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 100%);
            border: 1px solid #94A3B8;
            border-left: 6px solid #D97706;
            border-radius: 12px;
            padding: 1.15rem 1.35rem;
            color: #0F172A;
            line-height: 1.65;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.07);
            animation: bwFadeSlideUp 0.6s ease-out both;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _get_anthropic_api_key():
    try:
        if "ANTHROPIC_API_KEY" in st.secrets:
            val = st.secrets["ANTHROPIC_API_KEY"]
            if val:
                return str(val).strip()
    except Exception:
        pass
    env_val = os.getenv("ANTHROPIC_API_KEY")
    return env_val.strip() if env_val else None


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
        api_key = _get_anthropic_api_key()

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

    render_dashboard(saved["data"], saved["explanation_text"])


if __name__ == "__main__":
    main()