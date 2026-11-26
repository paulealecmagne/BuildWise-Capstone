import streamlit as st


def render_project_form(bw):
    """Render the 7 inputs from bw.card and return (inputs_dict, live_errors, live_warnings, submitted)."""
    card = bw.card
    cats = card["categories"]

    with st.form("buildwise_project_form"):
        col1, col2 = st.columns(2)

        with col1:
            project_type = st.selectbox("Project Type", options=cats["project_type"])

            # Filter structures to options seen for the chosen project_type
            valid_structs = card["valid_structures_by_type"].get(project_type, cats["structure_type"])
            structure_type = st.selectbox("Structure Type", options=valid_structs)

            storey_options = sorted(
                set(card["valid_storeys_by_type"].get(project_type, list(range(1, 10)))) | set(range(1, 10))
            )
            storey_options = [s for s in storey_options if 1 <= s <= 9]
            number_of_storeys = st.selectbox("Number of Storeys", options=storey_options)

            area_rng = card["area_range_by_type"].get(project_type, {"min": 40.0, "max": 100000.0})
            min_area = float(area_rng["min"])
            max_area = max(float(area_rng["max"]), 100000.0)
            default_area = min(max(120.0, min_area), max_area)

            floor_area_sqm = st.number_input(
                "Floor Area (sqm)",
                min_value=min_area,
                max_value=max_area,
                value=default_area,
                step=10.0,
                help=f"Allowed range for {project_type}: {min_area:g}–{max_area:g} sqm (up to 9 storeys)",
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