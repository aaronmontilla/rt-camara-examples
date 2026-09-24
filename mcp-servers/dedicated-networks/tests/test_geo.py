"""
tests/test_geo.py
──────────────────
Bounding-box math for CIRCLE and POLYGON service areas, using the exact
sample payload from CAMARA_MAP_PICKER_SPEC.md (Roland Garros CIRCLE +
Stade de France POLYGON, camelCase/lowercase-vs-uppercase UUIDs and all).
"""

import math

from camara.geo import area_bounds, combined_bounds

CIRCLE_AREA = {
    "id": "625b2d4b-4da7-4f07-9169-e60ffdf76671",
    "name": "Roland Garros Tennis Courts",
    "area": {
        "areaType": "CIRCLE",
        "center": {"latitude": 48.845867, "longitude": 2.253156},
        "radius": 1000,
    },
    "networkProfiles": ["7e54f738-...", "3016629c-..."],
    "qosProfiles": ["QOS_S", "58e104f7-..."],
}

POLYGON_AREA = {
    "area": {
        "areaType": "POLYGON",
        "boundary": [
            {"longitude": 2.35941, "latitude": 48.92493},
            {"longitude": 2.35968, "latitude": 48.92497},
        ],
    },
    "id": "C9019B9D-FD78-497C-AE07-636CD60202AD",
    "name": "Stade de France",
    "networkProfiles": ["914BA5A4-...", "5961C65A-..."],
}


def test_circle_bounds_expand_by_radius_in_degrees():
    bounds = area_bounds(CIRCLE_AREA)
    assert bounds is not None

    lat, lon, radius = 48.845867, 2.253156, 1000
    dlat = radius / 111_320.0
    dlon = radius / (111_320.0 * math.cos(math.radians(lat)))

    assert bounds["minLatitude"] == lat - dlat
    assert bounds["maxLatitude"] == lat + dlat
    assert bounds["minLongitude"] == lon - dlon
    assert bounds["maxLongitude"] == lon + dlon
    # A CIRCLE's bbox must straddle its own center.
    assert bounds["minLatitude"] < lat < bounds["maxLatitude"]
    assert bounds["minLongitude"] < lon < bounds["maxLongitude"]


def test_polygon_bounds_span_boundary_vertices():
    bounds = area_bounds(POLYGON_AREA)
    assert bounds == {
        "minLatitude": 48.92493,
        "maxLatitude": 48.92497,
        "minLongitude": 2.35941,
        "maxLongitude": 2.35968,
    }


def test_combined_bounds_covers_both_areas():
    bounds = combined_bounds([CIRCLE_AREA, POLYGON_AREA])
    assert bounds is not None

    circle = area_bounds(CIRCLE_AREA)
    polygon = area_bounds(POLYGON_AREA)
    assert bounds["minLatitude"] == min(circle["minLatitude"], polygon["minLatitude"])
    assert bounds["maxLatitude"] == max(circle["maxLatitude"], polygon["maxLatitude"])
    assert bounds["minLongitude"] == min(circle["minLongitude"], polygon["minLongitude"])
    assert bounds["maxLongitude"] == max(circle["maxLongitude"], polygon["maxLongitude"])


def test_combined_bounds_empty_list_is_none():
    assert combined_bounds([]) is None


def test_area_bounds_ignores_unknown_area_type():
    assert area_bounds({"area": {"areaType": "SQUARE"}}) is None


def test_combined_bounds_skips_malformed_entries():
    malformed = {"area": {"areaType": "CIRCLE", "center": {"latitude": 1.0}}}  # no radius
    assert combined_bounds([malformed, POLYGON_AREA]) == area_bounds(POLYGON_AREA)
