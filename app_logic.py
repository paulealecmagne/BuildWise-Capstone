### 3. Stage 3 - Prediction & Shared Dashboard Dictionary (app_logic.py)
from buildwise_core import InvalidInput


def build_dashboard_dict(bw, inputs):
    """Run bw.predict(inputs) and attach display-only derived fields in one dict."""
    try:
        result = bw.predict(inputs)
    except InvalidInput as exc:
        return {"ok": False, "errors": exc.errors, "warnings": [], "data": None}

    total_php = result["cost"]["total_php"]
    breakdown_pct = {
        k: round((v / total_php) * 100, 1) if total_php else 0.0
        for k, v in result["breakdown_php"].items()
    }

    float_ranked = sorted(
        [row for row in result["schedule"] if not row["critical"]],
        key=lambda r: r["float_weeks"],
        reverse=True,
    )

    dashboard_data = {
        **result,
        "display": {
            "breakdown_pct": breakdown_pct,
            "top_float_activities": float_ranked[:3],
            "critical_path_count": len(result["critical_path"]),
        },
    }
    return {"ok": True, "errors": [], "warnings": result["warnings"], "data": dashboard_data}