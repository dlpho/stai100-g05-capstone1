"""
Layer 1 — Unit Evaluations (Component Isolation)

Deterministic checks that require no LLM call:
  1. Guardrails  — PII redaction, prompt-injection detection, out-of-scope detection
  2. Location    — query -> province resolution
  3. SQL / tools — DB integrity + correlation mapping + prediction-service sanity

Run:  python evals/run_evals.py --layer unit
"""
import os
import sys
import json
import sqlite3

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "backend", "app"))

from core.guardrails import remove_pii, is_prompt_injection, is_out_of_scope
from services.location_resolve import resolve_location_sqlite
from services.correlation_service import WEATHER_VAR_MAP, OUTCOME_COLUMNS

DB = os.path.join(ROOT, "data", "weathertato.db")
GOLDEN = os.path.join(os.path.dirname(__file__), "golden_data.json")


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------
def confusion(tp, fp, fn, tn):
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    accuracy = (tp + tn) / (tp + fp + fn + tn) if (tp + fp + fn + tn) else 0.0
    return {"precision": round(precision, 3), "recall": round(recall, 3),
            "f1": round(f1, 3), "accuracy": round(accuracy, 3), "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def binary_metrics(preds, labels):
    tp = sum(1 for p, l in zip(preds, labels) if p and l)
    fp = sum(1 for p, l in zip(preds, labels) if p and not l)
    fn = sum(1 for p, l in zip(preds, labels) if not p and l)
    tn = sum(1 for p, l in zip(preds, labels) if not p and not l)
    return confusion(tp, fp, fn, tn)


# ---------------------------------------------------------------------------
# 1. Guardrails
# ---------------------------------------------------------------------------
def eval_guardrails(cases):
    inj_preds, inj_labels = [], []
    oos_preds, oos_labels = [], []
    pii_preds, pii_labels = [], []
    pii_failures = []

    for c in cases:
        text = c["text"]
        inj_preds.append(is_prompt_injection(text))
        inj_labels.append(bool(c["injection"]))
        oos_preds.append(is_out_of_scope(text))
        oos_labels.append(bool(c["out_of_scope"]))
        # PII "detection" = redaction changed the string
        changed = remove_pii(text) != text
        pii_preds.append(changed)
        pii_labels.append(bool(c["has_pii"]))
        if changed != bool(c["has_pii"]):
            pii_failures.append(text)

    return {
        "prompt_injection": binary_metrics(inj_preds, inj_labels),
        "out_of_scope": binary_metrics(oos_preds, oos_labels),
        "pii_redaction": binary_metrics(pii_preds, pii_labels),
        "pii_failures": pii_failures,
        "n_cases": len(cases),
    }


# ---------------------------------------------------------------------------
# 2. Location resolution
# ---------------------------------------------------------------------------
def eval_location(cases):
    correct_province = 0
    correct_status = 0
    resolved = 0
    failures = []

    for c in cases:
        entity, status = resolve_location_sqlite(c["query"])
        if status == c["expected_status"]:
            correct_status += 1
        if c["expected_status"] == "RESOLVED":
            if entity is not None:
                resolved += 1
                if entity.province == c["expected_province"]:
                    correct_province += 1
                else:
                    failures.append({"query": c["query"], "got": entity.province,
                                     "expected": c["expected_province"]})
            else:
                failures.append({"query": c["query"], "got": None, "expected": c["expected_province"]})

    return {
        "province_accuracy": round(correct_province / max(resolved, 1), 3),
        "status_accuracy": round(correct_status / len(cases), 3),
        "resolved": resolved,
        "failures": failures,
        "n_cases": len(cases),
    }


# ---------------------------------------------------------------------------
# 3. SQL / tool integrity
# ---------------------------------------------------------------------------
def eval_sql_and_tools():
    checks = []

    def check(name, ok, detail=""):
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    # DB integrity
    n_w = cur.execute("SELECT COUNT(*) FROM fact_weather_monthly").fetchone()[0]
    check("fact_weather_monthly populated", n_w == 1225, f"{n_w} rows")
    null_w = cur.execute(
        "SELECT COUNT(*) FROM fact_weather_monthly WHERE wind_gusts_10m_max IS NULL "
        "OR et0_fao_evapotranspiration IS NULL OR shortwave_radiation_sum IS NULL"
    ).fetchone()[0]
    check("weather wind/et0/shortwave seeded", null_w == 0, f"{null_w} NULL rows")
    n_p = cur.execute("SELECT COUNT(*) FROM fact_palay_production").fetchone()[0]
    check("fact_palay_production populated", n_p == 1386, f"{n_p} rows")
    n_r = cur.execute("SELECT COUNT(*) FROM fact_retail_prices").fetchone()[0]
    check("fact_retail_prices populated", n_r == 1225, f"{n_r} rows")
    provs = cur.execute("SELECT COUNT(DISTINCT province_id) FROM fact_palay_production").fetchone()[0]
    check("7 provinces with palay data", provs == 7, f"{provs} provinces")
    view_cols = [r[1] for r in cur.execute("PRAGMA table_info(v_ml_market_features)").fetchall()]
    needed = ["price_lag1", "price_lag12", "yield_lag1", "production_lag1", "hist_yield", "hist_price"]
    missing = [c for c in needed if c not in view_cols]
    check("v_ml_market_features has lag columns", not missing, f"missing={missing}")
    conn.close()

    # correlation service mapping
    expected_map = {"RAINFALL": "precipitation_sum", "MEAN_TEMP": "temperature_2m_mean",
                    "MAX_TEMP": "temperature_2m_max", "MIN_TEMP": "temperature_2m_min",
                    "SOIL_MOISTURE": "soil_moisture_0_to_100cm_mean", "SURFACE_PRESSURE": "surface_pressure_mean"}
    check("WEATHER_VAR_MAP correct", WEATHER_VAR_MAP == expected_map, str(WEATHER_VAR_MAP))
    check("OUTCOME_COLUMNS correct", OUTCOME_COLUMNS == {"YIELD": "yield_mt_per_ha",
        "PRODUCTION": "volume_metric_tons", "PRICE": "retail_price_php"}, str(OUTCOME_COLUMNS))

    # prediction service sanity (uses the chatbot's actual predict path)
    pred_detail = "n/a"
    pred_ok = False
    try:
        from services.predict_service import predict_yield, predict_price
        y = predict_yield("Pampanga", 2024, 6)
        p = predict_price("Pampanga", 2024, 6)
        pred_ok = (isinstance(y, float) and 0 < y < 15) and (isinstance(p, float) and 0 < p < 100)
        pred_detail = f"yield={y} MT/ha, price={p} PHP/kg"
    except Exception as e:
        pred_detail = f"ERROR: {type(e).__name__}: {e}"
    check("predict_service returns plausible values", pred_ok, pred_detail)

    return {"checks": checks, "passed": sum(1 for c in checks if c["ok"]), "total": len(checks)}


def main():
    with open(GOLDEN, "r", encoding="utf-8") as f:
        golden = json.load(f)

    g = eval_guardrails(golden["guardrails"])
    loc = eval_location(golden["location"])
    sql = eval_sql_and_tools()

    results = {"unit": {"guardrails": g, "location": loc, "sql_tools": sql}}
    out_path = os.path.join(os.path.dirname(__file__), "metrics_unit.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)

    print(json.dumps(results, indent=2))
    print(f"\n[unit] wrote {out_path}")


if __name__ == "__main__":
    main()
