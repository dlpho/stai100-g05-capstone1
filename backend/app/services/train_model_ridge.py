import os
import sys
import sqlite3
import joblib
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.linear_model import RidgeCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

MODELS_DIR = os.path.join(ROOT_DIR, "services", "models")

# Restricted strictly to 6 base variables + 2 derived variables
WEATHER_VARS = [
    "precipitation_sum",             # RAINFALL
    "temperature_2m_mean",          # MEAN_TEMP
    "temperature_2m_max",           # MAX_TEMP
    "temperature_2m_min",           # MIN_TEMP
    "soil_moisture_0_to_100cm_mean", # SOIL_MOISTURE
    "surface_pressure_mean",        # SURFACE_PRESSURE
    "extreme_rain_days",            # DERIVED (precipitation_sum >= 54 mm)
    "extreme_heat_days"             # DERIVED (temperature_2m_max >= 34 C)
]

def get_combined_data():
    """
    Fetches and joins weather and market data from the database.
    Calculates cyclical month features.
    """
    query = """
        SELECT
            p.province_name,
            p.latitude,
            p.longitude,
            w.year AS current_year,
            w.month,
            m.yield_mt_per_ha AS target_yield,
            m.retail_price_php AS target_price,
            m.volume_metric_tons AS target_production,
            m.price_lag1,
            m.price_lag12,
            m.yield_lag1,
            m.hist_yield,
            m.production_lag1,
            m.hist_price,
            w.precipitation_sum,
            w.temperature_2m_mean,
            w.temperature_2m_max,
            w.temperature_2m_min,
            w.surface_pressure_mean,
            w.soil_moisture_0_to_100cm_mean,
            w.extreme_rain_days,
            w.extreme_heat_days
        FROM fact_weather_monthly w
        JOIN dim_province p ON w.province_id = p.province_id
        LEFT JOIN v_ml_market_features m
            ON p.province_name = m.province_name
           AND w.year = m.year
           AND w.month = m.month
        WHERE w.year >= 2011
          AND (w.year < 2026 OR (w.year = 2026 AND w.month <= 6))
        ORDER BY p.province_name, w.year, w.month
    """
    with sqlite3.connect("data/weathertato.db") as conn:
        df = pd.read_sql_query(query, conn)

    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    return df

def get_weather_rolling(g):
    """
    Builds antecedent weather features by calculating 1-month, 2-month, and 3-month rolling averages/sums.
    """
    g = g.copy()
    for v in WEATHER_VARS:
        if v in g.columns:
            g[f"{v}_1m"] = g[v]
            is_sum = "sum" in v or "days" in v
            g[f"{v}_2m"] = g[v].rolling(2, min_periods=2).sum() if is_sum else g[v].rolling(2, min_periods=2).mean()
            g[f"{v}_3m"] = g[v].rolling(3, min_periods=3).sum() if is_sum else g[v].rolling(3, min_periods=3).mean()
    return g

def calc_metrics(y_true, y_pred):
    """
    Calculates MAE, RMSE, and R2 scores between true and predicted values,
    ignoring any NaN values.
    """
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_t, y_p = y_true[mask], y_pred[mask]
    return mean_absolute_error(y_t, y_p), np.sqrt(mean_squared_error(y_t, y_p)), r2_score(y_t, y_p)

def main():
    """
    Main training script for the Ridge regression model.
    Prepares data, trains models for yield, price, and production, evaluates them, and saves the models to disk.
    """
    df_raw = get_combined_data()
    frames = []

    for prov, g in df_raw.groupby("province_name"):
        g = g.sort_values(["current_year", "month"])
        frames.append(get_weather_rolling(g))

    if not frames:
        return

    df = pd.concat(frames, ignore_index=True)
    df = df[df["current_year"] >= 2012]
    df = pd.get_dummies(df, columns=["province_name"], prefix="prov")
    df.dropna(inplace=True)

    print(f"Final merged dataset contains {len(df)} records.")

    train, test = df[df["current_year"] <= 2023], df[df["current_year"] >= 2024]

    w_cols = [c for c in df.columns if any(c.startswith(v) for v in WEATHER_VARS)]
    p_cols = [c for c in df.columns if c.startswith("prov_")]

    y_feats = w_cols + ["hist_yield", "hist_price", "month_sin", "month_cos"] + p_cols
    p_feats = ["price_lag1", "price_lag12", "yield_lag1", "production_lag1", "hist_yield", "month_sin", "month_cos"] + w_cols + p_cols
    pr_feats = w_cols + ["production_lag1", "month_sin", "month_cos"] + p_cols

    # Yield Baselines & Model
    b1_y = calc_metrics(test["target_yield"], test["hist_yield"])
    b2_y = calc_metrics(test["target_yield"], test["month"].map(train.groupby("month")["target_yield"].mean()))

    y_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0, 500.0])) # Automatically finds best penalty
    ])
    y_model.fit(train[y_feats], train["target_yield"])
    ml_y = calc_metrics(test["target_yield"], y_model.predict(test[y_feats]))

    # Price Baselines & Model
    b1_p = calc_metrics(test["target_price"], test["price_lag1"])
    b2_p = calc_metrics(test["target_price"], test["price_lag12"])

    p_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0, 500.0]))
    ])
    p_model.fit(train[p_feats], train["target_price"])
    ml_p = calc_metrics(test["target_price"], p_model.predict(test[p_feats]))

    print("\n--- Yield Model Benchmarks (MAE, RMSE, R2) ---")
    print(f"Prev Year:         {b1_y[0]:.3f}, {b1_y[1]:.3f}, {b1_y[2]:.3f}")
    print(f"Seasonal Avg:      {b2_y[0]:.3f}, {b2_y[1]:.3f}, {b2_y[2]:.3f}")
    print(f"ML Model (Ridge):  {ml_y[0]:.3f}, {ml_y[1]:.3f}, {ml_y[2]:.3f}")

    print("\n--- Price Model Benchmarks (MAE, RMSE, R2) ---")
    print(f"Prev Month:        {b1_p[0]:.3f}, {b1_p[1]:.3f}, {b1_p[2]:.3f}")
    print(f"Prev Year:         {b2_p[0]:.3f}, {b2_p[1]:.3f}, {b2_p[2]:.3f}")
    print(f"ML Model (Ridge):  {ml_p[0]:.3f}, {ml_p[1]:.3f}, {ml_p[2]:.3f}")

    # Production Baselines & Model
    b1_pr = calc_metrics(test["target_production"], test["production_lag1"])
    b2_pr = calc_metrics(test["target_production"], test["month"].map(train.groupby("month")["target_production"].mean()))

    pr_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", RidgeCV(alphas=[0.1, 1.0, 10.0, 100.0, 500.0]))
    ])
    pr_model.fit(train[pr_feats], train["target_production"])
    ml_pr = calc_metrics(test["target_production"], pr_model.predict(test[pr_feats]))

    print("\n--- Production Model Benchmarks (MAE, RMSE, R2) ---")
    print(f"Prev Month:        {b1_pr[0]:.3f}, {b1_pr[1]:.3f}, {b1_pr[2]:.3f}")
    print(f"Seasonal Avg:      {b2_pr[0]:.3f}, {b2_pr[1]:.3f}, {b2_pr[2]:.3f}")
    print(f"ML Model (Ridge):  {ml_pr[0]:.3f}, {ml_pr[1]:.3f}, {ml_pr[2]:.3f}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    joblib.dump(y_model.fit(df[y_feats], df["target_yield"]), os.path.join(MODELS_DIR, f"ridge_yield_model_{timestamp}.joblib"))
    joblib.dump(p_model.fit(df[p_feats], df["target_price"]), os.path.join(MODELS_DIR, f"ridge_price_model_{timestamp}.joblib"))
    joblib.dump(pr_model.fit(df[pr_feats], df["target_production"]), os.path.join(MODELS_DIR, f"ridge_production_model_{timestamp}.joblib"))

if __name__ == "__main__":
    main()
