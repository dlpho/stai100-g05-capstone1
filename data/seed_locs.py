import csv, io, sqlite3
from typing import Optional

def seed_muni(cur: sqlite3.Cursor, data: list[dict]):
  for r in data:
    p, reg, c, lat, lon = r["province"].strip(), r["region"].strip(), r["municipality_city"].strip(), float(r["latitude"]), float(r["longitude"])
    cur.execute("INSERT INTO dim_province (province_name, region_name, latitude, longitude) VALUES (?, ?, ?, ?) ON CONFLICT(province_name) DO UPDATE SET region_name = excluded.region_name", (p, reg, lat, lon))
    cur.execute("SELECT province_id FROM dim_province WHERE province_name = ?", (p,))
    pid = cur.fetchone()[0]
    cur.execute("INSERT INTO dim_city_municipality (city_municipality_name, province_id, latitude, longitude) SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM dim_city_municipality WHERE city_municipality_name = ? AND province_id = ?)", (c, pid, lat, lon, c, pid))

def seed_brgy(cur: sqlite3.Cursor, data: list[dict]):
  for r in data:
    b, c, p, lat, lon = r["barangay"].strip(), r["municipality_city"].strip(), r["province"].strip(), float(r["latitude"]), float(r["longitude"])
    cur.execute("SELECT c.city_municipality_id FROM dim_city_municipality c JOIN dim_province p ON c.province_id = p.province_id WHERE LOWER(c.city_municipality_name) = LOWER(?) AND LOWER(p.province_name) = LOWER(?)", (c, p))
    res = cur.fetchone()
    if not res: continue
    cid = res[0]
    cur.execute("INSERT INTO dim_barangay (barangay_name, city_municipality_id, latitude, longitude) SELECT ?, ?, ?, ? WHERE NOT EXISTS (SELECT 1 FROM dim_barangay WHERE barangay_name = ? AND city_municipality_id = ?)", (b, cid, lat, lon, b, cid))

if __name__ == "__main__":
  conn = sqlite3.connect("./data/weathertato.db")
  cur = conn.cursor()
  cur.execute("PRAGMA foreign_keys = ON;")

  with open("./data/philippines_municities_coordinates_2023.csv", "r", encoding="utf-8") as f:
    mdata = list(csv.DictReader(f))

  with open("./data/philippines_barangay_coordinates_2023.csv", "r", encoding="utf-8") as f:
    bdata = list(csv.DictReader(f))

  seed_muni(cur, mdata)
  seed_brgy(cur, bdata)

  conn.commit()
  conn.close()
