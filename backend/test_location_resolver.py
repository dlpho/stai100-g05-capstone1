import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "app")))

from app.services.location_resolve import resolve_location_sqlite
from app.models.schemas import LocationEntity

def test_resolve_province_exact():
    entity, status = resolve_location_sqlite("Pampanga")
    assert status == "RESOLVED"
    assert entity.granularity == "province"
    assert entity.province == "Pampanga"
    assert entity.region == "Region III (Central Luzon)"
    assert entity.latitude == entity.province_latitude
    assert entity.longitude == entity.province_longitude
    print("test_resolve_province_exact passed!")

def test_resolve_municipality_exact():
    entity, status = resolve_location_sqlite("Bacolor")
    assert status == "RESOLVED"
    assert entity.granularity == "municipality_city"
    assert entity.province == "Pampanga"
    print("test_resolve_municipality_exact passed!")

def test_resolve_barangay_fallback():
    entity, status = resolve_location_sqlite("San Isidro, Pampanga")
    assert status in ["RESOLVED", "AMBIGUOUS"]
    print("test_resolve_barangay_fallback passed!")

def test_ambiguous_location():
    entity, status = resolve_location_sqlite("San Isidro")
    assert status == "AMBIGUOUS"
    assert entity is None
    print("test_ambiguous_location passed!")

def test_unsupported_region():
    entity, status = resolve_location_sqlite("Cebu")
    assert status == "UNSUPPORTED_REGION"
    assert entity is None
    print("test_unsupported_region passed!")

def test_not_found():
    entity, status = resolve_location_sqlite("Atlantis")
    assert status == "NOT_FOUND"
    assert entity is None
    print("test_not_found passed!")

if __name__ == "__main__":
    test_resolve_province_exact()
    test_resolve_municipality_exact()
    test_resolve_barangay_fallback()
    test_ambiguous_location()
    test_unsupported_region()
    test_not_found()
    print("All location resolver tests passed!")
