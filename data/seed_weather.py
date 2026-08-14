import os
import sys
import time
import sqlite3
import pandas as pd
import logging

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.app.services.meteo_service import fetch_monthly_weather, MONTHLY_AGG

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

DB_PATH = os.path.join("data", "weathertato.db")

ALL_WEATHER_VARS = list(MONTHLY_AGG.keys())

START_DATE = "2012-01-01"
END_DATE = "2026-07-31"

def seed_fact_weather_monthly():
    """
    Fetches historical monthly weather data for all provinces from the Open-Meteo API
    and populates the fact_weather_monthly table in the database.
    """
    if not os.path.exists(DB_PATH):
        raise FileNotFoundError(f"Database file not found at {DB_PATH}")

    with sqlite3.connect(DB_PATH) as conn:
        # 1. Fetch all provinces from dim_province
        provinces_df = pd.read_sql_query(
            "SELECT province_id, province_name, latitude, longitude FROM dim_province",
            conn
        )

        if provinces_df.empty:
            logging.error("dim_province table is empty! Populate dim_province first.")
            return

        logging.info(f"Found {len(provinces_df)} provinces to seed: {provinces_df['province_name'].tolist()}")

        for _, row in provinces_df.iterrows():
            prov_id = row["province_id"]
            prov_name = row["province_name"]
            lat = float(row["latitude"])
            lon = float(row["longitude"])

            logging.info(f"Fetching weather data for '{prov_name}' (ID: {prov_id}, Lat: {lat}, Lon: {lon})...")

            try:
                # 2. Fetch monthly aggregated weather from Open-Meteo API
                monthly_df = fetch_monthly_weather(
                    lat=lat,
                    lon=lon,
                    start_date=START_DATE,
                    end_date=END_DATE,
                    daily_vars=ALL_WEATHER_VARS
                )

                if monthly_df.empty:
                    logging.warning(f"No weather data returned for {prov_name}.")
                    continue

                # 3. Attach province_id for database foreign key constraint
                monthly_df["province_id"] = prov_id

                # 4. Clear existing records for this province to avoid duplication
                conn.execute(
                    "DELETE FROM fact_weather_monthly WHERE province_id = ?",
                    (prov_id,)
                )

                # 5. Insert newly fetched monthly records into SQLite
                monthly_df.to_sql(
                    "fact_weather_monthly",
                    conn,
                    if_exists="append",
                    index=False
                )
                conn.commit()

                logging.info(f"Successfully inserted {len(monthly_df)} monthly records for {prov_name}.")

            except Exception as e:
                conn.rollback()
                logging.error(f"Failed to fetch or save weather data for '{prov_name}': {e}")

            # Politeness delay to prevent rate limiting
            time.sleep(1)

    logging.info("Weather seeding completed!")

if __name__ == "__main__":
    seed_fact_weather_monthly()
