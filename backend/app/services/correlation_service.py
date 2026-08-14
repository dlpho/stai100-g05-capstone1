"""
WeatherTato — weather <-> crop outcome correlation service.

Computes Pearson correlations between monthly-aggregated weather variables
(fetched on the fly from Open-Meteo, never persisted) and monthly palay
outcomes (yield / production / retail price) read from the SQLite warehouse.

This backs the agent's ANALYZE_CORRELATION action. Nothing here writes to the DB.
"""

import os
import sqlite3 as sql
import time

import pandas as pd

from services.meteo_service import fetch_monthly_weather


DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "weathertato.db")
)

# Palay outcomes available in the warehouse, keyed by the agent's outcome_metric enum.
OUTCOME_COLUMNS = {
    "YIELD": "yield_mt_per_ha",
    "PRODUCTION": "volume_metric_tons",
    "PRICE": "retail_price_php",
}

# Agent slot vocabulary (weather_variables enum) -> Open-Meteo daily variables.
WEATHER_VAR_MAP = {
    "RAINFALL": "precipitation_sum",
    "MEAN_TEMP": "temperature_2m_mean",
    "MAX_TEMP": "temperature_2m_max",
    "MIN_TEMP": "temperature_2m_min",
    "SOIL_MOISTURE": "soil_moisture_0_to_100cm_mean",
    "SURFACE_PRESSURE": "surface_pressure_mean",
}


def _provinces_with_data(conn: sql.Connection) -> pd.DataFrame:
    """Provinces that actually have palay production rows in the warehouse."""
    return pd.read_sql_query(
        """
        SELECT d.province_id, d.province_name, d.latitude, d.longitude
        FROM dim_province d
        JOIN (SELECT DISTINCT province_id FROM fact_palay_production) p
          ON d.province_id = p.province_id
        ORDER BY d.province_id
        """,
        conn,
    )


def _aligned_data(
    conn: sql.Connection,
    weather_vars: list,
    start_date: str,
    end_date: str,
    lag_months: int = 0,
    province_name: str | None = None,
) -> pd.DataFrame:
    """One merged frame of weather + outcomes, aligned on (province, month).

    If lag_months > 0, each weather row is paired with the outcome `lag_months`
    later — i.e. weather at month t is compared to the outcome at month t + lag.
    """
    start_year = int(start_date[:4])
    end_year = int(end_date[:4])

    provinces = _provinces_with_data(conn)
    if province_name:
        provinces = provinces[provinces["province_name"].str.lower() == province_name.lower()]
    frames = []
    for _, prov in provinces.iterrows():
        w = fetch_monthly_weather(
            float(prov.latitude), float(prov.longitude),
            start_date, end_date, weather_vars,
        )
        prod = pd.read_sql_query(
            "SELECT year, month, volume_metric_tons, area_harvested_hectares, yield_mt_per_ha "
            "FROM fact_palay_production WHERE province_id = ? AND year BETWEEN ? AND ?",
            conn, params=(int(prov.province_id), start_year, end_year),
        )
        price = pd.read_sql_query(
            "SELECT year, month, retail_price_php FROM fact_retail_prices "
            "WHERE province_id = ? AND year BETWEEN ? AND ?",
            conn, params=(int(prov.province_id), start_year, end_year),
        )
        out = prod.merge(price, on=["year", "month"], how="inner")

        # Month ordinal (0-indexed) so we can shift weather vs outcome.
        w = w.copy()
        out = out.copy()
        w["_ym"] = w["year"] * 12 + (w["month"] - 1) + lag_months
        out["_ym"] = out["year"] * 12 + (out["month"] - 1)
        out = out.drop(columns=["year", "month"])

        merged = w.merge(out, on="_ym", how="inner")
        merged.insert(0, "province", prov.province_name)
        frames.append(merged)
        time.sleep(3)  # stay under Open-Meteo's anonymous rate limit

    return pd.concat(frames, ignore_index=True)


def compute_correlations(
    weather_vars: list,
    outcomes: list = ("YIELD", "PRODUCTION", "PRICE"),
    start_date: str = "2012-01-01",
    end_date: str = "2026-07-31",
    lag_months: int = 0,
    province_name: str | None = None,
) -> pd.DataFrame:
    """Pooled Pearson r between monthly weather vars and palay outcomes.

    All provinces are pooled into a single sample. `lag_months` shifts weather
    relative to outcome (see _aligned_data). Returns a DataFrame of correlation
    coefficients: rows = weather variables, columns = outcomes.
    """
    outcome_cols = [OUTCOME_COLUMNS[o] for o in outcomes]

    conn = sql.connect(DB_PATH)
    try:
        data = _aligned_data(conn, weather_vars, start_date, end_date, lag_months, province_name)
    finally:
        conn.close()

    r = pd.DataFrame(index=weather_vars, columns=outcomes, dtype=float)
    for v in weather_vars:
        for o, col in zip(outcomes, outcome_cols):
            sub = data[[v, col]].dropna()
            r.loc[v, o] = sub[v].corr(sub[col])
    r.index.name = "weather_variable"
    return r


def correlations_by_province(
    weather_vars: list,
    outcomes: list = ("YIELD", "PRODUCTION", "PRICE"),
    start_date: str = "2012-01-01",
    end_date: str = "2026-07-31",
    lag_months: int = 0,
    province_name: str | None = None,
) -> pd.DataFrame:
    """Per-province Pearson r (temporal, within each province's own series).

    Returns a DataFrame indexed by (province, weather_variable) with one
    column per outcome.
    """
    outcome_cols = [OUTCOME_COLUMNS[o] for o in outcomes]

    conn = sql.connect(DB_PATH)
    try:
        data = _aligned_data(conn, weather_vars, start_date, end_date, lag_months, province_name)
    finally:
        conn.close()

    rows = []
    for prov, sub in data.groupby("province", sort=True):
        for v in weather_vars:
            row = {"province": prov, "weather_variable": v}
            for o, col in zip(outcomes, outcome_cols):
                s = sub[[v, col]].dropna()
                row[o] = s[v].corr(s[col])
            rows.append(row)

    out = pd.DataFrame(rows).set_index(["province", "weather_variable"])
    return out

def compute_detailed_correlation(
    weather_vars: list,
    outcomes: list,
    start_date: str,
    end_date: str,
    province_name: str,
    selected_lag: int = 4
) -> dict:
    """Computes detailed correlation metrics for a specific province,
    including exact observations and cross-lag correlations for visualization.
    """
    conn = sql.connect(DB_PATH)
    try:
        # Get exact observations at the selected lag
        data_selected = _aligned_data(conn, weather_vars, start_date, end_date, selected_lag, province_name)
        
        # We only compute metrics for the selected_lag now that cross-lag visualizations are disabled.
        lag_series = {}
        lag_metrics = {}
        for v in weather_vars:
            lag_metrics[v] = {}
            for o in outcomes:
                col = OUTCOME_COLUMNS[o]
                if v in data_selected.columns and col in data_selected.columns:
                    s = data_selected[[v, col]].dropna()
                    lag_metrics[v][o] = s[v].corr(s[col]) if len(s) > 1 else None
        
        lag_series[selected_lag] = lag_metrics
            
    finally:
        conn.close()

    return {
        "observations": data_selected,
        "lag_series": lag_series,
        "selected_lag": selected_lag
    }
