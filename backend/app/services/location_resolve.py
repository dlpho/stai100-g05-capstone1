import sqlite3
import os
from typing import Optional, Tuple
from models.schemas import LocationEntity

DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "weathertato.db")
)

def _get_connection():
    """
    Creates and returns a sqlite3 database connection to the weathertato database.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def resolve_location_sqlite(query_str: str) -> Tuple[Optional[LocationEntity], str]:
    """
    Returns (LocationEntity, status)
    status can be: "RESOLVED", "AMBIGUOUS", "NOT_FOUND", "UNSUPPORTED_REGION"
    """
    if not query_str or not query_str.strip():
        return None, "NOT_FOUND"

    import re
    query_clean = re.sub(r'[^\w\s]', ' ', query_str.strip()).lower()
    
    conn = _get_connection()
    try:
        cur = conn.cursor()

        # Strategy 1: Exact Match (Case-Insensitive)
        cur.execute('''
            SELECT province_id, province_name, region_name, latitude, longitude
            FROM dim_province
            WHERE LOWER(province_name) = ?
        ''', (query_clean,))
        prov_matches = cur.fetchall()

        cur.execute('''
            SELECT c.city_municipality_name, c.latitude, c.longitude,
                   p.province_id, p.province_name, p.region_name, p.latitude as p_lat, p.longitude as p_lon
            FROM dim_city_municipality c
            JOIN dim_province p ON c.province_id = p.province_id
            WHERE LOWER(c.city_municipality_name) = ?
        ''', (query_clean,))
        muni_matches = cur.fetchall()

        cur.execute('''
            SELECT b.barangay_name, b.latitude, b.longitude,
                   c.city_municipality_name, 
                   p.province_id, p.province_name, p.region_name, p.latitude as p_lat, p.longitude as p_lon
            FROM dim_barangay b
            JOIN dim_city_municipality c ON b.city_municipality_id = c.city_municipality_id
            JOIN dim_province p ON c.province_id = p.province_id
            WHERE LOWER(b.barangay_name) = ?
        ''', (query_clean,))
        brgy_matches = cur.fetchall()

        if len(prov_matches) == 1:
            return _build_entity_from_match(prov_matches, [], [], query_str)
        elif len(prov_matches) > 1:
            return None, "AMBIGUOUS"
            
        if len(muni_matches) == 1:
            return _build_entity_from_match([], muni_matches, [], query_str)
        elif len(muni_matches) > 1:
            return None, "AMBIGUOUS"
            
        if len(brgy_matches) == 1:
            return _build_entity_from_match([], [], brgy_matches, query_str)
        elif len(brgy_matches) > 1:
            return None, "AMBIGUOUS"

        # Strategy 2: Fallback Concatenated LIKE Match
        words = [w for w in query_clean.split() if w not in ('in', 'the', 'of', 'city', 'municipality', 'province')]
        if not words:
            return None, "NOT_FOUND"

        like_clauses_brgy = " AND ".join(["(LOWER(b.barangay_name) || ' ' || LOWER(c.city_municipality_name) || ' ' || LOWER(p.province_name)) LIKE ?"] * len(words))
        like_clauses_muni = " AND ".join(["(LOWER(c.city_municipality_name) || ' ' || LOWER(p.province_name)) LIKE ?"] * len(words))
        like_clauses_prov = " AND ".join(["LOWER(p.province_name) LIKE ?"] * len(words))
        
        params = [f"%{w}%" for w in words]

        cur.execute(f'''
            SELECT b.barangay_name, b.latitude, b.longitude,
                   c.city_municipality_name, 
                   p.province_id, p.province_name, p.region_name, p.latitude as p_lat, p.longitude as p_lon
            FROM dim_barangay b
            JOIN dim_city_municipality c ON b.city_municipality_id = c.city_municipality_id
            JOIN dim_province p ON c.province_id = p.province_id
            WHERE {like_clauses_brgy}
        ''', params)
        brgy_like_matches = cur.fetchall()

        cur.execute(f'''
            SELECT c.city_municipality_name, c.latitude, c.longitude,
                   p.province_id, p.province_name, p.region_name, p.latitude as p_lat, p.longitude as p_lon
            FROM dim_city_municipality c
            JOIN dim_province p ON c.province_id = p.province_id
            WHERE {like_clauses_muni}
        ''', params)
        muni_like_matches = cur.fetchall()

        cur.execute(f'''
            SELECT province_id, province_name, region_name, latitude, longitude
            FROM dim_province p
            WHERE {like_clauses_prov}
        ''', params)
        prov_like_matches = cur.fetchall()

        if len(prov_like_matches) == 1:
            return _build_entity_from_match(prov_like_matches, [], [], query_str)
        elif len(prov_like_matches) > 1:
            return None, "AMBIGUOUS"
            
        if len(muni_like_matches) == 1:
            return _build_entity_from_match([], muni_like_matches, [], query_str)
        elif len(muni_like_matches) > 1:
            return None, "AMBIGUOUS"
            
        if len(brgy_like_matches) == 1:
            return _build_entity_from_match([], [], brgy_like_matches, query_str)
        elif len(brgy_like_matches) > 1:
            return None, "AMBIGUOUS"
        else:
            return None, "NOT_FOUND"

    except sqlite3.Error as e:
        print(e)
        return None, "NOT_FOUND"
    finally:
        conn.close()

def _build_entity_from_match(prov_matches, muni_matches, brgy_matches, original_query) -> Tuple[Optional[LocationEntity], str]:
    """
    Constructs a LocationEntity object from the matching database records.
    Returns the entity and a status string ('RESOLVED' or 'UNSUPPORTED_REGION').
    """
    entity = None
    if prov_matches:
        r = prov_matches[0]
        entity = LocationEntity(
            original_query=original_query,
            resolved_name=r['province_name'],
            granularity="province",
            province=r['province_name'],
            region=r['region_name'],
            latitude=r['latitude'],
            longitude=r['longitude'],
            province_latitude=r['latitude'],
            province_longitude=r['longitude'],
            province_id=r['province_id']
        )
    elif muni_matches:
        r = muni_matches[0]
        entity = LocationEntity(
            original_query=original_query,
            resolved_name=f"{r['city_municipality_name']}, {r['province_name']}",
            granularity="municipality_city",
            province=r['province_name'],
            region=r['region_name'],
            latitude=r['latitude'],
            longitude=r['longitude'],
            province_latitude=r['p_lat'],
            province_longitude=r['p_lon'],
            province_id=r['province_id']
        )
    elif brgy_matches:
        r = brgy_matches[0]
        entity = LocationEntity(
            original_query=original_query,
            resolved_name=f"{r['barangay_name']}, {r['city_municipality_name']}, {r['province_name']}",
            granularity="barangay",
            province=r['province_name'],
            region=r['region_name'],
            latitude=r['latitude'],
            longitude=r['longitude'],
            province_latitude=r['p_lat'],
            province_longitude=r['p_lon'],
            province_id=r['province_id']
        )
    
    if entity.region != "Region III (Central Luzon)":
        return None, "UNSUPPORTED_REGION"
    
    return entity, "RESOLVED"
