### 2. Stage 2 - Dependent Input Form Helper (ui_form.py)
import streamlit as st


def render_project_form(bw):
    """Render the 7 inputs from bw.card and return (inputs_dict, live_errors, live_warnings, submitted)."""
    card = bw.card
    cats = card["categories"]

    with st.form("buildwise_project_form"):
        col1, col2 = st.columns(2)

        with col1:
            project_type = st.selectbox("Project Type", options=cats["project_type"])

            # Filter structures and storeys to options seen for the chosen project_type
            valid_structs = card["valid_structures_by_type"].get(project_type, cats["structure_type"])
            structure_type = st.selectbox("Structure Type", options=valid_structs)

            valid_storeys = card["valid_storeys_by_type"].get(project_type, [1, 2, 3])
            number_of_storeys = st.selectbox("Number of Storeys", options=valid_storeys)

            area_rng = card["area_range_by_type"].get(project_type, {"min": 40.0, "max": 400.0})
            floor_area_sqm = st.number_input(
                "Floor Area (sqm)",
                min_value=float(area_rng["min"]),
                max_value=float(area_rng["max"]),
                value=min(max(120.0, float(area_rng["min"])), float(area_rng["max"])),
                step=1.0,
                help=f"Seen in synthetic data for {project_type}: {area_rng['min']}-{area_rng['max']} sqm",
            )

        with col2:
            project_scope = st.selectbox("Project Scope", options=cats["project_scope"])
            finish_tier = st.selectbox("Finish Tier", options=cats["finish_tier"])
            province = st.selectbox("Province", options=cats["province"])

        st.caption("Dataset status: SYNTHETIC - Benchmark Calibrated (not real project costs)")
        submitted = st.form_submit_button("Estimate Cost & Schedule", type="primary")

    inputs = {
        "floor_area_sqm": float(floor_area_sqm),
        "number_of_storeys": int(number_of_storeys),
        "project_type": project_type,
        "structure_type": structure_type,
        "finish_tier": finish_tier,
        "project_scope": project_scope,
        "province": province,
    }

    # Delegate validation to buildwise_core.py (single source of truth)
    errors, warnings = bw.validate(inputs)
    return inputs, errors, warnings, submitted