import csv
import sqlite3

def seed_muni(cur: sqlite3.Cursor, data: list[dict]):
    """
    Inserts municipality and city records into the database.
    """
    cur.execute("SELECT LOWER(province_name), province_id FROM dim_province")
    province_map = {row[0]: row[1] for row in cur.fetchall()}

    munis_to_insert = []
    for r in data:
      c = r["municipality_city"].strip()
      p_lower = r["province"].strip().lower()
      lat = float(r["latitude"])
      lon = float(r["longitude"])

      pid = province_map.get(p_lower)
      if pid:
          munis_to_insert.append((c, pid, lat, lon))

    cur.executemany(
      """INSERT OR IGNORE INTO dim_city_municipality (city_municipality_name, province_id, latitude, longitude)
        VALUES (?, ?, ?, ?)""",
      munis_to_insert
    )


def seed_brgy(cur: sqlite3.Cursor, data: list[dict]):
    """
    Inserts barangay records into the database, mapped to their respective municipalities.
    """
    cur.execute("""
      SELECT LOWER(c.city_municipality_name), LOWER(p.province_name), c.city_municipality_id
      FROM dim_city_municipality c
      JOIN dim_province p ON c.province_id = p.province_id
    """)
    city_map = {(row[0], row[1]): row[2] for row in cur.fetchall()}

    rows_to_insert = []
    for r in data:
      b = r["barangay"].strip()
      c = r["municipality_city"].strip().lower()
      p = r["province"].strip().lower()
      lat = float(r["latitude"])
      lon = float(r["longitude"])

      cid = city_map.get((c, p))
      if cid:
        rows_to_insert.append((b, cid, lat, lon))

    cur.executemany(
      """INSERT OR IGNORE INTO dim_barangay (barangay_name, city_municipality_id, latitude, longitude)
        VALUES (?, ?, ?, ?)""",
      rows_to_insert
    )


if __name__ == "__main__":
    conn = sqlite3.connect("./data/weathertato.db", timeout=30.0)
    conn.execute("PRAGMA journal_mode = WAL;")
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    print("Reading CSV files...")
    with open("./data/philippines_municities_coordinates_2023.csv", "r", encoding="utf-8") as f:
      mdata = list(csv.DictReader(f))

    with open("./data/philippines_barangay_coordinates_2023.csv", "r", encoding="utf-8") as f:
      bdata = list(csv.DictReader(f))

    with conn:
        print(f"Seeding {len(mdata)} Municipalities/Cities...")
        seed_muni(cur, mdata)

        print(f"Seeding {len(bdata)} Barangays...")
        seed_brgy(cur, bdata)

    conn.close()
    print("Database seeding completed successfully!")
