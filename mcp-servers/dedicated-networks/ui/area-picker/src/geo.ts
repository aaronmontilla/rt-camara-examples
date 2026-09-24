import type { AreaGeometry, Bounds, Point, ServiceArea } from "./types";

const EARTH_RADIUS_M = 6_371_000;

/** Leaflet expects [lat, lng] pairs — map by field name, never by array position,
 *  since the backend's key order for a boundary point is not guaranteed. */
export function toLatLngTuples(points: Point[]): [number, number][] {
  return points.map((p) => [p.latitude, p.longitude]);
}

export function boundsToLatLngBounds(bounds: Bounds): [[number, number], [number, number]] {
  return [
    [bounds.minLatitude, bounds.minLongitude],
    [bounds.maxLatitude, bounds.maxLongitude],
  ];
}

/** Surface area in m², used to sort covering areas from most to least specific. */
export function surfaceOf(geometry: AreaGeometry): number {
  if (geometry.areaType === "CIRCLE") {
    return Math.PI * geometry.radius ** 2;
  }
  return polygonSurfaceM2(geometry.boundary);
}

/**
 * Shoelace formula over a local equirectangular projection referenced to the
 * boundary's mean latitude, so longitude degrees are scaled by cos(lat) like
 * everywhere else here. Good enough for service-area-sized polygons; not
 * meant for anything continent-sized.
 */
function polygonSurfaceM2(boundary: Point[]): number {
  if (boundary.length < 3) return 0;

  const refLatRad = (mean(boundary.map((p) => p.latitude)) * Math.PI) / 180;
  const projected = boundary.map((p) => ({
    x: EARTH_RADIUS_M * ((p.longitude * Math.PI) / 180) * Math.cos(refLatRad),
    y: EARTH_RADIUS_M * ((p.latitude * Math.PI) / 180),
  }));

  let twiceArea = 0;
  for (let i = 0; i < projected.length; i++) {
    const a = projected[i];
    const b = projected[(i + 1) % projected.length];
    twiceArea += a.x * b.y - b.x * a.y;
  }
  return Math.abs(twiceArea) / 2;
}

function mean(values: number[]): number {
  return values.reduce((sum, v) => sum + v, 0) / values.length;
}

/** Ascending by surface, so the most specific (smallest) area lists first. */
export function sortBySurfaceAscending(areas: ServiceArea[]): ServiceArea[] {
  return [...areas].sort((a, b) => surfaceOf(a.area) - surfaceOf(b.area));
}

/** Great-circle distance in meters (haversine) — used by the optional
 *  draw-a-circle mode to turn a drag distance into a radius. */
export function haversineMeters(a: Point, b: Point): number {
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(b.latitude - a.latitude);
  const dLon = toRad(b.longitude - a.longitude);
  const lat1 = toRad(a.latitude);
  const lat2 = toRad(b.latitude);

  const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) ** 2;
  return 2 * EARTH_RADIUS_M * Math.asin(Math.sqrt(h));
}
