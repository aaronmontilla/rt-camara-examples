import { App } from "@modelcontextprotocol/ext-apps";
import L from "leaflet";
import "./mcp-app.css";
import { boundsToLatLngBounds, haversineMeters, sortBySurfaceAscending, toLatLngTuples } from "./geo";
import type { MinimalToolResult, PickLocationResult, RetrieveAreasResult, ServiceArea } from "./types";

const DEFAULT_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png";

const DIM_STYLE: L.PathOptions = { color: "#6b7280", weight: 1, fillOpacity: 0.08, opacity: 0.6 };
const HIGHLIGHT_STYLE: L.PathOptions = { color: "#2563eb", weight: 2, fillOpacity: 0.25, opacity: 0.9 };
const DRAW_STYLE: L.PathOptions = { color: "#2563eb", weight: 2, dashArray: "4 4", fillOpacity: 0.05 };
const MARKER_STYLE: L.CircleMarkerOptions = {
  radius: 7,
  color: "#2563eb",
  weight: 2,
  fillColor: "#ffffff",
  fillOpacity: 1,
};

const panelHint = requireEl("panel-mode-hint");
const panelError = requireEl("panel-error");
const panelList = requireEl("panel-list");
const drawModeToggle = requireEl("draw-mode-toggle") as HTMLInputElement;

let map: L.Map | undefined;
const areaLayers = new Map<string, L.Layer>();
let clickMarker: L.CircleMarker | undefined;
let selectionConfirmed = false;

// Draw-a-circle mode (optional extension): mousedown fixes the center,
// mousemove resizes a preview circle, mouseup queries overlappingArea.
let drawCenter: L.LatLng | undefined;
let drawPreview: L.Circle | undefined;

const app = new App({ name: "camara-area-picker", version: "0.1.0" });

// Registered before connect(): the SDK warns if handlers are attached after
// the ui/notifications/initialized handshake, and the initial render depends
// on catching the very first tool result.
app.ontoolresult = (result: MinimalToolResult) => {
  if (result.isError) {
    showError(textOf(result) ?? "No se pudo cargar el mapa.");
    return;
  }
  const data = parseResult<PickLocationResult>(result);
  if (data) initializeMap(data);
};

main().catch((err) => {
  console.error("[camara-area-picker] failed to connect:", err);
  showError("No se pudo conectar con el host de MCP Apps.");
});

async function main(): Promise<void> {
  await app.connect();
  applyTheme();
  drawModeToggle.addEventListener("change", onDrawModeToggle);
}

function applyTheme(): void {
  const theme = app.getHostContext?.()?.theme;
  if (theme === "dark" || theme === "light") {
    document.documentElement.dataset.theme = theme;
  }
}

function requireEl(id: string): HTMLElement {
  const el = document.getElementById(id);
  if (!el) throw new Error(`missing #${id} in area_picker.html`);
  return el;
}

function textOf(result: MinimalToolResult): string | undefined {
  return result.content?.find((c) => c.type === "text")?.text;
}

function parseResult<T>(result: MinimalToolResult): T | undefined {
  const text = textOf(result);
  if (!text) return undefined;
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}

function showError(message: string): void {
  panelError.textContent = message;
  panelError.hidden = false;
}

function clearError(): void {
  panelError.hidden = true;
  panelError.textContent = "";
}

// ─── Initial render ─────────────────────────────────────────────────────────

function initializeMap(data: PickLocationResult): void {
  if (map) return; // a second tool result (e.g. re-open) shouldn't re-init

  const tileUrl = data.tileUrl || DEFAULT_TILE_URL;

  map = L.map("map");
  L.tileLayer(tileUrl, {
    maxZoom: 19,
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors',
  }).addTo(map);

  renderAllAreasDim(data.areas);

  if (data.center) {
    map.setView([data.center.latitude, data.center.longitude], data.zoom ?? 13);
  } else if (data.bounds) {
    map.fitBounds(boundsToLatLngBounds(data.bounds), { padding: [24, 24] });
  } else {
    map.setView([0, 0], 2);
  }

  if (data.areas.length === 0) {
    panelHint.textContent = data.message ?? "No hay service areas disponibles.";
  }

  map.on("click", onMapClick);
  map.on("mousedown", onDrawMouseDown);
  map.on("mousemove", onDrawMouseMove);
  map.on("mouseup", onDrawMouseUp);
}

function renderAllAreasDim(areas: ServiceArea[]): void {
  areaLayers.forEach((layer) => layer.remove());
  areaLayers.clear();

  for (const area of areas) {
    const layer = layerFor(area, DIM_STYLE);
    if (layer && map) {
      layer.addTo(map);
      areaLayers.set(area.id, layer);
    }
  }
}

function layerFor(area: ServiceArea, style: L.PathOptions): L.Layer | undefined {
  const geometry = area.area;
  if (geometry.areaType === "CIRCLE") {
    return L.circle([geometry.center.latitude, geometry.center.longitude], {
      radius: geometry.radius,
      ...style,
    });
  }
  if (geometry.areaType === "POLYGON") {
    return L.polygon(toLatLngTuples(geometry.boundary), style);
  }
  return undefined;
}

function highlightAreas(covering: ServiceArea[]): void {
  const coveringIds = new Set(covering.map((a) => a.id));
  areaLayers.forEach((layer, id) => {
    if (layer instanceof L.Path) {
      layer.setStyle(coveringIds.has(id) ? HIGHLIGHT_STYLE : DIM_STYLE);
    }
  });
}

// ─── Click-to-query flow ────────────────────────────────────────────────────

async function onMapClick(e: L.LeafletMouseEvent): Promise<void> {
  if (selectionConfirmed || drawModeToggle.checked) return;

  clearError();
  const { lat, lng } = e.latlng;

  clickMarker?.remove();
  clickMarker = L.circleMarker([lat, lng], MARKER_STYLE).addTo(map!);

  panelHint.textContent = "Buscando áreas en este punto…";
  panelList.innerHTML = "";

  try {
    const result = (await app.callServerTool({
      name: "camara_retrieve_service_areas",
      arguments: {
        params: { atLocation: { latitude: lat, longitude: lng }, response_format: "json" },
      },
    })) as MinimalToolResult;

    if (result.isError) {
      showError(textOf(result) ?? "Error al consultar las áreas.");
      panelHint.textContent = "Haz clic en el mapa para volver a intentarlo.";
      return;
    }

    const data = parseResult<RetrieveAreasResult>(result);
    renderCoverageResult(data?.areas ?? [], lat, lng);
  } catch (err) {
    showError(err instanceof Error ? err.message : "Error al consultar las áreas.");
  }
}

function renderCoverageResult(areas: ServiceArea[], lat: number, lng: number): void {
  highlightAreas(areas);
  panelList.innerHTML = "";

  if (areas.length === 0) {
    panelHint.textContent = "Sin cobertura en este punto.";
    return;
  }

  panelHint.textContent = `${areas.length} área(s) en este punto, de menor a mayor superficie:`;
  for (const area of sortBySurfaceAscending(areas)) {
    panelList.appendChild(buildAreaCard(area, lat, lng));
  }
}

function buildAreaCard(area: ServiceArea, lat: number, lng: number): HTMLElement {
  const card = document.createElement("div");
  card.className = "area-card";

  const title = document.createElement("h3");
  title.textContent = area.name || area.id;
  card.appendChild(title);

  const typeTag = document.createElement("span");
  typeTag.className = "area-type";
  typeTag.textContent = area.area.areaType;
  card.appendChild(typeTag);

  const dl = document.createElement("dl");
  appendField(dl, "networkProfiles", (area.networkProfiles ?? []).join(", ") || "none");
  appendField(
    dl,
    "qosProfiles",
    area.qosProfiles && area.qosProfiles.length > 0
      ? area.qosProfiles.join(", ")
      : "none (solo admite creación por networkProfileId)",
  );
  card.appendChild(dl);

  const button = document.createElement("button");
  button.type = "button";
  button.textContent = "Usar esta área";
  button.addEventListener("click", () => void confirmArea(area, lat, lng, card, button));
  card.appendChild(button);

  return card;
}

function appendField(dl: HTMLDListElement, label: string, value: string): void {
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.textContent = value;
  dl.appendChild(dt);
  dl.appendChild(dd);
}

// ─── Confirmation ───────────────────────────────────────────────────────────

async function confirmArea(
  area: ServiceArea,
  lat: number,
  lng: number,
  card: HTMLElement,
  button: HTMLButtonElement,
): Promise<void> {
  if (selectionConfirmed) return;
  selectionConfirmed = true;

  document.querySelectorAll<HTMLButtonElement>(".area-card button").forEach((b) => {
    b.disabled = true;
  });
  button.textContent = "Seleccionada";
  button.classList.add("confirmed-label");
  card.classList.add("confirmed");

  const latStr = lat.toFixed(6);
  const lngStr = lng.toFixed(6);
  const networkProfiles = (area.networkProfiles ?? []).join(", ") || "none";
  const qosProfiles = (area.qosProfiles ?? []).join(", ") || "none";
  const label = area.name ?? area.id;

  // Per spec: updateModelContext first (overwrites prior view context with a
  // structured block), then sendMessage (this is the one that triggers a
  // model turn).
  app.updateModelContext({
    content: [
      {
        type: "text",
        text:
          `Ubicación seleccionada en el mapa:\n` +
          `- Coordenadas: ${latStr}, ${lngStr}\n` +
          `- serviceAreaId: ${area.id}\n` +
          `- Nombre: ${label}\n` +
          `- networkProfiles: ${networkProfiles}\n` +
          `- qosProfiles: ${qosProfiles}`,
      },
    ],
  });

  await app.sendMessage({
    role: "user",
    content: [
      {
        type: "text",
        text:
          `He seleccionado en el mapa el punto ${latStr}, ${lngStr} → área "${label}" ` +
          `(serviceAreaId ${area.id}). Continúa con la creación de la red.`,
      },
    ],
  });

  panelHint.textContent = "Selección confirmada. Continúa la conversación con Claude.";
}

// ─── Optional extension: draw-a-circle mode ────────────────────────────────

function onDrawModeToggle(): void {
  if (!map) return;
  if (drawModeToggle.checked) {
    map.dragging.disable();
    panelHint.textContent = "Clic y arrastra para dibujar un círculo de búsqueda.";
  } else {
    map.dragging.enable();
    drawPreview?.remove();
    drawPreview = undefined;
    drawCenter = undefined;
    panelHint.textContent = "Haz clic en el mapa para ver qué áreas cubren ese punto.";
  }
}

function onDrawMouseDown(e: L.LeafletMouseEvent): void {
  if (!drawModeToggle.checked || !map) return;
  drawCenter = e.latlng;
  drawPreview?.remove();
  drawPreview = L.circle(drawCenter, { radius: 0, ...DRAW_STYLE }).addTo(map);
}

function onDrawMouseMove(e: L.LeafletMouseEvent): void {
  if (!drawModeToggle.checked || !drawCenter || !drawPreview) return;
  const radius = haversineMeters(
    { latitude: drawCenter.lat, longitude: drawCenter.lng },
    { latitude: e.latlng.lat, longitude: e.latlng.lng },
  );
  drawPreview.setRadius(radius);
}

async function onDrawMouseUp(e: L.LeafletMouseEvent): Promise<void> {
  if (!drawModeToggle.checked || !drawCenter || selectionConfirmed) return;

  const radius = haversineMeters(
    { latitude: drawCenter.lat, longitude: drawCenter.lng },
    { latitude: e.latlng.lat, longitude: e.latlng.lng },
  );
  const center = { latitude: drawCenter.lat, longitude: drawCenter.lng };
  drawCenter = undefined;

  if (radius < 10) return; // treat a near-zero drag as a non-drag, ignore it

  clearError();
  panelHint.textContent = "Buscando áreas que solapan este círculo…";
  panelList.innerHTML = "";

  try {
    const result = (await app.callServerTool({
      name: "camara_retrieve_service_areas",
      arguments: {
        params: {
          overlappingArea: { areaType: "CIRCLE", center, radius },
          response_format: "json",
        },
      },
    })) as MinimalToolResult;

    if (result.isError) {
      showError(textOf(result) ?? "Error al consultar las áreas.");
      return;
    }

    const data = parseResult<RetrieveAreasResult>(result);
    // Confirmation still binds to the circle's center coordinates.
    renderCoverageResult(data?.areas ?? [], center.latitude, center.longitude);
  } catch (err) {
    showError(err instanceof Error ? err.message : "Error al consultar las áreas.");
  }
}
