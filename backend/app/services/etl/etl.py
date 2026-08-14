import os
import io
import requests
import sqlite3 as sql
from datetime import date

import numpy as np
import pandas as pd
from tsdisagg import disaggregate_series


DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "data", "weathertato.db")
)


def insert_into_crop_production(crop: str, cur: sql.Cursor):
    ytd = date.today().year
    vol_url = "https://openstat.psa.gov.ph:443/PXWeb/api/v1/en/DB/2E/CS/0012E4EVCP0.px"
    area_url = "https://openstat.psa.gov.ph:443/PXWeb/api/v1/en/DB/2E/CS/0022E4EAHC0.px"

    year_list = [str(x + 23) for x in range(0, (ytd - 2010 + 1))]
    loc_list = [str(x) for x in range(20, 27)]
    payload = {
        "query": [
            {
                "code": "Ecosystem/Croptype",
                "selection": {
                    "filter": "item",
                    "values": ["2" if (crop == "palay") else "5"],
                },
            },
            {
                "code": "Geolocation",
                "selection": {
                    "filter": "item",
                    "values": loc_list,
                },
            },
            {
                "code": "Year",
                "selection": {
                    "filter": "item",
                    "values": year_list,
                },
            },
            {
                "code": "Period",
                "selection": {
                    "filter": "item",
                    "values": ["0", "1", "3", "4"],
                },
            },
        ],
        "response": {"format": "csv"},
    }

    vol_res = requests.post(vol_url, json=payload)
    vol_df = pd.read_csv(io.StringIO(vol_res.text)).T
    vol_df.columns = [s.strip(".") for s in vol_df.iloc[1]]
    vol_df.drop(index=vol_df.iloc[0:2].index, inplace=True)
    vol_df = vol_df.replace(r"^\.+$", pd.NA, regex=True)
    vol_df = vol_df.dropna()
    vol_df.index = pd.PeriodIndex(
        vol_df.index.str.replace(" Quarter ", "Q"), freq="Q"
    ).to_timestamp(how="end")

    result_cols = {}
    for col in vol_df.columns:
        series = disaggregate_series(
            vol_df[[col]],
            target_freq="ME",
            method="denton-cholette",
            agg_func="sum",
            h=1,
        )
        result_cols[col] = series.squeeze()
    vol_df = pd.DataFrame(result_cols)

    area_res = requests.post(area_url, json=payload)
    area_df = pd.read_csv(io.StringIO(area_res.text)).T
    area_df.columns = [s.strip(".") for s in area_df.iloc[1]]
    area_df.drop(index=area_df.iloc[0:2].index, inplace=True)
    area_df = area_df.replace(r"^\.+$", pd.NA, regex=True)
    area_df = area_df.dropna()
    area_df.index = pd.PeriodIndex(
        area_df.index.str.replace(" Quarter ", "Q"), freq="Q"
    ).to_timestamp(how="end")

    result_cols = {}
    for col in area_df.columns:
        series = disaggregate_series(
            area_df[[col]],
            target_freq="ME",
            method="denton-cholette",
            agg_func="sum",
            h=1,
        )
        result_cols[col] = series.squeeze()
    area_df = pd.DataFrame(result_cols)

    stack_vol = vol_df.stack().reset_index()
    stack_vol.columns = ["date", "province", "volume_metric_tons"]

    stack_area = area_df.stack().reset_index()
    stack_area.columns = ["date", "province", "area_harvested_hectares"]

    comb_df = stack_vol.merge(stack_area, on=["date", "province"])
    comb_df["year"] = comb_df["date"].dt.year
    comb_df["month"] = comb_df["date"].dt.month
    comb_df["crop"] = crop

    cur.execute("SELECT province_id, province_name FROM dim_province")
    province_map = {row[1]: row[0] for row in cur.fetchall()}

    rows = []
    for _, row in comb_df.iterrows():
        pid = province_map.get(row["province"])
        if pid is None:
            continue
        rows.append((
            pid,
            row["crop"],
            int(row["year"]),
            int(row["month"]),
            float(row["volume_metric_tons"]),
            float(row["area_harvested_hectares"]),
        ))

    cur.executemany(
        """INSERT OR IGNORE INTO fact_crop_production
           (province_id, crop, year, month, volume_metric_tons, area_harvested_hectares)
           VALUES (?, ?, ?, ?, ?, ?)""",
        rows,
    )

def _fetch_retail_prices(url: str, query: dict) -> pd.DataFrame:
    res = requests.post(url, json=query)
    df = pd.read_csv(io.StringIO(res.text)).T
    df.columns = [s.strip(".") for s in df.iloc[0]]
    df.drop(index=df.iloc[0:2].index, inplace=True)
    df = df.replace(r"^\.+$", pd.NA, regex=True)
    df.index = pd.to_datetime(df.index, format="%Y %B").to_period("M").to_timestamp(how="end")
    stacked = df.stack().reset_index()
    stacked.columns = ["date", "province", "retail_price_php"]
    stacked["retail_price_php"] = pd.to_numeric(stacked["retail_price_php"], errors="coerce")
    return stacked.dropna(subset=["retail_price_php"])


def insert_into_retail(cur: sql.Cursor):
    newapi = "https://openstat.psa.gov.ph:443/PXWeb/api/v1/en/DB/2M/2018NEW/0042M4ARN01.px"
    oldapi = "https://openstat.psa.gov.ph:443/PXWeb/api/v1/en/DB/2M/NRP/0042M4ARN01.px"
    newquery = {
        "query": [
            {
            "code": "Geolocation",
            "selection": {
                "filter": "item",
                "values": [
                "037700000",
                "030800000",
                "031400000",
                "034900000",
                "035400000",
                "036900000",
                "037100000"
                ]
            }
            },
            {
            "code": "Commodity",
            "selection": {
                "filter": "item",
                "values": [
                "1"
                ]
            }
            },
            {
            "code": "Period",
            "selection": {
                "filter": "item",
                "values": [
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "11"
                ]
            }
            }
        ],
        "response": {
            "format": "csv"
        }
    }
    oldquery = {
        "query": [
            {
            "code": "Region/Province",
            "selection": {
                "filter": "item",
                "values": [
                "21",
                "22",
                "23",
                "24",
                "25",
                "26",
                "27"
                ]
            }
            },
            {
            "code": "Commodity",
            "selection": {
                "filter": "item",
                "values": [
                "0"
                ]
            }
            },
            {
            "code": "period",
            "selection": {
                "filter": "item",
                "values": [
                "0",
                "1",
                "2",
                "3",
                "4",
                "5",
                "6",
                "7",
                "8",
                "9",
                "10",
                "11"
                ]
            }
            }
        ],
        "response": {
            "format": "csv"
        }
    }
    old_df = _fetch_retail_prices(oldapi, oldquery)
    new_df = _fetch_retail_prices(newapi, newquery)
    comb_df = pd.concat([old_df, new_df], ignore_index=True) 
    comb_df = comb_df.drop_duplicates(subset=["date", "province"], keep="last") # keep newer
    comb_df["year"] = comb_df["date"].dt.year
    comb_df["month"] = comb_df["date"].dt.month

    cur.execute("SELECT province_id, province_name FROM dim_province")
    province_map = {row[1]: row[0] for row in cur.fetchall()}

    rows = []
    for _, row in comb_df.iterrows():
        pid = province_map.get(row["province"])
        if pid is None:
            continue
        rows.append((
            pid,
            int(row["year"]),
            int(row["month"]),
            float(row["retail_price_php"]),
        ))

    cur.executemany(
        """INSERT OR IGNORE INTO fact_retail_prices
           (province_id, year, month, retail_price_php)
           VALUES (?, ?, ?, ?)""",
        rows,
    )


if __name__ == "__main__":
    conn = sql.connect(DB_PATH)
    cur = conn.cursor()
    insert_into_crop_production("palay", cur)
    insert_into_crop_production("corn", cur)
    insert_into_retail(cur)
    conn.commit()
    conn.close()
