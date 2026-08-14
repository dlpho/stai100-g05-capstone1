"""
Prediction service — generates yield / price / production forecasts.

Feature engineering is kept IDENTICAL to `train_model.py` (4-month antecedent
lag + growing-season aggregate + dry/wet interaction + province dummies), and
predictions come from the most recently trained Lasso models, so the deployed
tool matches the benchmarked models.

For future target months, raw weather is imputed with the province's
month-of-year climatology and antecedent lag features are recomputed, so the
model predicts "given the completed growing season's weather" (in-season nowcast).
"""
import os
import glob
import joblib
import numpy as np
import pandas as pd

from services.train_model import get_combined_data, get_weather_rolling, WEATHER_VARS

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(ROOT_DIR, "services", "models")

MARKET_COLS = ["price_lag1", "price_lag12", "yield_lag1",
               "production_lag1", "hist_yield", "hist_price"]


def get_latest_model(model_type: str):
    """Load the most recently trained Lasso model for `model_type`."""
    files = glob.glob(os.path.join(MODELS_DIR, f"lasso_{model_type}_model_*.joblib"))
    if not files:
        raise FileNotFoundError(
            f"No lasso '{model_type}' models found in {MODELS_DIR}. Run train_model.py first."
        )
    return joblib.load(max(files, key=os.path.getmtime))


def _next_month(year: int, month: int):
    month += 1
    if month > 12:
        month = 1
        year += 1
    return year, month


def _build_features(province_name: str, target_year: int, target_month: int) -> pd.DataFrame:
    """Build the feature row for (province, year, month), matching training."""
    df_raw = get_combined_data()

    mask = df_raw["province_name"].str.strip().str.lower() == province_name.strip().lower()
    prov_raw = df_raw[mask].sort_values(["current_year", "month"]).reset_index(drop=True).copy()
    if prov_raw.empty:
        raise ValueError(f"No records found for province '{province_name}'.")

    # 1. Forward-fill market features (carry last known market state forward)
    prov_raw[MARKET_COLS] = prov_raw[MARKET_COLS].ffill().bfill()

    # 2. If the target month is in the future, append climatology rows so the
    #    antecedent (t-4..t-1) lag features are fully computable.
    last_year, last_month = int(prov_raw.iloc[-1]["current_year"]), int(prov_raw.iloc[-1]["month"])
    exists = ((prov_raw["current_year"] == target_year) & (prov_raw["month"] == target_month)).any()
    if not exists and (target_year, target_month) > (last_year, last_month):
        y, m = last_year, last_month
        synth_rows = []
        while (y, m) != (target_year, target_month):
            y, m = _next_month(y, m)
            synth = prov_raw.iloc[[-1]].copy()
            synth["current_year"] = y
            synth["month"] = m
            for v in WEATHER_VARS:
                if v in synth.columns:
                    clim = prov_raw[prov_raw["month"] == m][v].mean()
                    synth[v] = clim if not pd.isna(clim) else 0.0
            synth_rows.append(synth)
        if synth_rows:
            prov_raw = pd.concat([prov_raw] + synth_rows, ignore_index=True)

    # 3. Antecedent weather features + season indicator (same as training)
    feats = get_weather_rolling(prov_raw)
    feats["month_sin"] = np.sin(2 * np.pi * feats["month"] / 12)
    feats["month_cos"] = np.cos(2 * np.pi * feats["month"] / 12)

    # 4. Province dummies over the same 7 training provinces
    for p in sorted(df_raw["province_name"].str.strip().unique()):
        feats[f"prov_{p}"] = 1.0 if p.strip().lower() == province_name.strip().lower() else 0.0

    # 5. Target row (fallback to the synthesized last row if exact match missing)
    target = feats[(feats["current_year"] == target_year) & (feats["month"] == target_month)]
    if target.empty:
        target = feats.iloc[[-1]]
    return target.iloc[[-1]].fillna(0.0)


def _predict(model_type: str, province_name: str, target_year: int, target_month: int) -> float:
    row = _build_features(province_name, target_year, target_month)
    model = get_latest_model(model_type)
    return float(model.predict(row[model.feature_names_in_])[0])


def predict_yield(province_name: str, target_year: int, target_month: int) -> float:
    """Palay yield prediction in Metric Tons per Hectare (MT/ha)."""
    return round(max(0.0, _predict("yield", province_name, target_year, target_month)), 3)


def predict_price(province_name: str, target_year: int, target_month: int) -> float:
    """Palay retail price prediction in Philippine Pesos per Kilogram (PHP/kg)."""
    return round(max(0.0, _predict("price", province_name, target_year, target_month)), 2)


def predict_production(province_name: str, target_year: int, target_month: int) -> float:
    """Palay production volume prediction in Metric Tons (MT)."""
    return round(max(0.0, _predict("production", province_name, target_year, target_month)), 2)
