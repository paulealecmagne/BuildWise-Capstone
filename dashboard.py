import html
import pandas as pd
import plotly.express as px
import streamlit as st
from buildwise_core import gantt_figure


def _breakdown_dataframe(result):
    """Build a display-formatted DataFrame strictly from result's breakdown_php and display.breakdown_pct."""
    pct_map = result.get("display", {}).get("breakdown_pct", {})
    rows = []
    for key, php_val in result["breakdown_php"].items():
        pct_val = pct_map.get(key)
        rows.append(
            {
                "Component": key.replace("_", " ").title(),
                "Estimated Cost (PHP)": f"PHP {int(php_val):,}",
                "Average Share (%)": f"{float(pct_val):.1f}%" if pct_val is not None else "—",
            }
        )
    return pd.DataFrame(rows)


def _breakdown_bar_chart(result):
    """Horizontal bar chart of PHP cost shares from existing result fields."""
    items = [
        {"Component": k.replace("_", " ").title(), "PHP": v}
        for k, v in result["breakdown_php"].items()
    ]
    df_chart = pd.DataFrame(items).sort_values("PHP", ascending=True)
    fig = px.bar(
        df_chart,
        x="PHP",
        y="Component",
        orientation="h",
        title="Cost Breakdown by Component (PHP — Tier & Scope Average Shares)",
        color="PHP",
        color_continuous_scale=["#93C5FD", "#1E3A5F"],
    )
    fig.update_layout(
        height=360,
        margin=dict(l=10, r=10, t=45, b=10),
        showlegend=False,
        coloraxis_showscale=False,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def render_dashboard(result, explanation_text):
    """Render cost, schedule, critical path, and explanation from a BuildWise result dict."""
    inp = result["inputs"]
    cost = result["cost"]
    dur = result["duration"]
    display_meta = result.get("display", {})

    st.divider()
    st.subheader("Project Summary")
    s1, s2, s3, s4 = st.columns(4)
    s1.metric("Project Type", inp["project_type"])
    s2.metric("Floor Area", f"{inp['floor_area_sqm']:,.1f} sqm")
    s3.metric("Storeys & Province", f"{inp['number_of_storeys']}F • {inp['province']}")
    s4.metric("Tier & Scope", f"{inp['finish_tier']} • {inp['project_scope']}")
    st.caption(f"Structure: {inp['structure_type']} | Dataset: {result['data_label']}")

    st.subheader("Key Cost & Duration Estimates")
    c1, c2, c3 = st.columns(3)
    c1.metric("Estimated Total (PHP)", f"PHP {cost['total_php']:,}")
    c2.metric("Rate / sqm (PHP)", f"PHP {cost['rate_php_per_sqm']:,}")
    c3.metric("Estimated Duration", f"{dur['weeks']} weeks")

    st.caption(
        f"80% cost range: PHP {cost['total_low_php']:,} – PHP {cost['total_high_php']:,} "
        f"(typical error on synthetic test set: {cost['typical_error_pct_on_synthetic_test']}%) | "
        f"80% duration range: {dur['weeks_low']} – {dur['weeks_high']} weeks "
        f"(typical error on synthetic test set: {dur['typical_error_pct_on_synthetic_test']}%)"
    )

    st.subheader("Cost Breakdown (Typical Share by Finish Tier & Scope — No ML)")
    tab_table, tab_chart = st.tabs(["Breakdown Table", "Component Chart"])
    with tab_table:
        st.dataframe(_breakdown_dataframe(result), width="stretch", hide_index=True)
    with tab_chart:
        st.plotly_chart(_breakdown_bar_chart(result), width="stretch")

    st.subheader("Illustrative Schedule Scaled to Predicted Duration")
    st.plotly_chart(
        gantt_figure(result["schedule"], "BuildWise Schedule (illustrative schedule)"),
        width="stretch",
    )

    cp_count = display_meta.get("critical_path_count", len(result["critical_path"]))
    st.markdown(f"**Critical Path ({cp_count} activities):** " + " → ".join(result["critical_path"]))

    float_acts = display_meta.get("top_float_activities", [])
    if float_acts:
        with st.expander("Highest-Float (Flexible) Activities"):
            for act in float_acts:
                st.write(
                    f"• **{act['activity']}** (WBS {act['wbs']}): "
                    f"{act['float_weeks']} weeks float (Weeks {act['start_week']}–{act['end_week']})"
                )

    st.subheader("Plain-Language Explanation")
    safe_text = html.escape(explanation_text).replace("\n", "<br>")
    st.markdown(f'<div class="bw-explainer-box">{safe_text}</div>', unsafe_allow_html=True)
    st.caption(
        "Reminder: Underlying dataset is synthetic (benchmark calibrated); cost breakdown uses "
        "historical tier/scope average shares; schedule is an illustrative template scaled to predicted weeks; "
        "ranges reflect ~80% cross-validation error bands—not real-world market quotes."
    )