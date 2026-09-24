export interface Point {
  latitude: number;
  longitude: number;
}

export interface CircleGeometry {
  areaType: "CIRCLE";
  center: Point;
  radius: number;
}

export interface PolygonGeometry {
  areaType: "POLYGON";
  boundary: Point[];
}

export type AreaGeometry = CircleGeometry | PolygonGeometry;

export interface ServiceArea {
  id: string;
  name?: string;
  description?: string;
  area: AreaGeometry;
  networkProfiles?: string[];
  qosProfiles?: string[];
}

export interface Bounds {
  minLatitude: number;
  maxLatitude: number;
  minLongitude: number;
  maxLongitude: number;
}

/** What camara_pick_location returns. */
export interface PickLocationResult {
  areas: ServiceArea[];
  bounds: Bounds | null;
  center?: Point;
  zoom?: number;
  tileUrl: string;
  message?: string;
}

/** What camara_retrieve_service_areas returns with response_format="json". */
export interface RetrieveAreasResult {
  areas: ServiceArea[];
  count: number;
}

/** Minimal structural shape we rely on from CallToolResult — loose on purpose
 *  so it matches whatever the real SDK type shapes content blocks as. */
export interface MinimalToolResult {
  content?: Array<{ type: string; text?: string }>;
  isError?: boolean;
}
