import os
import glob
import sqlite3
import joblib
import pandas as pd
import numpy as np

from services.train_model import WEATHER_VARS
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
MODELS_DIR = os.path.join(ROOT_DIR, "services", "models")

def get_latest_model(model_type="yield"):
    """Finds and loads the most recently trained .joblib model."""
    patterns = [
        os.path.join(MODELS_DIR, f"ridge_{model_type}_model.joblib")
    ]
    files = []
    for p in patterns:
        files.extend(glob.glob(p))

    if not files:
        raise FileNotFoundError(f"No trained '{model_type}' models found in directory: {MODELS_DIR}")

    latest_file = max(files, key=os.path.getctime)
    return joblib.load(latest_file)

def get_weather_rolling(df: pd.DataFrame) -> pd.DataFrame:
    """Computes 1-month, 2-month, and 3-month rolling weather aggregations."""
    df = df.copy()
    for v in WEATHER_VARS:
        if v in df.columns:
            df[f"{v}_1m"] = df[v]
            is_sum = "sum" in v or "days" in v or "et0" in v
            df[f"{v}_2m"] = df[v].rolling(2, min_periods=2).sum() if is_sum else df[v].rolling(2, min_periods=2).mean()
            df[f"{v}_3m"] = df[v].rolling(3, min_periods=3).sum() if is_sum else df[v].rolling(3, min_periods=3).mean()
    return df

def _prepare_features(province_name: str, target_year: int, target_month: int) -> pd.DataFrame:
    """Queries dataset, computes rolling weather stats, imputes missing future features,
    and formats dummy variables for Ridge ML models."""

    query = """
        SELECT *
        FROM v_ml_full_dataset
        WHERE LOWER(TRIM(province_name)) = LOWER(TRIM(?))
        ORDER BY current_year, month
    """

    with sqlite3.connect("data/weathertato.db") as conn:
        df = pd.read_sql_query(query, conn, params=[province_name.strip()])

    if df.empty:
        raise ValueError(
            f"No records found in database view 'v_ml_full_dataset' for province: '{province_name}'."
        )

    # 1. Forward-fill market lag features across timeline (carries last known market stats forward)
    market_cols = [c for c in df.columns if "lag" in c or "hist" in c or "target" in c]
    df[market_cols] = df[market_cols].ffill().bfill()

    # 2. Impute missing weather features using historical month-of-year averages (Climatology)
    for col in WEATHER_VARS:
        if col in df.columns:
            month_avg = df.groupby("month")[col].transform("mean")
            df[col] = df[col].fillna(month_avg)

    # 3. Compute rolling weather windows across historical timeline
    df = get_weather_rolling(df)

    # 4. Compute cyclical month features
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)

    # 5. Isolate target prediction row
    target_row = df[(df["current_year"] == target_year) & (df["month"] == target_month)].copy()

    # Fallback if target year/month row doesn't exist at all in database
    if target_row.empty:
        target_row = df.tail(1).copy()
        target_row["current_year"] = target_year
        target_row["month"] = target_month
        target_row["month_sin"] = np.sin(2 * np.pi * target_month / 12)
        target_row["month_cos"] = np.cos(2 * np.pi * target_month / 12)

        # Re-apply monthly climatology weather averages to the synthesized target row
        for v in WEATHER_VARS:
            hist_m_avg = df[df["month"] == target_month][v].mean()
            if not np.isnan(hist_m_avg):
                target_row[v] = hist_m_avg
                target_row[f"{v}_1m"] = hist_m_avg
                target_row[f"{v}_2m"] = hist_m_avg
                target_row[f"{v}_3m"] = hist_m_avg

    # 6. One-Hot Encode Province Dummies
    with sqlite3.connect("data/weathertato.db") as conn:
        all_provinces = pd.read_sql_query(
            "SELECT DISTINCT province_name FROM dim_province", conn
        )["province_name"].tolist()

    for p in all_provinces:
        target_row[f"prov_{p}"] = 1.0 if p.strip().lower() == province_name.strip().lower() else 0.0

    # 7. Final Safety Imputation: Replace any lingering NaNs with 0.0 before returning to model
    target_row = target_row.fillna(0.0)

    return target_row

def predict_yield(province_name: str, target_year: int, target_month: int) -> float:
    """Generates palay yield prediction in Metric Tons per Hectare (MT/ha)."""
    input_df = _prepare_features(province_name, target_year, target_month)
    model = get_latest_model("yield")
    pred = model.predict(input_df[model.feature_names_in_])[0]

    pred = max(0.0, float(pred))
    return round(float(pred), 3)

def predict_price(province_name: str, target_year: int, target_month: int) -> float:
    """Generates palay retail price prediction in Philippine Pesos per Kilogram (PHP/kg)."""
    input_df = _prepare_features(province_name, target_year, target_month)
    model = get_latest_model("price")
    pred = model.predict(input_df[model.feature_names_in_])[0]
    return round(float(pred), 2)
