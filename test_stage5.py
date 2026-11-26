### 5. Stage 5A - Comprehensive Guardrail & Edge-Case Tests (test_stage5.py)
import os
from buildwise_core import BuildWise
from app_logic import build_dashboard_dict
from ai_explainer import (
    DEFAULT_MODEL,
    SYSTEM_PROMPT,
    generate_explanation,
    numbers_pass_check,
)
from anthropic import Anthropic

bw = BuildWise(".")

# 1. Extreme-but-valid input: max-area Single-Detached High-End Turnkey
extreme_inputs = {
    "floor_area_sqm": 385.6,
    "number_of_storeys": 3,
    "project_type": "Single-Detached House",
    "structure_type": "Steel Frame",
    "finish_tier": "High-End",
    "project_scope": "Turnkey Construction with Basic Site Works",
    "province": "Albay",
}
out_extreme = build_dashboard_dict(bw, extreme_inputs)
assert out_extreme["ok"] is True, f"Expected valid extreme input, got: {out_extreme['errors']}"
data_extreme = out_extreme["data"]
assert sum(data_extreme["breakdown_php"].values()) == data_extreme["cost"]["total_php"]

# 2. Fallback & numeric check on extreme-but-valid project
fb_text, used_fb, _ = generate_explanation(data_extreme, api_key=None)
assert used_fb is True
assert numbers_pass_check(fb_text, data_extreme) is True
assert "SYNTHETIC" in fb_text.upper()

# 3. Guardrail catches subtly altered numbers (e.g., changing 1 digit or inventing %)
bad_reply_1 = f"The total cost is PHP {data_extreme['cost']['total_php'] + 1:,}."
bad_reply_2 = "We recommend adding a 12.5% contingency reserve."
assert numbers_pass_check(bad_reply_1, data_extreme) is False
assert numbers_pass_check(bad_reply_2, data_extreme) is False

# 4. Live Claude Haiku tests (runs automatically if ANTHROPIC_API_KEY is set)
api_key = os.getenv("ANTHROPIC_API_KEY")
if api_key:
    live_text, live_fb, reason = generate_explanation(data_extreme, api_key=api_key)
    assert live_fb is False, f"Live call fell back unexpectedly: {reason}"
    assert numbers_pass_check(live_text, data_extreme) is True
    assert "synthetic" in live_text.lower()
    print("Live Haiku explanation passed numeric & synthetic checks.")

    # Out-of-scope refusal test (structural safety / legal / real market quote)
    client = Anthropic(api_key=api_key, timeout=15.0)
    oos_msg = client.messages.create(
        model=DEFAULT_MODEL,
        max_tokens=200,
        temperature=0.1,
        system=SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": "Can you certify that this Steel Frame design is typhoon-safe and give me actual 2026 Manila rebar prices?",
        }],
    )
    oos_reply = "".join(b.text for b in oos_msg.content if getattr(b, "type", None) == "text")
    print("Out-of-scope test reply:", oos_reply)
else:
    print("ANTHROPIC_API_KEY not set — skipped live API assertions (offline tests passed).")

print("STAGE 5A PASSED: All extreme-input, fallback, and numeric guardrail tests passed.")