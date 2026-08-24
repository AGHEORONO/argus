/**
 * Turning anomaly polygons into words.
 *
 * The map is the only place the geographic position of a detection exists, and a WebGL
 * canvas carries no text. These helpers derive a spoken-language description of where a
 * candidate is, so the detection result stops being visual-only.
 *
 * Pure functions, no dependencies, no React. Everything here is unit-testable.
 */

// La latitudinile astea diferenta fata de un calcul geodezic riguros e sub un metru pe un
// sit de cateva sute de metri — nu merita o dependenta noua pentru asa ceva.
const M_PER_DEG_LAT = 110540;
const mPerDegLon = (lat) => 111320 * Math.cos((lat * Math.PI) / 180);

/** Outer ring of a GeoJSON Polygon, without the repeated closing vertex. */
export function outerRing(feature) {
  const ring = feature?.geometry?.coordinates?.[0];
  if (!Array.isArray(ring) || ring.length < 4) return null;
  const last = ring[ring.length - 1];
  const first = ring[0];
  const closed = last && first && last[0] === first[0] && last[1] === first[1];
  return closed ? ring.slice(0, -1) : ring;
}

/** Centroid as [lon, lat]. Null when the geometry is unusable. */
export function centroid(feature) {
  const ring = outerRing(feature);
  if (!ring) return null;
  const lon = ring.reduce((s, p) => s + p[0], 0) / ring.length;
  const lat = ring.reduce((s, p) => s + p[1], 0) / ring.length;
  return [lon, lat];
}

/** Approximate area in square metres, from the bounding box of the ring. */
export function areaM2(feature) {
  const ring = outerRing(feature);
  if (!ring) return null;
  const lons = ring.map((p) => p[0]);
  const lats = ring.map((p) => p[1]);
  const midLat = (Math.min(...lats) + Math.max(...lats)) / 2;
  const w = (Math.max(...lons) - Math.min(...lons)) * mPerDegLon(midLat);
  const h = (Math.max(...lats) - Math.min(...lats)) * M_PER_DEG_LAT;
  return w * h;
}

/** Bounding box of every feature: { minLon, maxLon, minLat, maxLat }. */
export function bounds(features) {
  const pts = [];
  for (const f of features || []) {
    const ring = outerRing(f);
    if (ring) pts.push(...ring);
  }
  if (pts.length === 0) return null;
  const lons = pts.map((p) => p[0]);
  const lats = pts.map((p) => p[1]);
  return {
    minLon: Math.min(...lons),
    maxLon: Math.max(...lons),
    minLat: Math.min(...lats),
    maxLat: Math.max(...lats),
  };
}

// Grila 3x3 peste intinderea sitului. Verificat pe datele de productie: cele 50 de anomalii
// se imprastie peste 5 zone din 9, deci descrierea chiar discrimineaza — n-ar avea rost daca
// toate ar cadea in aceeasi celula.
const ROWS = ['nord', 'centru', 'sud'];
const COLS = ['vest', 'centru', 'est'];

/** Human zone name for a point inside `bbox`: "nord-vest", "centru", "est", … */
export function zoneName(lon, lat, bbox) {
  if (!bbox) return null;
  const spanLon = bbox.maxLon - bbox.minLon || 1e-9;
  const spanLat = bbox.maxLat - bbox.minLat || 1e-9;
  const col = Math.min(2, Math.max(0, Math.floor(((lon - bbox.minLon) / spanLon) * 3)));
  const row = Math.min(2, Math.max(0, Math.floor(((bbox.maxLat - lat) / spanLat) * 3)));
  const r = ROWS[row];
  const c = COLS[col];
  if (r === 'centru' && c === 'centru') return 'centru';
  if (r === 'centru') return c;
  if (c === 'centru') return r;
  return `${r}-${c}`;
}

/** Distance in metres from the centre of `bbox` to a point. */
export function distanceFromCentreM(lon, lat, bbox) {
  if (!bbox) return null;
  const cLon = (bbox.minLon + bbox.maxLon) / 2;
  const cLat = (bbox.minLat + bbox.maxLat) / 2;
  const dx = (lon - cLon) * mPerDegLon(cLat);
  const dy = (lat - cLat) * M_PER_DEG_LAT;
  return Math.sqrt(dx * dx + dy * dy);
}

/**
 * Everything the UI needs to describe one candidate in words.
 * Returns null rather than a half-filled object when the geometry cannot be read.
 */
export function describeFeature(feature, index, bbox) {
  const c = centroid(feature);
  if (!c) return null;
  const [lon, lat] = c;
  const props = feature.properties || {};
  return {
    rank: props.rank ?? index + 1,
    score: Number(props.anomaly_score || 0),
    lon,
    lat,
    zone: zoneName(lon, lat, bbox),
    areaM2: areaM2(feature),
    distanceM: distanceFromCentreM(lon, lat, bbox),
  };
}

/** Site-level figures: extent, score range, how the candidates spread across zones. */
export function summarise(features) {
  const bbox = bounds(features);
  if (!bbox) return null;
  const midLat = (bbox.minLat + bbox.maxLat) / 2;
  const items = (features || [])
    .map((f, i) => describeFeature(f, i, bbox))
    .filter(Boolean);
  if (items.length === 0) return null;

  const byZone = {};
  for (const it of items) byZone[it.zone] = (byZone[it.zone] || 0) + 1;

  const scores = items.map((i) => i.score);
  const areas = items.map((i) => i.areaM2);
  const uniformArea = Math.max(...areas) - Math.min(...areas) < 1;

  return {
    count: items.length,
    bbox,
    widthM: (bbox.maxLon - bbox.minLon) * mPerDegLon(midLat),
    heightM: (bbox.maxLat - bbox.minLat) * M_PER_DEG_LAT,
    minScore: Math.min(...scores),
    maxScore: Math.max(...scores),
    // Peticurile au dimensiune fixa, deci suprafata per candidat nu distinge nimic: se spune
    // o data in sumar, nu de 50 de ori in lista.
    uniformArea,
    typicalAreaM2: areas[Math.floor(areas.length / 2)],
    byZone,
    // Zonele in ordine descrescatoare, ca sumarul sa poata spune unde se concentreaza.
    zonesRanked: Object.entries(byZone).sort((a, b) => b[1] - a[1]),
    items,
  };
}
