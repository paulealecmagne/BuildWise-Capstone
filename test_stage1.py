### 1. Stage 1 - Core Engine Verification Script (test_stage1.py)
from buildwise_core import BuildWise, InvalidInput, gantt_figure

# Initialize the engine from the current folder
bw = BuildWise(".")
assert bw.version_warning is None, f"Version mismatch: {bw.version_warning}"

# Test A: Valid benchmark project (must match teammate's exact numbers)
valid_inputs = {
    "floor_area_sqm": 120,
    "number_of_storeys": 2,
    "project_type": "Townhouse",
    "structure_type": "Reinforced Concrete Frame with CHB Infill",
    "finish_tier": "Mid-Range",
    "project_scope": "New Complete Construction",
    "province": "Metro Manila",
}

result = bw.predict(valid_inputs)
assert result["cost"]["rate_php_per_sqm"] == 35931
assert result["cost"]["total_php"] == 4311714
assert result["duration"]["weeks"] == 41
assert sum(result["breakdown_php"].values()) == result["cost"]["total_php"]

# Verify Plotly Gantt builds without error
fig = gantt_figure(result["schedule"], "Verification Test")
assert len(fig.data) == 2

# Test B: Impossible combination (1-storey Townhouse must be blocked)
bad_inputs = {**valid_inputs, "number_of_storeys": 1}
try:
    bw.predict(bad_inputs)
    assert False, "Expected InvalidInput was not raised!"
except InvalidInput as e:
    print("Blocked as expected:", e.errors)

print("STAGE 1 PASSED: All benchmark numbers and validation rules verified.")