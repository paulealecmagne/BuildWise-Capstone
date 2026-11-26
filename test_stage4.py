### 4. Stage 4 - Guardrail & Fallback Smoke Test (test_stage4.py)
import json
from pathlib import Path
from ai_explainer import deterministic_fallback, generate_explanation, numbers_pass_check

# Load example_result.json and attach the same display fields built in Stage 3
raw = json.loads(Path("example_result.json").read_text())
total_php = raw["cost"]["total_php"]
data = {
    **raw,
    "display": {
        "breakdown_pct": {
            k: round((v / total_php) * 100, 1) for k, v in raw["breakdown_php"].items()
        },
        "top_float_activities": [],
        "critical_path_count": len(raw["critical_path"]),
    },
}

# 1. Fallback text must pass the numeric check and run without an API key
fb_text, used_fb, reason = generate_explanation(data, api_key=None)
assert used_fb is True
assert numbers_pass_check(fb_text, data) is True
print("Fallback test passed:", reason)
print(fb_text)

# 2. Invented number must fail numbers_pass_check
assert numbers_pass_check("Estimated total is PHP 9,999,999 in 41 weeks.", data) is False
print("Invented-number guardrail test passed.")