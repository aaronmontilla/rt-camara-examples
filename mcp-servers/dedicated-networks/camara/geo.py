"""
camara/geo.py
─────────────
Pure geometry helpers for service-area geometry.

Used by camara_pick_location to compute a bounding box the map view can
fit(), without pulling in a full GIS dependency. No network calls, no
CAMARA-specific formatting — just plain dicts in, plain dicts out, so this
is straightforward to unit test.

Exported:
  area_bounds(area)       → bbox of one area's geometry, or None if malformed
  combined_bounds(areas)  → bbox covering every area, or None if there are none
"""

import json
import math
from typing import Any, Dict, List, Optional, TypedDict
from urllib.parse import quote

# Meters per degree of latitude (~constant on Earth's surface).
_METERS_PER_DEGREE = 111_320.0


class Bounds(TypedDict):
    minLatitude: float
    maxLatitude: float
    minLongitude: float
    maxLongitude: float


def _circle_bounds(geometry: Dict[str, Any]) -> Optional[Bounds]:
    """Bbox of a CIRCLE, expanding the center by its radius (in meters)."""
    center = geometry.get("center") or {}
    lat = center.get("latitude")
    lon = center.get("longitude")
    radius = geometry.get("radius")
    if lat is None or lon is None or radius is None:
        return None

    dlat = radius / _METERS_PER_DEGREE
    # A degree of longitude shrinks with cos(latitude); clamp near the poles
    # to avoid dividing by ~0.
    dlon = radius / (_METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 1e-6))

    return {
        "minLatitude": lat - dlat,
        "maxLatitude": lat + dlat,
        "minLongitude": lon - dlon,
        "maxLongitude": lon + dlon,
    }


def _polygon_bounds(geometry: Dict[str, Any]) -> Optional[Bounds]:
    """Bbox of a POLYGON's boundary vertices."""
    boundary = geometry.get("boundary") or []
    lats = [p["latitude"] for p in boundary if "latitude" in p and "longitude" in p]
    lons = [p["longitude"] for p in boundary if "latitude" in p and "longitude" in p]
    if not lats:
        return None

    return {
        "minLatitude": min(lats),
        "maxLatitude": max(lats),
        "minLongitude": min(lons),
        "maxLongitude": max(lons),
    }


def area_bounds(area: Dict[str, Any]) -> Optional[Bounds]:
    """Bounding box of one service area's geometry.

    Returns None for an unrecognized areaType or missing coordinates, so a
    malformed entry is silently skipped by combined_bounds() rather than
    raising.
    """
    geometry = area.get("area") or {}
    area_type = geometry.get("areaType")
    if area_type == "CIRCLE":
        return _circle_bounds(geometry)
    if area_type == "POLYGON":
        return _polygon_bounds(geometry)
    return None


_CIRCLE_SEGMENTS = 64


def _circle_ring(geometry: Dict[str, Any]) -> Optional[List[List[float]]]:
    """Closed [lon, lat] ring approximating a CIRCLE (GeoJSON has no circles)."""
    center = geometry.get("center") or {}
    lat = center.get("latitude")
    lon = center.get("longitude")
    radius = geometry.get("radius")
    if lat is None or lon is None or radius is None:
        return None

    dlat = radius / _METERS_PER_DEGREE
    dlon = radius / (_METERS_PER_DEGREE * max(math.cos(math.radians(lat)), 1e-6))
    ring = [
        [
            lon + dlon * math.cos(2 * math.pi * i / _CIRCLE_SEGMENTS),
            lat + dlat * math.sin(2 * math.pi * i / _CIRCLE_SEGMENTS),
        ]
        for i in range(_CIRCLE_SEGMENTS)
    ]
    ring.append(ring[0])
    return ring


def _polygon_ring(geometry: Dict[str, Any]) -> Optional[List[List[float]]]:
    """Closed [lon, lat] ring from a POLYGON's boundary."""
    ring = [
        [p["longitude"], p["latitude"]]
        for p in (geometry.get("boundary") or [])
        if "latitude" in p and "longitude" in p
    ]
    if len(ring) < 3:
        return None
    if ring[0] != ring[-1]:
        ring.append(ring[0])
    return ring


def area_to_geojson(area: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """GeoJSON Feature for one service area, or None if the geometry is malformed."""
    geometry = area.get("area") or {}
    area_type = geometry.get("areaType")
    if area_type == "CIRCLE":
        ring = _circle_ring(geometry)
    elif area_type == "POLYGON":
        ring = _polygon_ring(geometry)
    else:
        return None
    if ring is None:
        return None

    return {
        "type": "Feature",
        "properties": {
            "id": area.get("id"),
            "name": area.get("name"),
            "description": area.get("description"),
            "areaType": area_type,
        },
        "geometry": {"type": "Polygon", "coordinates": [ring]},
    }


def areas_to_geojson(areas: List[Dict[str, Any]]) -> Dict[str, Any]:
    """GeoJSON FeatureCollection covering every area with usable geometry."""
    features = [f for f in (area_to_geojson(a) for a in areas) if f is not None]
    return {"type": "FeatureCollection", "features": features}


def geojson_url(geojson: Dict[str, Any]) -> str:
    """geojson.io URL that renders the given GeoJSON (data is embedded in the URL)."""
    payload = json.dumps(geojson, separators=(",", ":"))
    return "https://geojson.io/#data=data:application/json," + quote(payload, safe="")


def area_geojson_url(area: Dict[str, Any]) -> Optional[str]:
    """geojson.io URL visualising one area, or None if its geometry is unusable."""
    feature = area_to_geojson(area)
    return geojson_url(feature) if feature else None


def combined_bounds(areas: List[Dict[str, Any]]) -> Optional[Bounds]:
    """Bounding box covering every area's geometry, or None if none apply."""
    boxes = [b for b in (area_bounds(a) for a in areas) if b is not None]
    if not boxes:
        return None

    return {
        "minLatitude": min(b["minLatitude"] for b in boxes),
        "maxLatitude": max(b["maxLatitude"] for b in boxes),
        "minLongitude": min(b["minLongitude"] for b in boxes),
        "maxLongitude": max(b["maxLongitude"] for b in boxes),
    }
