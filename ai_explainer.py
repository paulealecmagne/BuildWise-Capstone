### 4. Stage 4 - Claude Haiku Explainer, Guardrail & Fallback (ai_explainer.py)
import json
import os
import re
from anthropic import Anthropic

# Verify exact current Haiku model ID in Anthropic's docs before final submission
DEFAULT_MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = """You are BuildWise's plain-language explanation assistant for Philippine residential projects.
Rules (never break):
1. Use ONLY the numbers and facts present in the provided JSON data. Never calculate, estimate, round differently, or invent new numbers.
2. Quote key figures (total cost, 80% range, rate per sqm, duration weeks and range, top cost shares, and critical path/float highlights) accurately as given.
3. Explicitly state that the underlying dataset is SYNTHETIC ("SYNTHETIC - Benchmark Calibrated"), that cost breakdown uses average shares by tier and scope, and that the schedule is an illustrative template scaled to predicted weeks.
4. State clearly that BuildWise cannot predict real-world market prices, and never claim real-world accuracy.
5. Never give legal advice, structural safety engineering sign-off, or unverified market/price advice. If asked for those, state that it is out of scope.
6. Keep the explanation concise, clear, and easy for a homeowner or project stakeholder to read."""


def deterministic_fallback(data):
    """Plain-language summary built purely from Python numbers (no API call)."""
    inp = data["inputs"]
    cost = data["cost"]
    dur = data["duration"]
    top_share = max(data["display"]["breakdown_pct"].items(), key=lambda kv: kv[1])
    share_label = top_share[0].replace("_", " ").title()

    return (
        f"[Deterministic Summary - Fallback Mode] For a {inp['number_of_storeys']}-storey "
        f"{inp['project_type']} ({inp['floor_area_sqm']} sqm) in {inp['province']} "
        f"({inp['finish_tier']}, {inp['project_scope']}), the synthetic benchmark model estimates "
        f"PHP {cost['total_php']:,} total (80% range: PHP {cost['total_low_php']:,} to "
        f"PHP {cost['total_high_php']:,}; rate: PHP {cost['rate_php_per_sqm']:,}/sqm; "
        f"typical error on the synthetic test set: {cost['typical_error_pct_on_synthetic_test']}%). "
        f"Estimated duration is {dur['weeks']} weeks (80% range: {dur['weeks_low']} to "
        f"{dur['weeks_high']} weeks; typical error on the synthetic test set: "
        f"{dur['typical_error_pct_on_synthetic_test']}%). Largest cost component by average share "
        f"is {share_label} ({top_share[1]}%). Based on {data['data_label']}; cost breakdown uses "
        f"historical tier/scope averages and the schedule is an illustrative template—not real market prices."
    )


def _extract_allowed_numbers(data):
    """Collect numeric tokens/values present in dashboard_data (including common comma/1-dec forms)."""
    allowed = {"80"}

    def walk(obj):
        if isinstance(obj, bool):
            return
        if isinstance(obj, (int, float)):
            allowed.add(str(obj))
            if isinstance(obj, int) or float(obj).is_integer():
                val_int = int(round(float(obj)))
                allowed.add(str(val_int))
                allowed.add(f"{val_int:,}")
            else:
                val_f = float(obj)
                allowed.add(f"{val_f:.1f}")
                allowed.add(f"{val_f:.2f}")
        elif isinstance(obj, dict):
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)

    walk(data)
    return allowed


def numbers_pass_check(reply_text, data):
    """Return True if every standalone number in reply_text matches dashboard_data."""
    allowed = _extract_allowed_numbers(data)
    tokens = re.findall(r"\b\d[\d,]*(?:\.\d+)?\b", reply_text)
    for tok in tokens:
        if tok not in allowed:
            return False
    return True


def generate_explanation(data, api_key=None, model=DEFAULT_MODEL):
    """Call Claude Haiku on dashboard_data; return (text, used_fallback, reason)."""
    key = api_key or os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return deterministic_fallback(data), True, "Missing ANTHROPIC_API_KEY"

    try:
        client = Anthropic(api_key=key, timeout=15.0, max_retries=1)
        user_payload = json.dumps(data, indent=2)
        msg = client.messages.create(
            model=model,
            max_tokens=450,
            temperature=0.1,
            system=SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Explain this BuildWise estimate clearly:\n{user_payload}",
                }
            ],
        )
        reply = "".join(
            block.text for block in msg.content if getattr(block, "type", None) == "text"
        ).strip()
        if not reply:
            return deterministic_fallback(data), True, "Empty response from Claude"
        if not numbers_pass_check(reply, data):
            return deterministic_fallback(data), True, "Post-check flagged unverified number in reply"
        return reply, False, None
    except Exception as exc:
        return deterministic_fallback(data), True, f"API error: {type(exc).__name__}"