"""
buildwise_core.py - the single entry point between the ML work (Phase 2) and the app (Phase 3).

    from buildwise_core import BuildWise
    bw = BuildWise("folder_with_the_saved_files")
    result = bw.predict({...7 inputs...})      # JSON-safe dict: cost, band, breakdown, weeks, schedule

IMPORTANT
- All data behind these models is SYNTHETIC. Always show result["data_label"] in the app.
- Everything here is computed by Python. The Claude layer may only EXPLAIN these numbers.
- The schedule uses an ILLUSTRATIVE template (Additional_Data.xlsx); only its logic and
  proportions are used, scaled to the ML-predicted duration.

Files needed in the folder:
    buildwise_model_card.json, buildwise_cost_model.joblib, buildwise_duration_model.joblib,
    buildwise_component_shares.csv, Additional_Data.xlsx (sheet: construction_schedule_template)
Requires: pandas, numpy, scikit-learn (same version as in the model card), joblib, openpyxl.
plotly is only needed for gantt_figure().
"""
import json
import warnings
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

FILES = {
    "card": "buildwise_model_card.json",
    "cost_model": "buildwise_cost_model.joblib",
    "duration_model": "buildwise_duration_model.joblib",
    "shares": "buildwise_component_shares.csv",
    "template": "Additional_Data.xlsx",
}
TEMPLATE_SHEET = "construction_schedule_template"

NUM_COLS = ["floor_area_sqm", "number_of_storeys"]
CAT_COLS = ["project_type", "structure_type", "finish_tier", "project_scope", "province"]

# True  -> combinations never seen in the data are BLOCKED (errors)
# False -> they only produce a warning
STRICT_COMBINATIONS = False
MIN_PROVINCE_ROWS = 30
MAX_STOREYS = 9
MAX_FLOOR_AREA_SQM = 100000.0

# Which template activities (WBS numbers) apply to each scope. ASSUMPTION agreed in the project.
SCOPE_ACTIVITIES = {
    "New Complete Construction": list(range(1, 17)),
    "Turnkey Construction with Basic Site Works": list(range(1, 17)),
    "House Extension or Additional Floor": list(range(1, 17)),
    "Shell and Core": list(range(1, 12)),
    "Major Renovation or Fit-Out": [1, 2, 9, 10, 11, 12, 13, 14, 15, 16],
}


class InvalidInput(ValueError):
    """Raised when the form values break a validation rule. .errors holds readable messages."""

    def __init__(self, errors):
        super().__init__("; ".join(errors))
        self.errors = errors


class BuildWise:
    def __init__(self, folder=None):
        folder = Path(folder) if folder else Path(__file__).resolve().parent
        self.card = json.loads((folder / FILES["card"]).read_text())
        self.cost_model = joblib.load(folder / FILES["cost_model"])
        self.duration_model = joblib.load(folder / FILES["duration_model"])
        self.shares = pd.read_csv(folder / FILES["shares"], index_col=[0, 1])
        self.tmpl = self._load_template(folder / FILES["template"])

        import sklearn
        self.version_warning = None
        if sklearn.__version__ != self.card.get("sklearn_version"):
            self.version_warning = (f"scikit-learn {sklearn.__version__} differs from the version used "
                                    f"to train ({self.card.get('sklearn_version')}); install the same version.")
            warnings.warn(self.version_warning)

    # ------------------------------------------------------------------ validation
    def validate(self, inputs):
        """Return (errors, warnings). Errors must block the estimate; warnings are shown to the user."""
        errors, warns = [], []
        card = self.card

        missing = [c for c in NUM_COLS + CAT_COLS if inputs.get(c) in (None, "")]
        if missing:
            return [f"Missing: {', '.join(missing)}"], warns

        for c in CAT_COLS:
            if inputs[c] not in card["categories"][c]:
                errors.append(f"Unknown {c}: {inputs[c]!r}")
        try:
            area = float(inputs["floor_area_sqm"])
            storeys_f = float(inputs["number_of_storeys"])
            storeys = int(storeys_f)
            if storeys != storeys_f:
                raise ValueError
        except (TypeError, ValueError):
            errors.append("floor_area_sqm must be a number and number_of_storeys a whole number")
        if errors:
            return errors, warns

        ptype, struct = inputs["project_type"], inputs["structure_type"]

        if storeys < 1 or storeys > MAX_STOREYS:
            errors.append(f"number_of_storeys must be between 1 and {MAX_STOREYS}; got {storeys}")
        if area > MAX_FLOOR_AREA_SQM + 0.05:
            errors.append(f"floor_area_sqm must be at most {MAX_FLOOR_AREA_SQM:g} sqm; got {area}")

        rng = card["area_range_by_type"][ptype]
        if not (rng["min"] - 0.05 <= area <= rng["max"] + 0.05):
            errors.append(f"{ptype} floor area must be between {rng['min']} and {rng['max']} sqm "
                          f"(range seen in the data); got {area}")

        problems = []
        if storeys not in card["valid_storeys_by_type"][ptype]:
            problems.append(f"{ptype} with {storeys} storey(s) never appears in the data "
                            f"(seen: {card['valid_storeys_by_type'][ptype]})")
        if struct not in card["valid_structures_by_type"][ptype]:
            problems.append(f"{struct} never appears on a {ptype} in the data")
        if storeys not in card["valid_storeys_by_structure"][struct]:
            problems.append(f"{struct} with {storeys} storey(s) never appears in the data "
                            f"(seen: {card['valid_storeys_by_structure'][struct]})")
        (errors if STRICT_COMBINATIONS else warns).extend(problems)

        seen = card.get("seen_combinations")
        if seen and not problems and [ptype, struct, storeys] not in seen:
            warns.append("This exact combination of project type, structure and storeys never appears "
                         "in the training data; treat the estimate with extra caution.")

        counts = card.get("province_counts")
        if counts and counts.get(inputs["province"], 0) < MIN_PROVINCE_ROWS:
            warns.append(f"Only {counts.get(inputs['province'], 0)} projects from {inputs['province']} "
                         f"in the data; the location effect is uncertain.")
        return errors, warns

    # ------------------------------------------------------------------ prediction
    def predict(self, inputs):
        errors, warns = self.validate(inputs)
        if errors:
            raise InvalidInput(errors)

        area = float(inputs["floor_area_sqm"])
        row = pd.DataFrame([{
            "floor_area_sqm": area,
            "number_of_storeys": int(float(inputs["number_of_storeys"])),
            **{c: inputs[c] for c in CAT_COLS},
        }])
        tier, scope = inputs["finish_tier"], inputs["project_scope"]

        # --- cost (log cost per sqm -> rate -> total) with an 80% range from CV residuals
        rate = float(np.exp(self.cost_model.predict(row)[0]))
        total = round(rate * area)
        q10, q90 = self.card["band_log_q10_q90"]

        # --- duration (log weeks -> weeks) with an 80% range from CV residuals
        weeks_raw = float(np.exp(self.duration_model.predict(row)[0]))
        weeks = max(1, int(round(weeks_raw)))
        dq10, dq90 = self.card["duration_model"]["band_log_q10_q90"]

        breakdown = self._breakdown(total, tier, scope)
        schedule = self.build_schedule(weeks, scope)

        return {
            "data_label": self.card["dataset_label"],
            "inputs": {k: inputs[k] for k in NUM_COLS + CAT_COLS},
            "warnings": warns,
            "cost": {
                "rate_php_per_sqm": round(rate),
                "total_php": total,
                "total_low_php": round(total * float(np.exp(q10))),
                "total_high_php": round(total * float(np.exp(q90))),
                "typical_error_pct_on_synthetic_test": round(self.card["test_metrics"]["MAPE_pct"], 1),
            },
            "breakdown_php": breakdown,
            "duration": {
                "weeks": weeks,
                "weeks_low": max(1, int(round(weeks_raw * float(np.exp(dq10))))),
                "weeks_high": int(round(weeks_raw * float(np.exp(dq90)))),
                "typical_error_pct_on_synthetic_test": round(self.card["duration_model"]["test_mape_pct"], 1),
            },
            "schedule": schedule.round(1).to_dict("records"),
            "critical_path": schedule.loc[schedule["critical"], "activity"].tolist(),
        }

    # ------------------------------------------------------------------ breakdown (no ML)
    def _breakdown(self, total_php, tier, scope):
        row = self.shares.loc[(tier, scope)]
        parts = (row * total_php).round(0)
        parts.iloc[-1] += total_php - parts.sum()          # rounding remainder goes to the last part
        return {k: int(v) for k, v in parts.items()}

    # ------------------------------------------------------------------ schedule (rule-based CPM)
    @staticmethod
    def _load_template(path):
        t = pd.read_excel(path, sheet_name=TEMPLATE_SHEET)
        t["wbs"] = t["wbs"].astype(int)
        t["preds"] = t["predecessor_wbs"].apply(
            lambda s: [] if pd.isna(s) else [int(float(x)) for x in str(s).split(";")])
        t["mid_days"] = (t["duration_min_workdays"] + t["duration_max_workdays"]) / 2
        assert all(p < w for w, ps in zip(t["wbs"], t["preds"]) for p in ps)
        return t

    def _run_cpm(self, keep):
        keep = set(keep)
        info = self.tmpl.set_index("wbs")

        def kept_preds(w):                                   # reconnect around removed activities
            out, stack = set(), list(info.loc[w, "preds"])
            while stack:
                p = stack.pop()
                if p in keep:
                    out.add(p)
                else:
                    stack += info.loc[p, "preds"]
            return out

        preds = {w: kept_preds(w) for w in keep}
        dur = info["mid_days"].to_dict()

        es, ef = {}, {}
        for w in sorted(keep):                               # forward pass
            es[w] = max((ef[p] for p in preds[w]), default=0)
            ef[w] = es[w] + dur[w]
        total = max(ef.values())

        succs = {w: [v for v in keep if w in preds[v]] for w in keep}
        ls = {}
        for w in sorted(keep, reverse=True):                 # backward pass
            lf = min((ls[s] for s in succs[w]), default=total)
            ls[w] = lf - dur[w]

        out = pd.DataFrame({"wbs": sorted(keep)})
        out["es_days"] = out["wbs"].map(es)
        out["dur_days"] = out["wbs"].map(dur)
        out["float_days"] = out["wbs"].map(lambda w: ls[w] - es[w])
        out["critical"] = np.isclose(out["float_days"], 0)
        return out, total

    def build_schedule(self, total_weeks, scope):
        cpm, total_days = self._run_cpm(SCOPE_ACTIVITIES[scope])
        k = total_weeks / total_days                         # weeks per template workday
        s = cpm.merge(self.tmpl[["wbs", "activity"]], on="wbs")
        s["start_week"] = s["es_days"] * k
        s["duration_weeks"] = s["dur_days"] * k
        s["end_week"] = s["start_week"] + s["duration_weeks"]
        s["float_weeks"] = s["float_days"] * k
        return s[["wbs", "activity", "start_week", "duration_weeks", "end_week",
                  "float_weeks", "critical"]]


def gantt_figure(schedule_records, title="Project schedule"):
    """Plotly Gantt from result['schedule']. Red = critical path, blue = has float."""
    import plotly.graph_objects as go
    s = pd.DataFrame(schedule_records)
    fig = go.Figure()
    for is_crit, name, color in [(True, "Critical path", "#d62728"), (False, "Has float (slack)", "#1f77b4")]:
        part = s[s["critical"] == is_crit]
        fig.add_trace(go.Bar(
            y=part["activity"], x=part["duration_weeks"], base=part["start_week"], orientation="h",
            name=name, marker_color=color,
            customdata=part[["float_weeks"]].to_numpy(),
            hovertemplate="%{y}<br>Duration: %{x:.1f} wk<br>Float: %{customdata[0]:.1f} wk<extra></extra>"))
    fig.update_yaxes(autorange="reversed", categoryorder="array", categoryarray=s["activity"].tolist())
    fig.update_xaxes(title="Project week")
    fig.update_layout(title=f"{title} (illustrative schedule)", height=520, barmode="overlay")
    return fig


if __name__ == "__main__":
    bw = BuildWise()
    demo = {"floor_area_sqm": 120, "number_of_storeys": 2, "project_type": "Townhouse",
            "structure_type": "Reinforced Concrete Frame with CHB Infill", "finish_tier": "Mid-Range",
            "project_scope": "New Complete Construction", "province": "Metro Manila"}
    print(json.dumps(bw.predict(demo), indent=2))