import os
import sys
import sqlite3
import joblib
from datetime import datetime
import pandas as pd
import numpy as np
from sklearn.linear_model import LassoCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)

MODELS_DIR = os.path.join(ROOT_DIR, "services", "models")

WEATHER_VARS = [
    "precipitation_sum", "et0_fao_evapotranspiration", "shortwave_radiation_sum",
    "temperature_2m_mean", "temperature_2m_max", "temperature_2m_min",
    "wind_gusts_10m_max", "surface_pressure_mean", "soil_moisture_0_to_100cm_mean",
    "relative_humidity_2m_mean", "extreme_rain_days", "extreme_heat_days"
]

def get_combined_data():
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
            w.et0_fao_evapotranspiration,
            w.shortwave_radiation_sum,
            w.temperature_2m_mean,
            w.temperature_2m_max,
            w.temperature_2m_min,
            w.wind_gusts_10m_max,
            w.surface_pressure_mean,
            w.soil_moisture_0_to_100cm_mean,
            w.relative_humidity_2m_mean,
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
    g = g.copy()
    for v in WEATHER_VARS:
        if v in g.columns:
            g[f"{v}_1m"] = g[v]
            is_sum = "sum" in v or "days" in v or "et0" in v
            g[f"{v}_2m"] = g[v].rolling(2, min_periods=2).sum() if is_sum else g[v].rolling(2, min_periods=2).mean()
            g[f"{v}_3m"] = g[v].rolling(3, min_periods=3).sum() if is_sum else g[v].rolling(3, min_periods=3).mean()
    return g

def calc_metrics(y_true, y_pred):
    mask = ~np.isnan(y_true) & ~np.isnan(y_pred)
    y_t, y_p = y_true[mask], y_pred[mask]
    return mean_absolute_error(y_t, y_p), np.sqrt(mean_squared_error(y_t, y_p)), r2_score(y_t, y_p)

def print_top_features(model, feature_names, title="Selected Features"):
    scaler = model.named_steps["scaler"]
    lasso = model.named_steps["model"]

    # Coefficients are on standardized scale (directly comparable magnitude)
    coefs = pd.Series(lasso.coef_, index=feature_names)
    active_coefs = coefs[coefs != 0].sort_values(key=abs, ascending=False)

    print(f"\n--- {title} (Non-zero Lasso Weights) ---")
    if active_coefs.empty:
        print("Lasso eliminated all features (predicting baseline mean).")
    else:
        for feat, val in active_coefs.items():
            print(f"  {feat:<35}: {val:+.4f}")

def main():
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

    # Yield Model
    b1_y = calc_metrics(test["target_yield"], test["hist_yield"])
    b2_y = calc_metrics(test["target_yield"], test["month"].map(train.groupby("month")["target_yield"].mean()))

    y_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LassoCV(cv=5, random_state=42, max_iter=10000))
    ])
    y_model.fit(train[y_feats], train["target_yield"])
    ml_y = calc_metrics(test["target_yield"], y_model.predict(test[y_feats]))

    # Price Model
    b1_p = calc_metrics(test["target_price"], test["price_lag1"])
    b2_p = calc_metrics(test["target_price"], test["price_lag12"])

    p_model = Pipeline([
        ("scaler", StandardScaler()),
        ("model", LassoCV(cv=5, random_state=42, max_iter=10000))
    ])
    p_model.fit(train[p_feats], train["target_price"])
    ml_p = calc_metrics(test["target_price"], p_model.predict(test[p_feats]))

    # Print Interpretability Insights
    print_top_features(y_model, y_feats, "Yield Model Feature Importance")
    print_top_features(p_model, p_feats, "Price Model Feature Importance")

    print("\n--- Yield Model Benchmarks (MAE, RMSE, R2) ---")
    print(f"Prev Year:         {b1_y[0]:.3f}, {b1_y[1]:.3f}, {b1_y[2]:.3f}")
    print(f"Seasonal Avg:      {b2_y[0]:.3f}, {b2_y[1]:.3f}, {b2_y[2]:.3f}")
    print(f"ML Model (Lasso):  {ml_y[0]:.3f}, {ml_y[1]:.3f}, {ml_y[2]:.3f}")

    print("\n--- Price Model Benchmarks (MAE, RMSE, R2) ---")
    print(f"Prev Month:        {b1_p[0]:.3f}, {b1_p[1]:.3f}, {b1_p[2]:.3f}")
    print(f"Prev Year:         {b2_p[0]:.3f}, {b2_p[1]:.3f}, {b2_p[2]:.3f}")
    print(f"ML Model (Lasso):  {ml_p[0]:.3f}, {ml_p[1]:.3f}, {ml_p[2]:.3f}")

    os.makedirs(MODELS_DIR, exist_ok=True)
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')

    joblib.dump(y_model.fit(df[y_feats], df["target_yield"]), os.path.join(MODELS_DIR, f"lasso_yield_model_{timestamp}.joblib"))
    joblib.dump(p_model.fit(df[p_feats], df["target_price"]), os.path.join(MODELS_DIR, f"lasso_price_model_{timestamp}.joblib"))

if __name__ == "__main__":
    main()
