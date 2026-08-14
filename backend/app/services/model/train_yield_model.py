import sqlite3
import pandas as pd
import joblib
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline

WEATHER_VARS = [
  "precipitation_sum", "temperature_2m_max", "temperature_2m_min",
  "wind_gusts_10m_max", "temperature_2m_mean", "soil_moisture_0_to_100cm_mean",
  "surface_pressure_mean", "et0_fao_evapotranspiration",
  "shortwave_radiation_sum", "relative_humidity_2m_mean"
]

def fetch_lagged_training_data():
  """Fetch data and self-join to create Year-Over-Year historical features."""
  conn = sqlite3.connect("data/weathertato.db")

  # Get current year targets and previous year (t-1) historicals
  query = """
    SELECT
      curr.province_name,
      p.latitude,
      p.longitude,
      curr.year as current_year,
      curr.month,
      curr.yield_mt_per_ha as target_yield,
      curr.retail_price_php as target_price,
      prev.yield_mt_per_ha as hist_yield,
      prev.retail_price_php as hist_price,
      prev.volume_metric_tons as hist_production
    FROM v_monthly_market_summary curr
    JOIN dim_province p ON curr.province_id = p.province_id
    JOIN v_monthly_market_summary prev
      ON curr.province_id = prev.province_id
      AND curr.month = prev.month
      AND curr.year = prev.year + 1
    WHERE curr.yield_mt_per_ha IS NOT NULL
      AND curr.retail_price_php IS NOT NULL
      AND prev.yield_mt_per_ha IS NOT NULL
      AND prev.retail_price_php IS NOT NULL
  """
  df = pd.read_sql_query(query, conn)
  conn.close()
  return df

def build_and_train_models():
  print("Fetching historical database records with YoY lag...")
  df = fetch_lagged_training_data()

  yield_features = []
  yield_targets = []
  price_features = []
  price_targets = []

  print(f"Processing {len(df)} records for training...")
  for _, row in df.iterrows():
    # --- 1. BUILD YIELD MODEL DATA (Weather + Hist Price + Hist Yield) ---
    start_date = f"{int(row['current_year'])}-{int(row['month']):02d}-01"
    end_date = f"{int(row['current_year'])}-{int(row['month']):02d}-28"

    try:
      # Mock API call - Replace with actual fetch to your meteo_service
      weather_data = mock_extract_weather_features(
        row['latitude'], row['longitude'], start_date, end_date, WEATHER_VARS
      )

      if weather_data:
        # Combine weather with historical DB features
        y_feat = [weather_data[v] for v in WEATHER_VARS] + [row['hist_price'], row['hist_yield']]
        yield_features.append(y_feat)
        yield_targets.append(row['target_yield'])

    except Exception as e:
      print(f"Weather fetch failed: {e}")

    # --- 2. BUILD PRICE MODEL DATA (Hist Yield + Hist Production) ---
    # No weather needed for price model as per user specs
    p_feat = [row['hist_yield'], row['hist_production']]
    price_features.append(p_feat)
    price_targets.append(row['target_price'])

  # Train Yield Model
  print("Training Yield Model...")
  X_yield = pd.DataFrame(yield_features, columns=WEATHER_VARS + ['hist_price', 'hist_yield'])
  model_yield = Pipeline([
    ('scaler', StandardScaler()),
    ('regressor', LinearRegression())
  ])
  model_yield.fit(X_yield, yield_targets)
  joblib.dump(model_yield, "models/lr_yield_model.joblib")

  # Train Price Model
  print("Training Price Model...")
  X_price = pd.DataFrame(price_features, columns=['hist_yield', 'hist_production'])
  model_price = Pipeline([
    ('scaler', StandardScaler()),
    ('regressor', LinearRegression())
  ])
  model_price.fit(X_price, price_targets)
  joblib.dump(model_price, "models/lr_price_model.joblib")

  print("Both models trained and saved successfully.")

def mock_extract_weather_features(lat, lon, start, end, vars):
  """Placeholder for your internal open-meteo dict extraction."""
  return {var: 0.0 for var in vars}

if __name__ == "__main__":
  build_and_train_models()
