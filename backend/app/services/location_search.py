"""Search PSGC CSV files for location names matching a prompt.

Uses hierarchical matching: province first, then municipality/barangay
filtered by parent, yielding compact, high-relevance results for the LLM.
"""

import csv
import os
from typing import Optional

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BASE_DIR)
_CSV_DIR = os.path.abspath(os.path.join(_PROJECT_ROOT, os.pardir, os.pardir, "data"))

BARANGAY_CSV = os.path.join(_CSV_DIR, "philippines_barangay_coordinates_2023.csv")
MUNICITY_CSV = os.path.join(_CSV_DIR, "philippines_municities_coordinates_2023.csv")
PROVDIST_CSV = os.path.join(_CSV_DIR, "philippines_provdists_coordinates_2023.csv")

BARANGAY_COLS = ["barangay", "municipality_city", "province", "region", "latitude", "longitude"]
MUNICITY_COLS = ["municipality_city", "province", "region", "latitude", "longitude"]
PROVDIST_COLS = ["province", "region", "latitude", "longitude"]

# Cache
_cache: dict[str, list[dict]] = {}


def _load_csv(path: str) -> list[dict]:
    if path not in _cache:
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows.append(row)
        _cache[path] = rows
    return _cache[path]


def _clean_prompt(prompt: str) -> list[str]:
    """Extract location-relevant words from prompt, skipping noise."""
    noise = {
        "weather", "forecast", "temperature", "rain", "humidity", "wind",
        "storm", "typhoon", "heat", "climate", "uv", "visibility", "pressure",
        "in", "the", "of", "for", "is", "at", "what", "how", "want", "get",
        "please", "can", "you", "tell", "show", "give", "me", "i", "to", "a",
        "el", "nino", "nina", "la", "del", "de",
    }
    return [w.lower().strip(",.;:!?()[]\"'")
            for w in prompt.split()
            if w.lower().strip(",.;:!?()[]\"'") not in noise
            and len(w.lower().strip(",.;:!?()[]\"'")) >= 4]


def _matches_any(name: str, search_words: list[str]) -> bool:
    """Check if any search word appears in the name."""
    name_lower = name.lower()
    return any(w in name_lower for w in search_words)


def _filter_rows(rows: list[dict], col: str, words: list[str]) -> list[dict]:
    """Return rows where the column value contains at least one search word."""
    results = []
    for row in rows:
        val = row[col].lower()
        if any(w in val for w in words):
            results.append(row)
    return results


def search_location(prompt: str) -> list[str]:
    """Hierarchical search: province → municipality → barangay.

    Returns compact reference lines for the LLM prompt.
    """
    words = _clean_prompt(prompt)
    if not words:
        return []

    provinces = _load_csv(PROVDIST_CSV)
    munities = _load_csv(MUNICITY_CSV)
    brgys = _load_csv(BARANGAY_CSV)

    # 1. Find matching provinces
    matched_provinces = _filter_rows(provinces, "province", words)

    result_lines: list[str] = []
    seen: set[str] = set()

    # 2. For each matched province, add it + its matching munities + brgys
    for prov in matched_provinces[:10]:
        pname = prov["province"]
        key = f"province|{pname}"
        if key not in seen:
            seen.add(key)
            cols = [prov[c] for c in PROVDIST_COLS]
            result_lines.append(f"[province] {' | '.join(cols)}")

        # Find matching municipalities in this province
        prov_munities = [m for m in munities if m["province"] == pname]
        matched_munities = [m for m in prov_munities if _matches_any(m["municipality_city"], words)]

        for muni in matched_munities[:8]:
            mname = muni["municipality_city"]
            key = f"municipality_city|{mname}|{pname}"
            if key not in seen:
                seen.add(key)
                cols = [muni[c] for c in MUNICITY_COLS]
                result_lines.append(f"[municipality_city] {' | '.join(cols)}")

            # Find matching barangays in this municipality
            muni_brgys = [b for b in brgys
                          if b["municipality_city"] == mname and b["province"] == pname]
            matched_brgys = [b for b in muni_brgys if _matches_any(b["barangay"], words)]

            for brgy in matched_brgys[:5]:
                key = f"barangay|{brgy['barangay']}|{mname}|{pname}"
                if key not in seen:
                    seen.add(key)
                    cols = [brgy[c] for c in BARANGAY_COLS]
                    result_lines.append(f"[barangay] {' | '.join(cols)}")

    return result_lines
