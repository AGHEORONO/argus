import React, { useEffect, useMemo, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';
import { bounds as anomalyBounds, summarise, zoneName } from './geo';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const DEFAULT_CENTER = [-78.43072, 0.01334];
const DEFAULT_ZOOM = 16.5;

// Starile vin in engleza de la backend; pagina e lang="ro", deci se traduc inainte de
// afisare, altfel o voce sintetica romaneasca le pronunta neinteligibil.
const STATUS_LABELS = {
  pending: 'in asteptare',
  running: 'in curs',
  done: 'finalizat',
  failed: 'esuat',
};

// Number.toFixed produce "0.81", pe care o voce sintetica romaneasca il citeste
// "zero punct optzeci si unu". In romana separatorul zecimal e virgula.
const nf2 = new Intl.NumberFormat('ro-RO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const nf4 = new Intl.NumberFormat('ro-RO', { minimumFractionDigits: 4, maximumFractionDigits: 4 });
const fmt2 = (x) => nf2.format(Number(x) || 0);
const fmt4 = (x) => nf4.format(Number(x) || 0);

// Numeralele romanesti cer particula "de" cand ultimele doua cifre sunt 0 sau intre 20 si 99:
// "50 de anomalii", dar "15 anomalii".
const de = (n) => { const r = Math.abs(n) % 100; return (r === 0 || r >= 20) ? 'de ' : ''; };
const anomaliiText = (n) =>
  n === 0 ? 'nicio anomalie' : n === 1 ? 'o anomalie' : `${n} ${de(n)}anomalii`;
const metriText = (n) => (n === 1 ? 'un metru' : `${n} ${de(n)}metri`);
const zileText = (n) => (n === 1 ? 'o zi' : `${n} ${de(n)}zile`);
const luniText = (n) => (n === 1 ? 'o lună' : `${n} ${de(n)}luni`);
const secundeText = (n) => (n === 1 ? 'o secundă' : `${n} ${de(n)}secunde`);
const intervalText = (z) =>
  z < 60 ? zileText(z) : `aproximativ ${luniText(Math.round(z / 30))}`;

// timeZone UTC e obligatoriu, nu cosmetic: captured_on e o data fara ora, iar
// new Date('2026-03-12') se interpreteaza ca miezul noptii UTC. Formatata intr-un fus la
// vest de UTC ar da "11 martie". Romania e la est, deci ar merge local si s-ar strica tacut
// pentru oricine altcineva.
const _dateFmt = new Intl.DateTimeFormat('ro-RO', {
  day: 'numeric', month: 'long', year: 'numeric', timeZone: 'UTC',
});
const dataLunga = (iso) => (iso ? _dateFmt.format(new Date(`${iso}T00:00:00Z`)) : '');
const zileIntre = (a, b) =>
  Math.round(Math.abs(new Date(`${b}T00:00:00Z`) - new Date(`${a}T00:00:00Z`)) / 86400000);

const schimbariText = (n) =>
  n === 0 ? 'nicio schimbare cunoscută'
  : n === 1 ? 'o schimbare cunoscută'
  : `${n} ${de(n)}schimbări cunoscute`;
const metriPatratiText = (n) =>
  n === 1 ? 'un metru pătrat' : `${n} ${de(n)}metri pătrați`;

// In tiparul "în zona ___ a sitului", forma corecta e "de nord-vest" dar "centrală".
const ZONE_ARTICLE = {
  'nord-vest': 'de nord-vest', nord: 'de nord', 'nord-est': 'de nord-est',
  vest: 'de vest', centru: 'centrală', est: 'de est',
  'sud-vest': 'de sud-vest', sud: 'de sud', 'sud-est': 'de sud-est',
};
const zoneWithArticle = (z) => ZONE_ARTICLE[z] || `de ${z}`;

// Backendul da [vest, sud, est, nord]; geo.js vrea un obiect.
// Suprapunere pe cutii de incadrare: peticurile sunt dreptunghiuri aliniate, deci un test
// exact pe poligoane n-ar schimba raspunsul si ar aduce o dependenta.
const matchKnown = (feature, boxes) => {
  if (!boxes) return null;
  const ring = feature?.geometry?.coordinates?.[0] || [];
  if (!ring.length) return null;
  const lons = ring.map((q) => q[0]);
  const lats = ring.map((q) => q[1]);
  const a = { minLon: Math.min(...lons), maxLon: Math.max(...lons), minLat: Math.min(...lats), maxLat: Math.max(...lats) };
  return (
    boxes.find(
      (b) => a.minLon < b.maxLon && a.maxLon > b.minLon && a.minLat < b.maxLat && a.maxLat > b.minLat
    ) || null
  );
};

const rasterBoundsToBox = (b) =>
  Array.isArray(b) && b.length === 4
    ? { minLon: b[0], minLat: b[1], maxLon: b[2], maxLat: b[3] }
    : null;

const ISSUE_LABELS = {
  blurry: 'Neclare',
  no_gps: 'Fără date GPS',
  low_overlap: 'Suprapunere insuficientă',
  unreadable: 'Ilizibile',
};

export default function App() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const pollRef = useRef(null);
  const popupRef = useRef(null);
  const reportHeadingRef = useRef(null);

  // Existing states
  const [opacity, setOpacity] = useState(0.5);
  const [status, setStatus] = useState('Inițializare...');
  const [isProcessing, setIsProcessing] = useState(false);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);

  // Ingest panel states
  const [flightId, setFlightId] = useState('test');
  // Zborul afisat pe harta e separat de cel folosit la ingestie: poti valida poze pentru un
  // zbor nou in timp ce te uiti la rezultatele altuia.
  const [flights, setFlights] = useState([]);
  const [viewedFlight, setViewedFlight] = useState('test');
  const [isSwitching, setIsSwitching] = useState(false);
  const [isSheetOpen, setIsSheetOpen] = useState(false);
  // Intinderea reala a rasterului zborului afisat. Ancoreaza si grila de zone: pe bbox-ul
  // anomaliilor, "nord-vest" ar insemna alt loc la fiecare zbor.
  const [rasterBounds, setRasterBounds] = useState(null);
  // Adevarul de referinta exista doar pentru perechea sintetica: stim ce s-a schimbat
  // fiindca noi am injectat schimbarile. Pe un zbor real e null, si asta se SPUNE, nu se
  // ascunde — tacerea ar face datele absente sa semene cu un scor de zero.
  const [truth, setTruth] = useState(null);
  const [showKnown, setShowKnown] = useState(false);
  const [showCandidates, setShowCandidates] = useState(true);
  const sheetRef = useRef(null);
  const sheetHeadingRef = useRef(null);
  const openSheetBtnRef = useRef(null);
  const detailRef = useRef(null);
  // Efectul hartii ruleaza o singura data, inainte ca selectAnomaly sa existe in closure.
  const selectAnomalyRef = useRef(null);
  const viewedFlightRef = useRef('test');
  // Numele canvasului se rescrie din applyGeoJsonResult si din comutator; ambele au nevoie
  // de starea curenta fara sa depinda de closure.
  const showKnownRef = useRef(false);
  const truthCountRef = useRef(0);
  const anomaliesRef = useRef(0);
  const [selectedFiles, setSelectedFiles] = useState([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isValidating, setIsValidating] = useState(false);
  const [isUploaded, setIsUploaded] = useState(false);
  const [report, setReport] = useState(null);
  const [apiError, setApiError] = useState(null);
  const [lastFailedAction, setLastFailedAction] = useState(null); // 'upload' | 'validate' | null

  // Live regions states
  const [statusMessage, setStatusMessage] = useState('');
  const [statusSeq, setStatusSeq] = useState(0);
  const [errorMessage, setErrorMessage] = useState('');
  const [errorSeq, setErrorSeq] = useState(0);
  const uploadBtnRef = useRef(null);
  const validateBtnRef = useRef(null);

  // FastAPI intoarce `detail` ca sir la 400/404, dar ca lista de obiecte la 422 — fara
  // normalizare, sablonul de mai jos produce "[object Object]" in live region.
  const describeApiError = (status, detail) => {
    let text;
    if (Array.isArray(detail)) {
      text = detail.map((d) => d?.msg || JSON.stringify(d)).join('; ');
    } else if (detail && typeof detail === 'object') {
      text = detail.msg || JSON.stringify(detail);
    } else {
      text = detail || `status ${status}`;
    }
    // Sfatul de recuperare trebuie sa arate spre ce chiar repara problema.
    let advice;
    if (status === 404) advice = 'Verificați câmpul ID Zbor și încercați din nou.';
    else if (status === 422 || status === 400) advice = 'Verificați fișierele selectate și încercați din nou.';
    else advice = 'Încercați din nou peste câteva momente.';
    return `${text}. ${advice}`;
  };

  const announceStatus = (msg) => {
    setStatusMessage(msg);
    setStatusSeq((prev) => prev + 1);
  };

  const announceError = (msg) => {
    setErrorMessage(msg);
    setErrorSeq((prev) => prev + 1);
  };

  // Un drop ratat in afara zonei ar face browserul sa navigheze catre fisier, pierzand tot
  // ce era in panou. Blocam comportamentul implicit la nivel de fereastra.
  useEffect(() => {
    const block = (e) => e.preventDefault();
    window.addEventListener('dragover', block);
    window.addEventListener('drop', block);
    return () => {
      window.removeEventListener('dragover', block);
      window.removeEventListener('drop', block);
    };
  }, []);

  const loadTruth = async (fid, known) => {
    // Daca lista de zboruri spune deja ca nu exista adevar de referinta, nu se mai cere:
    // 404-ul ar fi corect, dar apare ca eroare in consola browserului degeaba.
    if (known === false) {
      setTruth(null);
      mapRef.current?.getSource('truth-source')?.setData({ type: 'FeatureCollection', features: [] });
      return null;
    }
    try {
      const res = await fetch(`${API_BASE}/flights/${encodeURIComponent(fid)}/truth`);
      if (res.ok) {
        const doc = await res.json();
        setTruth(doc);
        mapRef.current?.getSource('truth-source')?.setData(doc);
        return doc;
      }
      // 404 e o stare asteptata, nu un esec: un zbor real n-are adevar de referinta.
      // Rutarea lui catre role="alert" ar striga lupul.
      setTruth(null);
      mapRef.current?.getSource('truth-source')?.setData({ type: 'FeatureCollection', features: [] });
    } catch {
      setTruth(null);
    }
    return null;
  };

  const recallSentence = (doc, features) => {
    const zones = doc?.features || [];
    if (!zones.length) return '';
    const boxes = zones.map((f) => {
      const ring = f.geometry?.coordinates?.[0] || [];
      const lons = ring.map((q) => q[0]);
      const lats = ring.map((q) => q[1]);
      return { minLon: Math.min(...lons), maxLon: Math.max(...lons), minLat: Math.min(...lats), maxLat: Math.max(...lats) };
    });
    let found = 0;
    let deepest = 0;
    boxes.forEach((b) => {
      const idx = (features || []).findIndex((f) => {
        const ring = f.geometry?.coordinates?.[0] || [];
        if (!ring.length) return false;
        const lons = ring.map((q) => q[0]);
        const lats = ring.map((q) => q[1]);
        return Math.min(...lons) < b.maxLon && Math.max(...lons) > b.minLon
          && Math.min(...lats) < b.maxLat && Math.max(...lats) > b.minLat;
      });
      if (idx >= 0) { found += 1; deepest = Math.max(deepest, idx + 1); }
    });
    if (found === 0) return 'Nicio schimbare cunoscută de referință nu a fost găsită.';
    // Recall singur e trivial de pacalit: un detector care coloreaza tot situl scoate 4 din 4.
    // Rangul celei mai adanci schimbari gasite costa nimic si face cifra onesta.
    return `${found} din ${zones.length} schimbări cunoscute de referință au fost găsite`
      + (found === zones.length ? `, toate în primele ${deepest} anomalii după scor.` : '.');
  };

  const loadFlightList = async () => {
    try {
      const res = await fetch(`${API_BASE}/flights`);
      if (res.ok) {
        const list = (await res.json()).flights || [];
        setFlights(list);
        const cur = list.find((f) => f.id === viewedFlightRef.current);
        if (cur?.bounds) setRasterBounds(cur.bounds);
      }
    } catch {
      // Lista e o comoditate: daca nu vine, harta ramane pe zborul curent.
    }
  };

  useEffect(() => {
    loadFlightList();
  }, []);

  // Focus report heading after report is rendered
  useEffect(() => {
    if (report && reportHeadingRef.current) {
      reportHeadingRef.current.focus();
    }
  }, [report]);

  // Initialize MapLibre GL Map
  useEffect(() => {
    if (mapRef.current) return;

    const map = new maplibregl.Map({
      container: mapContainer.current,
      style: {
        version: 8,
        sources: {},
        layers: [
          {
            id: 'background',
            type: 'background',
            paint: { 'background-color': '#090d16' },
          },
        ],
      },
      center: DEFAULT_CENTER,
      zoom: DEFAULT_ZOOM,
      maxZoom: 20,
      minZoom: 10,
      // MapLibre isi eticheteaza singur canvasul si controalele, in engleza. Pagina e
      // lang="ro", deci o voce romaneasca le-ar pronunta neinteligibil.
      locale: {
        'Map.Title': 'Hartă ortofotoplan cu anomalii detectate',
        'NavigationControl.ZoomIn': 'Mărește harta',
        'NavigationControl.ZoomOut': 'Micșorează harta',
        'NavigationControl.ResetBearing': 'Resetează orientarea hărții spre nord',
        'AttributionControl.ToggleAttribution': 'Afișează atribuirile hărții',
        'Popup.Close': 'Închide fereastra de detalii',
      },
    });

    // 'top-left' le aseza sub .top-header si sub .ingest-panel — vizibil ramanea un fir de
    // cativa pixeli. Jos-stanga e singura zona pe care niciun panou n-o acopera.
    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'bottom-left');

    map.on('load', () => {
      // 1. Before Raster Layer
      // Fara `bounds` fix: erau limitele demo-ului si ar fi taiat tile-urile oricarui zbor
      // urcat in alta parte. In afara rasterului backendul intoarce un PNG gol de ~2KB,
      // cache-uit 24h, deci costul e neglijabil fata de a afisa gresit.
      map.addSource('before-source', {
        type: 'raster',
        tiles: [`${API_BASE}/tiles/before/{z}/{x}/{y}.png`],
        tileSize: 256,
      });

      map.addLayer({
        id: 'before-layer',
        type: 'raster',
        source: 'before-source',
        paint: {
          'raster-opacity': 1.0,
          'raster-fade-duration': 0,
        },
      });

      // 2. After Raster Layer (Opacity modulated by slider)
      map.addSource('after-source', {
        type: 'raster',
        tiles: [`${API_BASE}/tiles/after/{z}/{x}/{y}.png`],
        tileSize: 256,
      });

      map.addLayer({
        id: 'after-layer',
        type: 'raster',
        source: 'after-source',
        paint: {
          'raster-opacity': opacity,
          'raster-fade-duration': 0,
        },
      });

      // 3. Anomalies GeoJSON Layer
      map.addSource('anomalies-source', {
        type: 'geojson',
        data: {
          type: 'FeatureCollection',
          features: [],
        },
      });

      map.addLayer({
        id: 'anomalies-fill',
        type: 'fill',
        source: 'anomalies-source',
        paint: {
          'fill-color': '#ef4444',
          'fill-opacity': 0.35,
        },
      });

      // Conturul statea direct pe fotografie, unde niciun ton nu poate garanta 3:1 fata de
      // un fundal necunoscut. Un casing inchis dedesubt face ca vecinul liniei sa fie
      // casingul, nu ortofotoplanul: #f87171 pe #0B1220 da 6.86:1.
      map.addLayer({
        id: 'anomalies-casing',
        type: 'line',
        source: 'anomalies-source',
        paint: { 'line-color': '#0B1220', 'line-width': 5, 'line-opacity': 0.9 },
      });

      map.addLayer({
        id: 'anomalies-line',
        type: 'line',
        source: 'anomalies-source',
        paint: {
          'line-color': '#f87171',
          'line-width': 2.5,
        },
      });

      // 4. Schimbarile cunoscute de referinta, desenate PESTE candidati ca sa nu fie
      // ingropate sub cincizeci de dreptunghiuri. Fara umplere: umplerea rosie a
      // candidatilor ramane vizibila prin contur, deci suprapunerea se vede ca suprapunere.
      map.addSource('truth-source', {
        type: 'geojson',
        data: { type: 'FeatureCollection', features: [] },
      });

      map.addLayer({
        id: 'truth-casing',
        type: 'line',
        source: 'truth-source',
        layout: { visibility: 'none' },
        paint: { 'line-color': '#0B1220', 'line-width': 7, 'line-opacity': 0.9 },
      });

      map.addLayer({
        id: 'truth-line',
        type: 'line',
        source: 'truth-source',
        layout: { visibility: 'none' },
        paint: {
          'line-color': '#FDE047',
          'line-width': 3,
          // Linia intrerupta e purtatoare de sens, nu decor: #FDE047 fata de #f87171 da
          // 2.10:1, sub prag, deci culoarea singura nu distinge cele doua straturi.
          'line-dasharray': [2, 1.5],
        },
      });

      // Hover / Click Popup on Anomalies
      map.on('click', 'anomalies-fill', (e) => {
        if (!e.features || !e.features.length) return;
        const feature = e.features[0];
        const props = feature.properties || {};
        // O singura instanta, refolosita: altfel fiecare clic lasa in urma inca un buton de
        // inchidere focusabil, la o pozitie imprevizibila in ordinea de tabulare.
        if (!popupRef.current) popupRef.current = new maplibregl.Popup({ closeOnClick: true });
        popupRef.current
          .setLngLat(e.lngLat)
          .setHTML(
            `<strong>Anomalie #${props.rank || ''}</strong><br/>` +
            `Scor: ${fmt4(props.anomaly_score)}<br/>` +
            `Patch: ${props.patch_index || ''}`
          )
          .addTo(map);
        // Aceeasi selectie ca butonul din tabel: mouse-ul si tastatura converg pe o stare.
        // Conteaza pentru cine foloseste lupa plus voce — altfel popup-ul se deschide mut.
        selectAnomalyRef.current?.(feature, (props.rank || 1) - 1);
      });

      map.on('mouseenter', 'anomalies-fill', () => {
        map.getCanvas().style.cursor = 'pointer';
      });
      map.on('mouseleave', 'anomalies-fill', () => {
        map.getCanvas().style.cursor = '';
      });

      mapRef.current = map;
      // Start fetching detection data
      checkAndFetchDetection();
    });

    return () => {
      // Fara asta, un zbor care nu se termina niciodata lasa intervalul sa ruleze dupa
      // demontare si sa scrie in continuare intr-o live region.
      if (pollRef.current) clearInterval(pollRef.current);
      map.remove();
    };
  }, []);

  // Handle live slider opacity change — purely modifies WebGL raster-opacity without network calls
  const handleSliderChange = (e) => {
    const val = parseFloat(e.target.value);
    setOpacity(val);
    if (mapRef.current && mapRef.current.getLayer('after-layer')) {
      mapRef.current.setPaintProperty('after-layer', 'raster-opacity', val);
    }
  };

  // URL-ul de tile difera intre demo (rasterele de referinta) si un zbor urcat, care isi are
  // propriile COG-uri sub data/flights/<id>/.
  const tileUrl = (fid, layer) =>
    fid === 'test'
      ? `${API_BASE}/tiles/${layer}/{z}/{x}/{y}.png`
      : `${API_BASE}/tiles/flights/${encodeURIComponent(fid)}/${layer}/{z}/{x}/{y}.png`;

  const switchViewedFlight = async (fid) => {
    if (!fid || fid === viewedFlight || isSwitching) return;
    setIsSwitching(true);
    setViewedFlight(fid);
    setAnomalies([]);
    setSelectedAnomaly(null);
    // Fara asta, poligoanele galbene ale demo-ului raman peste imaginile altui zbor si
    // afirma ceva fals despre el.
    setTruth(null);
    setShowKnown(false);
    if (mapRef.current) {
      mapRef.current.getSource('truth-source')?.setData({ type: 'FeatureCollection', features: [] });
      for (const id of ['truth-casing', 'truth-line']) {
        if (mapRef.current.getLayer(id)) mapRef.current.setLayoutProperty(id, 'visibility', 'none');
      }
    }
    announceStatus(`Se încarcă situl ${fid}.`);

    const b = flights.find((f) => f.id === fid)?.bounds || null;
    setRasterBounds(b);

    const map = mapRef.current;
    if (map) {
      for (const layer of ['before', 'after']) {
        const src = map.getSource(`${layer}-source`);
        if (src && src.setTiles) src.setTiles([tileUrl(fid, layer)]);
      }
    }

    try {
      const res = await fetch(`${API_BASE}/flights/${encodeURIComponent(fid)}/result`);
      if (res.ok) {
        const data = await res.json();
        if (data.result) {
          applyGeoJsonResult(data.result, true);
          const n = data.result.features?.length || 0;
          setStatus(`Sit ${fid}: detecție finalizată`);
          const doc = await loadTruth(fid, flights.find((f) => f.id === fid)?.has_truth);
          const rec = recallSentence(doc, data.result.features);
          announceStatus(
            `Situl ${fid} a fost încărcat. ${anomaliiText(n)} detectate. ` +
              (rec || 'Acest zbor nu are schimbări cunoscute de referință, deci acoperirea nu poate fi calculată.')
          );
        } else {
          setStatus(`Sit ${fid}: fără rezultat`);
          announceStatus(`Situl ${fid} a fost încărcat, dar nu are încă un rezultat de detecție.`);
        }
      } else {
        setStatus(`Sit ${fid}: fără rezultat`);
        announceStatus(`Situl ${fid} nu are un rezultat de detecție.`);
      }
    } catch {
      announceError('Eroare de rețea la încărcarea zborului. Încercați din nou.');
    } finally {
      setIsSwitching(false);
    }
  };

  // Descarcarea rezultatului: un topograf vrea GeoJSON-ul in QGIS, nu intr-un panou.
  const downloadResult = async () => {
    if (anomalies.length === 0) return;
    try {
      const res = await fetch(`${API_BASE}/flights/${encodeURIComponent(viewedFlight)}/result`);
      if (!res.ok) {
        announceError('Rezultatul nu a putut fi descărcat. Încercați din nou.');
        return;
      }
      const data = await res.json();
      const blob = new Blob([JSON.stringify(data.result, null, 2)], { type: 'application/geo+json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `argus-${viewedFlight}-anomalii.geojson`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      announceStatus(`Fișierul argus-${viewedFlight}-anomalii.geojson a fost descărcat.`);
    } catch {
      announceError('Eroare de rețea la descărcare. Încercați din nou.');
    }
  };

  useEffect(() => {
    selectAnomalyRef.current = selectAnomaly;
    viewedFlightRef.current = viewedFlight;
    showKnownRef.current = showKnown;
    truthCountRef.current = truth?.features?.length || 0;
    anomaliesRef.current = anomalies.length;
  });

  const toggleKnownChanges = (on) => {
    setShowKnown(on);
    const map = mapRef.current;
    if (map) {
      for (const id of ['truth-casing', 'truth-line']) {
        // setLayoutProperty, nu adaugare/stergere: stergerea ar reintroduce de fiecare data
        // problema de ordine a straturilor.
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
      }
    }
    const n = truth?.features?.length || 0;
    applyCanvasLabel({ showKnown: on, truthCount: n });
    announceStatus(
      on
        ? `Cele ${schimbariText(n)} sunt acum afișate pe hartă, cu contur galben întrerupt. Lista lor se află în secțiunea Schimbări cunoscute.`
        : 'Schimbările cunoscute nu mai sunt afișate pe hartă.'
    );
  };

  const toggleCandidates = (on) => {
    setShowCandidates(on);
    const map = mapRef.current;
    if (map) {
      for (const id of ['anomalies-fill', 'anomalies-casing', 'anomalies-line']) {
        if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none');
      }
    }
    announceStatus(
      on
        ? `${anomaliiText(anomalies.length)} candidate sunt din nou afișate pe hartă.`
        : 'Anomaliile candidate au fost ascunse. Harta arată acum doar ortofotoplanul.'
    );
  };

  const openSheet = () => {
    const d = sheetRef.current;
    if (!d || d.open) return;
    d.showModal();
    setIsSheetOpen(true);
    // <dialog> ar focusa singur primul descendent focusabil, adica butonul de inchidere.
    // Titlul e locul corect: spune unde ai ajuns.
    sheetHeadingRef.current?.focus();
  };

  const closeSheet = () => {
    const d = sheetRef.current;
    if (d?.open) d.close();
  };

  // Escape si clicul pe backdrop inchid dialogul fara sa treaca prin handler-ul nostru.
  // Fara sincronizarea asta, starea React ramane "deschis" iar DOM-ul e inchis.
  useEffect(() => {
    const d = sheetRef.current;
    if (!d) return;
    const onClose = () => {
      setIsSheetOpen(false);
      openSheetBtnRef.current?.focus();
    };
    d.addEventListener('close', onClose);
    return () => d.removeEventListener('close', onClose);
  }, []);

  // Stratul de limbaj: geo.js intoarce cifre, aici devin propozitii. Rotunjirile sunt
  // deliberate — intre eroarea GPS si aproximarea centroidului, "la 127,4 m" ar pretinde
  // o precizie pe care n-o avem si ar face utilizatorul sa nu creada tot panoul.
  const anomalyModel = useMemo(
    () => (anomalies.length ? summarise(anomalies, rasterBoundsToBox(rasterBounds)) : null),
    [anomalies, rasterBounds]
  );

  // Cutia de incadrare a fiecarei zone cunoscute, pentru testul de suprapunere.
  const truthBoxes = useMemo(() => {
    if (!truth?.features?.length) return null;
    return truth.features.map((f, i) => {
      const ring = f.geometry?.coordinates?.[0] || [];
      const lons = ring.map((q) => q[0]);
      const lats = ring.map((q) => q[1]);
      return {
        zone: f.properties?.zone ?? i + 1,
        label: f.properties?.label || f.properties?.description || `zona ${i + 1}`,
        minLon: Math.min(...lons), maxLon: Math.max(...lons),
        minLat: Math.min(...lats), maxLat: Math.max(...lats),
      };
    });
  }, [truth]);

  const anomalyRows = useMemo(() => {
    if (!anomalyModel) return [];
    return anomalyModel.items.map((it, i) => {
      const dist = it.distanceM < 20 ? null : Math.round(it.distanceM / 10) * 10;
      return {
        ...it,
        index: i,
        feature: anomalies[i],
        positionText:
          dist === null
            ? `În zona ${zoneWithArticle(it.zone)} a sitului, la mai puțin de 20 de metri de centru`
            : `În zona ${zoneWithArticle(it.zone)} a sitului, la aproximativ ${metriText(dist)} de centru`,
        groupText: it.clusterId ? `Grupul ${it.clusterId}` : 'Izolată',
        known: matchKnown(anomalies[i], truthBoxes),
        coordsSpoken:
          `${Math.abs(it.lat).toFixed(6).replace('.', ',')} grade ${it.lat >= 0 ? 'nord' : 'sud'}, ` +
          `${Math.abs(it.lon).toFixed(6).replace('.', ',')} grade ${it.lon >= 0 ? 'est' : 'vest'}`,
      };
    });
  }, [anomalyModel, anomalies, truthBoxes]);

  const summaryText = useMemo(() => {
    const m = anomalyModel;
    if (!m) return '';
    const parts = [
      `${anomaliiText(m.count)} detectate pe o suprafață de aproximativ ` +
        `${Math.round(m.widthM)} pe ${metriText(Math.round(m.heightM))}.`,
      `Scorurile merg de la ${fmt2(m.minScore)} la ${fmt2(m.maxScore)}.`,
    ];
    if (m.uniformArea) {
      parts.push(`Fiecare anomalie acoperă aproximativ ${metriPatratiText(Math.round(m.typicalAreaM2))}.`);
    }
    const zones = m.zonesRanked
      .slice(0, 3)
      .map(([z, n]) => `${n} în zona ${zoneWithArticle(z)}`)
      .join(', ');
    if (zones) parts.push(`Distribuție: ${zones}.`);
    if (m.clusters.length) {
      const g = m.clusters
        .map((c) => `${anomaliiText(c.members.length)} în zona ${zoneWithArticle(c.zone)}`)
        .join(', ');
      parts.push(
        `Grupări: ${m.clusters.length === 1 ? 'un grup' : `${m.clusters.length} grupuri`} de anomalii apropiate — ${g}.` +
          (m.isolated ? ` Restul de ${m.isolated} sunt izolate.` : '')
      );
    }
    return parts.join(' ');
  }, [anomalyModel]);

  // Totul despre adevarul de referinta, intr-un singur loc: randurile tabelului, propozitia
  // de acoperire si enumerarea in proza. null cand zborul nu e o pereche sintetica.
  const truthInfo = useMemo(() => {
    if (!truthBoxes?.length || !anomalyRows.length) return null;
    const rows = truthBoxes.map((b) => {
      const hit = anomalyRows.find((r) => r.known && r.known.zone === b.zone) || null;
      const lon = (b.minLon + b.maxLon) / 2;
      const lat = (b.minLat + b.maxLat) / 2;
      const zona = anomalyModel ? zoneName(lon, lat, anomalyModel.bbox) : null;
      return {
        ...b,
        hit,
        positionText: zona ? `În zona ${zoneWithArticle(zona)} a sitului` : 'Poziție necunoscută',
      };
    });
    const found = rows.filter((r) => r.hit).length;
    const deepest = rows.reduce((m, r) => (r.hit ? Math.max(m, r.hit.rank) : m), 0);
    const recall =
      found === 0
        ? 'Nicio schimbare cunoscută de referință nu a fost găsită.'
        : `${found} din ${rows.length} schimbări cunoscute de referință au fost găsite` +
          (found === rows.length ? `, toate în primele ${deepest} anomalii după scor.` : '.');
    return {
      rows,
      count: rows.length,
      recall,
      labels: rows.map((r) => r.label.toLowerCase()).join(', '),
    };
  }, [truthBoxes, anomalyRows, anomalyModel]);

  const selectedDetail = useMemo(
    () => anomalyRows.find((r) => r.rank === selectedAnomaly) || null,
    [anomalyRows, selectedAnomaly]
  );

  const detailText = useMemo(() => {
    const d = selectedDetail;
    if (!d) return '';
    const grup = d.clusterId
      ? ` Face parte din grupul ${d.clusterId}.`
      : ' Nu face parte dintr-un grup de anomalii apropiate.';
    return (
      `Scor de anomalie ${fmt2(d.score)} din 1. ${d.positionText}. ` +
      `Suprafață aproximativ ${metriPatratiText(Math.round(d.areaM2))}.${grup} ` +
      (truthBoxes
        ? d.known
          ? ` Se suprapune cu schimbarea cunoscută ${d.known.zone}: ${d.known.label}.`
          : ' Nu se suprapune cu nicio schimbare cunoscută.'
        : '') +
      ` Coordonate: ${d.coordsSpoken}.`
    );
  }, [selectedDetail, truthBoxes]);

  // Poll backend for anomaly detection result
  const checkAndFetchDetection = async () => {
    try {
      setStatus('Verificare rezultat...');
      const res = await fetch(`${API_BASE}/flights/test/result`);

      if (res.status === 200) {
        const data = await res.json();
        if (data.status === 'done' && data.result) {
          applyGeoJsonResult(data.result);
          setStatus('Detecție finalizată');
          {
            const doc = await loadTruth('test');
            const rec = recallSentence(doc, data.result.features);
            announceStatus(
              `Detecție finalizată. ${anomaliiText(data.result.features?.length || 0)} detectate. ` +
                (rec ? rec + ' ' : '') +
                'Detaliile sunt în secțiunea Anomalii detectate.'
            );
          }
          return;
        }
      }

      // If not finished, trigger process and poll
      setIsProcessing(true);
      setStatus('Pornire detecție asincronă...');
      await fetch(`${API_BASE}/flights/test/process`, { method: 'POST' });

      const pollInterval = setInterval(async () => {
        try {
          const statusRes = await fetch(`${API_BASE}/flights/test/status`);
          if (statusRes.ok) {
            const statusData = await statusRes.json();
            setStatus(`Stare: ${STATUS_LABELS[statusData.status] || statusData.status}`);

            if (statusData.status === 'done') {
              clearInterval(pollInterval);
              setIsProcessing(false);
              const resultRes = await fetch(`${API_BASE}/flights/test/result`);
              const resultData = await resultRes.json();
              if (resultData.result) {
                applyGeoJsonResult(resultData.result);
                setStatus('Detecție finalizată');
                {
                  const doc = await loadTruth('test');
                  const rec = recallSentence(doc, resultData.result.features);
                  announceStatus(
                    `Detecție finalizată. ${anomaliiText(resultData.result.features?.length || 0)} detectate. ` +
                      (rec ? rec + ' ' : '') +
                      'Detaliile sunt în secțiunea Anomalii detectate.'
                  );
                }
              }
            } else if (statusData.status === 'failed') {
              clearInterval(pollInterval);
              setIsProcessing(false);
              setStatus(`Eșuat: ${statusData.error_message || ''}`);
            }
          }
        } catch (err) {
          console.error('Polling error:', err);
        }
      }, 1000);
      pollRef.current = pollInterval;
    } catch (err) {
      console.error('Fetch detection error:', err);
      setStatus('Eroare conexiune backend');
    }
  };

  // Eticheta canvasului se scrie acum din patru locuri. Construita dintr-o singura functie,
  // nu peticita cu regex: varianta veche cauta /\d+[^.]*contur galben/ si, de indata ce
  // intra date in text, ar fi prins "14" din "14 martie 2026" in loc de numarul de anomalii,
  // stergand tacut fragmentul gresit.
  const buildCanvasLabel = ({ anomalyCount, showKnown, truthCount }) => {
    const parts = ['Hartă ortofotoplan, comparație între zborul inițial și zborul curent.'];
    parts.push(`${anomaliiText(anomalyCount)} marcate cu poligoane pe hartă.`);
    if (showKnown && truthCount) {
      parts.push(`${schimbariText(truthCount)} de referință marcate suplimentar cu contur galben întrerupt.`);
    }
    parts.push('Echivalentul în text se află în secțiunea Anomalii detectate.');
    return parts.join(' ');
  };

  const applyCanvasLabel = (overrides = {}) => {
    const canvas = mapRef.current?.getCanvas?.();
    if (!canvas) return;
    canvas.setAttribute(
      'aria-label',
      buildCanvasLabel({
        anomalyCount: anomaliesRef.current,
        showKnown: showKnownRef.current,
        truthCount: truthCountRef.current,
        ...overrides,
      })
    );
  };

  const featureCentroid = (feature) => {
    const ring = feature?.geometry?.coordinates?.[0];
    if (!Array.isArray(ring) || ring.length < 4) return null;
    const pts = ring.slice(0, -1);
    return [
      pts.reduce((a, q) => a + q[0], 0) / pts.length,
      pts.reduce((a, q) => a + q[1], 0) / pts.length,
    ];
  };

  const applyGeoJsonResult = (geojson, recenter = false) => {
    if (mapRef.current && mapRef.current.getSource('anomalies-source')) {
      mapRef.current.getSource('anomalies-source').setData(geojson);
    }
    if (geojson && geojson.features) {
      setAnomalies(geojson.features);
      const n = geojson.features.length;
      applyCanvasLabel({ anomalyCount: n });
    }
  };

  // Selectia nu muta niciodata focusul: marcheaza randul, randeaza detaliul in panoul
  // lateral, misca camera si anunta scurt. Aceeasi functie pentru randul din tabel si
  // pentru clicul pe canvas, ca mouse-ul si tastatura sa nu divergheze.
  const selectAnomaly = (feature, index) => {
    const rank = feature.properties?.rank ?? index + 1;
    setSelectedAnomaly(rank);
    announceStatus(`Anomalia ${rank} selectată.`);
    if (!mapRef.current || !feature.geometry) return;
    const c = featureCentroid(feature);
    if (c) {
      // Fara essential:true — MapLibre suprima singur animatia camerei sub
      // prefers-reduced-motion, si asa vrem. Nu adauga essential aici.
      mapRef.current.flyTo({ center: c, zoom: 18.5, speed: 1.2 });
    }
  };

  // Files selection handler (shared by input onChange and drag & drop)
  const handleFilesSelected = (filesList) => {
    // Garda: fara asta, o selectie noua in timpul unei cereri in zbor lasa isUploaded si
    // numarul anuntat desincronizate fata de ce s-a trimis efectiv (closure vechi).
    if (isUploading || isValidating) return;

    const all = Array.from(filesList);
    if (all.length === 0) return;

    // Calea de drag-and-drop nu trece prin filtrul `accept` al pickerului, deci filtram aici,
    // altfel un .zip ajunge in lista si e anuntat ca "fotografie".
    const isJpeg = (f) => /^image\/jpe?g$/i.test(f.type) || /\.jpe?g$/i.test(f.name);
    const files = all.filter(isJpeg);
    const rejected = all.length - files.length;

    if (files.length === 0) {
      const msg = `Niciun fișier acceptat. ${rejected} ${rejected === 1 ? 'fișier nu este' : 'fișiere nu sunt'} în format JPEG.`;
      setApiError(msg);
      setLastFailedAction(null);
      announceError(msg);
      return;
    }

    setSelectedFiles(files);
    setIsUploaded(false);
    setReport(null);
    setApiError(null);
    setErrorMessage('');
    setLastFailedAction(null);
    announceStatus(
      rejected > 0
        ? `${files.length} fotografii selectate. ${rejected} ${rejected === 1 ? 'fișier ignorat, nu este' : 'fișiere ignorate, nu sunt'} în format JPEG.`
        : `${files.length} fotografii selectate.`
    );
  };

  const handleFileInputChange = (e) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesSelected(e.target.files);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    // dragleave urca si de la copiii zonei, deci fara verificarea asta starea palpaie
    // de fiecare data cand cursorul trece peste text sau peste eticheta.
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesSelected(e.dataTransfer.files);
    }
  };

  // Upload photos to API
  const handleUpload = async () => {
    if (isUploading || isValidating || selectedFiles.length === 0) return;

    setIsUploading(true);
    setApiError(null);
    setErrorMessage('');
    setLastFailedAction(null);
    announceStatus(`Se încarcă ${selectedFiles.length} fotografii.`);

    try {
      const formData = new FormData();
      for (const file of selectedFiles) {
        formData.append('files', file);
      }

      const res = await fetch(`${API_BASE}/flights/${encodeURIComponent(flightId)}/photos`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        let detail = null;
        try {
          const errData = await res.json();
          detail = errData.detail ?? res.statusText;
        } catch {
          detail = res.statusText;
        }
        const errorMsg = `Eroare la încărcare: ${describeApiError(res.status, detail)}`;
        setApiError(errorMsg);
        setLastFailedAction('upload');
        announceError(errorMsg);
        setIsUploading(false);
        return;
      }

      setIsUploaded(true);
      setIsUploading(false);
      announceStatus(
        `Încărcare finalizată. ${selectedFiles.length} fotografii încărcate. Butonul Validează este acum disponibil.`
      );
    } catch (err) {
      console.error('Upload error:', err);
      const errorMsg = 'Eroare de rețea. Verificați conexiunea și încercați din nou.';
      setApiError(errorMsg);
      setLastFailedAction('upload');
      announceError(errorMsg);
      setIsUploading(false);
    }
  };

  // Validate photos with API
  const handleValidate = async () => {
    if (isUploading || isValidating || !isUploaded) return;

    setIsValidating(true);
    setApiError(null);
    setErrorMessage('');
    setLastFailedAction(null);
    announceStatus(
      `Se validează ${selectedFiles.length} fotografii. Operațiunea poate dura câteva secunde.`
    );

    try {
      const res = await fetch(`${API_BASE}/flights/${encodeURIComponent(flightId)}/validate`, {
        method: 'POST',
      });

      if (!res.ok) {
        let detail = 'Eroare necunoscută';
        try {
          const errData = await res.json();
          detail = errData.detail || res.statusText || `status ${res.status}`;
        } catch {
          detail = res.statusText || `status ${res.status}`;
        }
        const errorMsg = `Eroare la validare: ${detail}. Verificați conexiunea și încercați din nou.`;
        setApiError(errorMsg);
        setLastFailedAction('validate');
        announceError(errorMsg);
        setIsValidating(false);
        return;
      }

      const data = await res.json();
      setReport(data);
      setIsValidating(false);

      // Anuntul ramane scurt intentionat: focusul se muta pe titlul raportului imediat dupa
      // acest render, iar o mutare de focus intrerupe un mesaj politicos lung. Detaliul e
      // atasat titlului prin aria-describedby, deci se citeste odata cu el.
      announceStatus(
        `Validare finalizată. Verdict: ${data.accepted ? 'ACCEPTAT' : 'RESPINS'}.`
      );
    } catch (err) {
      console.error('Validation error:', err);
      const errorMsg = 'Eroare de rețea. Verificați conexiunea și încercați din nou.';
      setApiError(errorMsg);
      setLastFailedAction('validate');
      announceError(errorMsg);
      setIsValidating(false);
    }
  };

  const handleRetry = () => {
    // Focusul se muta INAINTE de a reporni operatiunea: reincarcarea sterge apiError, ceea ce
    // demonteaza bannerul de eroare impreuna cu butonul care are focusul chiar acum. Fara asta,
    // activeElement cade pe <body> si cititorul de ecran isi pierde pozitia in pagina.
    const target = lastFailedAction === 'validate' ? validateBtnRef.current : uploadBtnRef.current;
    if (target) target.focus();

    if (lastFailedAction === 'upload') {
      handleUpload();
    } else if (lastFailedAction === 'validate') {
      handleValidate();
    }
  };

  return (
    <div className="app-container">
      {/* Top Header */}
      <header className="top-header">
        <div className="brand-section">
          <div className="logo-badge">A</div>
          <div className="title-group">
            <h1>Argus Custode</h1>
            <p>Detecție Anomalii Ortofotoplan Dronă</p>
          </div>
        </div>

        <div className="flight-switcher">
          <label htmlFor="view-flight-select" className="switcher-label">
            Sit afișat pe hartă
          </label>
          <select
            id="view-flight-select"
            className="switcher-select"
            value={viewedFlight}
            onChange={(e) => switchViewedFlight(e.target.value)}
            aria-busy={isSwitching}
          >
            {flights.length === 0 && <option value="test">test (demo)</option>}
            {flights.map((f) => (
              <option key={f.id} value={f.id} disabled={!f.has_tiles && !f.has_result}>
                {f.id === 'test' ? 'test (demo)' : f.id}
                {f.has_result ? '' : ' — fără rezultat'}
              </option>
            ))}
          </select>
          <button
            type="button"
            className="btn btn-secondary btn-download"
            onClick={downloadResult}
            aria-disabled={anomalies.length === 0}
          >
            Descarcă GeoJSON
            <span className="sr-only"> pentru zborul {viewedFlight}</span>
          </button>
        </div>

        <div className="header-status">
          {/* Fara role="status" aici: regiunea .sr-only de mai jos e tot o regiune politicoasa
              si poarta text strict mai bogat. Amandoua fiind live, fiecare schimbare de stare
              se anunta de doua ori. Badge-ul ramane stare vizuala. */}
          <div className={`status-badge ${isProcessing ? 'loading' : ''}`}>
            <span className="status-dot" aria-hidden="true"></span>
            <span>{status}</span>
          </div>
        </div>
      </header>

      {/* Main Landmark enclosing panels and map */}
      <main className="main-content">
        {/* Ingest Panel */}
        <section className="ingest-panel" aria-labelledby="ingest-heading">
          <h2 id="ingest-heading">Ingestie fotografii zbor</h2>

          {/* Live regions permanently mounted in DOM, initially empty */}
          <div role="status" aria-atomic="true" className="sr-only">
            {statusMessage ? <span key={statusSeq}>{statusMessage}</span> : null}
          </div>
          <div role="alert" aria-atomic="true" className="sr-only">
            {errorMessage ? <span key={errorSeq}>{errorMessage}</span> : null}
          </div>

          {/* Flight ID Input */}
          <div className="form-group">
            <label htmlFor="flight-id-input" className="form-label">
              ID Zbor
            </label>
            <input
              id="flight-id-input"
              type="text"
              className="text-input"
              value={flightId}
              onChange={(e) => setFlightId(e.target.value)}
              readOnly={isUploading || isValidating}
            />
          </div>

          {/* File Selection & Drop Zone */}
          <div className="form-group">
            <label htmlFor="flight-photos-input" className="form-label">
              Fotografii zbor (JPEG)
            </label>
            <input
              id="flight-photos-input"
              type="file"
              multiple
              accept="image/jpeg,.jpg,.jpeg"
              className="file-input sr-only"
              aria-describedby="drop-zone-instructions"
              onChange={handleFileInputChange}
            />
            <div
              className={`drop-zone ${isDragging ? 'drag-over' : ''}`}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleDrop}
            >
              <p id="drop-zone-instructions" className="drop-zone-text">
                Trageți fotografiile aici sau folosiți butonul de selectare.
              </p>
              <label htmlFor="flight-photos-input" className="file-select-button">
                Selectează fișiere
              </label>
            </div>
          </div>

          {/* Selected Files List */}
          {selectedFiles.length > 0 && (
            <div className="selected-files-block">
              <h3 className="sub-heading">Fișiere selectate ({selectedFiles.length})</h3>
              <ul className="selected-files-list" role="list">
                {selectedFiles.map((file, idx) => (
                  <li key={`${file.name}-${idx}`} className="selected-file-item">
                    <span className="file-name">{file.name}</span>
                    <span className="file-size">({Math.round(file.size / 1024)} KB)</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Actions & Native Progress */}
          <div className="button-group">
            {selectedFiles.length === 0 && (
              <p id="upload-help-text" className="help-text">
                Selectați fotografiile înainte de încărcare.
              </p>
            )}

            <button
              type="button"
              className="btn btn-primary"
              ref={uploadBtnRef}
              aria-disabled={selectedFiles.length === 0 || isUploading || isValidating}
              aria-busy={isUploading}
              aria-describedby={selectedFiles.length === 0 ? 'upload-help-text' : undefined}
              onClick={handleUpload}
            >
              Încarcă fotografiile
            </button>

            <button
              type="button"
              className="btn btn-primary"
              ref={validateBtnRef}
              aria-disabled={!isUploaded || isUploading || isValidating}
              aria-busy={isValidating}
              aria-describedby={!isUploaded ? 'validate-help-text' : undefined}
              onClick={handleValidate}
            >
              Validează
            </button>

            {!isUploaded && (
              <p id="validate-help-text" className="help-text">
                Încărcați fotografiile înainte de validare.
              </p>
            )}
          </div>

          {/* Native Progress Bar outside live regions */}
          {(isUploading || isValidating) && (
            <div className="progress-group">
              <label htmlFor="ingest-progress-bar" className="progress-label">
                {isUploading ? 'Se încarcă fotografiile...' : 'Se validează fotografiile...'}
              </label>
              <progress id="ingest-progress-bar" className="native-progress" />
            </div>
          )}

          {/* Error Banner with Retry */}
          {apiError && (
            <div className="error-banner">
              <p className="error-text" id="api-error-text">{apiError}</p>
              {lastFailedAction && (
                <button
                  type="button"
                  className="btn btn-secondary btn-retry"
                  onClick={handleRetry}
                  aria-describedby="api-error-text"
                >
                  {lastFailedAction === 'validate' ? 'Reîncearcă validarea' : 'Reîncearcă încărcarea'}
                </button>
              )}
            </div>
          )}

          {/* Validation Report */}
          {report && (
            <div className="report-container">
              <div
                className={`report-verdict-header ${
                  report.accepted ? 'verdict-pass-box' : 'verdict-fail-box'
                }`}
              >
                {report.accepted ? (
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    className="verdict-icon verdict-pass-icon"
                    viewBox="0 0 24 24"
                    width="24"
                    height="24"
                  >
                    <circle
                      cx="12"
                      cy="12"
                      r="10"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                    <path
                      d="M7 12.5l3.5 3.5 6.5-6.5"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                ) : (
                  <svg
                    aria-hidden="true"
                    focusable="false"
                    className="verdict-icon verdict-fail-icon"
                    viewBox="0 0 24 24"
                    width="24"
                    height="24"
                  >
                    <path
                      d="M7.86 2h8.28L22 7.86v8.28L16.14 22H7.86L2 16.14V7.86L7.86 2z"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    />
                    <line
                      x1="7"
                      y1="12"
                      x2="17"
                      y2="12"
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeLinecap="round"
                    />
                  </svg>
                )}
                <h3
                  id="report-heading"
                  ref={reportHeadingRef}
                  tabIndex={-1}
                  className="report-heading"
                  aria-describedby="report-verdict-detail"
                >
                  Raport validare — Verdict: {report.accepted ? 'ACCEPTAT' : 'RESPINS'}
                </h3>
                <span id="report-verdict-detail" className="sr-only">
                  {(() => {
                    const sum = report.summary || {};
                    const total = sum.total ?? 0;
                    const bad =
                      (sum.blurry ?? 0) + (sum.no_gps ?? 0) + (sum.low_overlap ?? 0) + (sum.unreadable ?? 0);
                    const detaliu = `Din ${total} fotografii: ${sum.blurry ?? 0} neclare, ${sum.no_gps ?? 0} fără date GPS, ${sum.low_overlap ?? 0} cu suprapunere insuficientă, ${sum.unreadable ?? 0} ilizibile.`;
                    if (report.accepted) {
                      // "nicio problemă" se deduce din cifre — un set poate fi acceptat avand
                      // totusi probleme sub prag, iar afirmatia contrara ar contrazice tabelul.
                      return bad === 0
                        ? `${total} fotografii verificate, nicio problemă.`
                        : `${detaliu} Sub pragul de respingere, deci setul a fost acceptat.`;
                    }
                    const nr = report.reasons?.length || 0;
                    return `${nr} ${nr === 1 ? 'motiv de respingere' : 'motive de respingere'}. ${detaliu}`;
                  })()}
                </span>
              </div>

              {/* Reasons list */}
              {report.reasons && report.reasons.length > 0 && (
                <div className="report-reasons-block">
                  <h4 className="sub-heading">Motive respingere</h4>
                  <ul className="reasons-list">
                    {report.reasons.map((reason, idx) => (
                      <li key={idx} lang="en">
                        {reason}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Numerical Summary */}
              <div className="report-summary-block">
                <h4 className="sub-heading">Sumar verificare</h4>
                <dl className="report-summary-dl">
                  <div className="summary-item">
                    <dt>Total fotografii</dt>
                    <dd>{report.summary?.total ?? 0}</dd>
                  </div>
                  <div className="summary-item">
                    <dt>Neclare</dt>
                    <dd>{report.summary?.blurry ?? 0}</dd>
                  </div>
                  <div className="summary-item">
                    <dt>Fără date GPS</dt>
                    <dd>{report.summary?.no_gps ?? 0}</dd>
                  </div>
                  <div className="summary-item">
                    <dt>Suprapunere insuficientă</dt>
                    <dd>{report.summary?.low_overlap ?? 0}</dd>
                  </div>
                  <div className="summary-item">
                    <dt>Ilizibile</dt>
                    <dd>{report.summary?.unreadable ?? 0}</dd>
                  </div>
                </dl>
              </div>

              {/* Per-photo Table */}
              {report.photos && report.photos.length > 0 && (
                <div
                  className="table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-labelledby="photos-table-caption"
                >
                  <table className="photos-table">
                    <caption id="photos-table-caption">Rezultate validare pentru fiecare fotografie</caption>
                    <thead>
                      <tr>
                        <th scope="col">Nume fișier</th>
                        <th scope="col">
                          Claritate (min. {report.config?.min_blur_score ?? 100})
                        </th>
                        <th scope="col">GPS</th>
                        <th scope="col">
                          Suprapunere (min. {Math.round((report.config?.min_overlap ?? 0.6) * 100)}%)
                        </th>
                        <th scope="col">Probleme</th>
                      </tr>
                    </thead>
                    <tbody>
                      {report.photos.map((photo, idx) => (
                        <tr key={photo.filename || idx}>
                          <th scope="row" className="photo-filename-cell">
                            {photo.filename}
                          </th>
                          <td>
                            {photo.blur_score !== null && photo.blur_score !== undefined ? (
                              fmt2(photo.blur_score)
                            ) : (
                              <>
                                <span aria-hidden="true">—</span>
                                <span className="sr-only">Nu se poate calcula, fisier ilizibil</span>
                              </>
                            )}
                          </td>
                          <td>{photo.has_gps ? 'Da' : 'Nu'}</td>
                          <td>
                            {photo.overlap_with_previous !== null &&
                            photo.overlap_with_previous !== undefined ? (
                              `${(Number(photo.overlap_with_previous) * 100).toFixed(1)}%`
                            ) : idx === 0 ? (
                              <>
                                <span aria-hidden="true">—</span>
                                <span className="sr-only">
                                  Nu se aplică, este prima fotografie
                                </span>
                              </>
                            ) : (
                              <>
                                <span aria-hidden="true">—</span>
                                <span className="sr-only">
                                  Nu se aplică, lipsesc datele GPS
                                </span>
                              </>
                            )}
                          </td>
                          <td>
                            {!photo.issues || photo.issues.length === 0 ? (
                              <span className="issue-tag-ok">Fără probleme</span>
                            ) : (
                              <ul className="photo-issues-list" role="list">
                                {photo.issues.map((issue, i) => (
                                  <li key={i} className={`issue-tag issue-${issue}`}>
                                    {ISSUE_LABELS[issue] || issue}
                                  </li>
                                ))}
                              </ul>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>

        {/* Map Container */}
        <div id="map" ref={mapContainer} />

        {/* Side Panel: rezumat + declansator. Tabelul complet sta in dialogul de mai jos. */}
        {anomalies.length > 0 && (
          <section className="side-panel" aria-labelledby="anomalies-heading">
            <div className="panel-header">
              <h2 id="anomalies-heading">Anomalii detectate</h2>
              <span className="anomaly-count-badge" aria-hidden="true">
                {anomalies.length}
              </span>
            </div>

            {/* Acoperirea inaintea rezumatului: ordinea de citire e ordinea importantei —
                "a functionat?" inainte de "ce e acolo?". */}
            {truthInfo ? (
              <>
                <p className="recall-line">{truthInfo.recall}</p>
                <div className="known-toggle">
                  <input
                    type="checkbox"
                    id="show-known-changes"
                    className="known-toggle-input"
                    checked={showKnown}
                    onChange={(e) => toggleKnownChanges(e.target.checked)}
                    aria-describedby="known-toggle-help"
                  />
                  <label htmlFor="show-known-changes">
                    Afișează schimbările cunoscute pe hartă
                  </label>
                </div>
                <p id="known-toggle-help" className="help-text">
                  Cele {truthInfo.count} schimbări confirmate, cu contur galben întrerupt.
                  Anomaliile candidate au contur roșu continuu.
                </p>
                {/* Enumerarea in proza: zonele exista ca text si cu dialogul inchis, si cu
                    stratul stins. */}
                <p className="known-list-prose">
                  Schimbări cunoscute de referință: {truthInfo.labels}.
                </p>
              </>
            ) : (
              <p className="help-text">
                Acest zbor nu are schimbări cunoscute de referință, deci acoperirea nu poate
                fi calculată.
              </p>
            )}

            {/* Ascunderea candidatilor lasa ortofotoplanul curat, ca sa se vada exact ce s-a
                schimbat sub ei — cu sliderul, diferenta devine vizibila direct. */}
            <div className="known-toggle">
              <input
                type="checkbox"
                id="show-candidates"
                className="known-toggle-input candidates-toggle-input"
                checked={showCandidates}
                onChange={(e) => toggleCandidates(e.target.checked)}
                aria-describedby="candidates-toggle-help"
              />
              <label htmlFor="show-candidates">Afișează anomaliile candidate</label>
            </div>
            <p id="candidates-toggle-help" className="help-text">
              Dezactivează ca să vezi ortofotoplanul fără marcaje și să compari cu sliderul.
            </p>

            {/* Rezumatul e singurul lucru prezent permanent in arborele de accesibilitate:
                tabelul e intr-un <dialog> inchis. Deci trebuie sa stea singur in picioare. */}
            <p className="anomalies-summary">{summaryText}</p>

            <button
              type="button"
              ref={openSheetBtnRef}
              className="btn btn-primary btn-open-sheet"
              aria-haspopup="dialog"
              onClick={openSheet}
            >
              Vezi lista completă
              <span className="sr-only">, {anomaliiText(anomalies.length)}</span>
              <span className="count-chip" aria-hidden="true">{anomalies.length}</span>
            </button>

            {/* Detaliul apare doar cat timp lista e inchisa: altfel ar exista doua suprafete
                de citire concurente si id-uri duplicate care ar rupe aria-describedby. */}
            {!isSheetOpen && selectedDetail && (
              <>
                <h3 id="detail-heading" ref={detailRef} tabIndex={-1}>
                  Anomalia {selectedDetail.rank}
                </h3>
                <p id="detail-body" className="anomaly-detail">{detailText}</p>
              </>
            )}
          </section>
        )}

        {/* Lista completa, in top layer. <dialog> aduce capcana de focus, Escape si inert
            pe fundal — inclusiv peste DOM-ul injectat de MapLibre, pe care altfel l-am fi uitat. */}
        <dialog
          ref={sheetRef}
          className="anomalies-sheet"
          aria-labelledby="sheet-heading"
        >
          <div className="sheet-header">
            <h2 id="sheet-heading" ref={sheetHeadingRef} tabIndex={-1}>
              {truthInfo ? 'Anomalii detectate și schimbări cunoscute' : 'Toate anomaliile detectate'}
            </h2>
            <button type="button" className="btn btn-secondary" onClick={closeSheet}>
              Închide lista
            </button>
          </div>
          <p className="sheet-note">
            Anomalia selectată rămâne centrată pe hartă după închiderea listei.
          </p>

          {truthInfo && (
            <>
              <h3 className="sheet-subheading">Schimbări cunoscute</h3>
              <div
                className="table-scroll sheet-table-scroll known-scroll"
                tabIndex={0}
                role="region"
                aria-labelledby="known-table-caption"
              >
                <table className="anomalies-table">
                  <caption id="known-table-caption">
                    Schimbările injectate în perechea sintetică de referință și dacă au fost găsite
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Nr.</th>
                      <th scope="col">Descriere</th>
                      <th scope="col">Poziție</th>
                      <th scope="col">Rezultat</th>
                      <th scope="col">Acțiuni</th>
                    </tr>
                  </thead>
                  <tbody>
                    {truthInfo.rows.map((z) => (
                      <tr key={z.zone}>
                        <th scope="row">{z.zone}</th>
                        <td>{z.label}</td>
                        <td>{z.positionText}</td>
                        <td>{z.hit ? `Găsită de anomalia ${z.hit.rank}` : 'Negăsită'}</td>
                        <td>
                          {z.hit ? (
                            <button
                              type="button"
                              className="btn btn-secondary btn-row"
                              onClick={() => selectAnomaly(z.hit.feature, z.hit.index)}
                            >
                              Selectează
                              <span className="sr-only"> anomalia {z.hit.rank}</span>
                            </button>
                          ) : (
                            <>
                              <span aria-hidden="true">—</span>
                              <span className="sr-only">Nu există o anomalie corespunzătoare</span>
                            </>
                          )}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <h3 className="sheet-subheading">Toate anomaliile detectate</h3>
            </>
          )}

          <div
            className="table-scroll sheet-table-scroll"
            tabIndex={0}
            role="region"
            aria-labelledby="anomalies-table-caption"
          >
            <table className="anomalies-table">
              <caption id="anomalies-table-caption">
                Toate anomaliile detectate, ordonate după scor descrescător
              </caption>
              <thead>
                <tr>
                  <th scope="col">Rang</th>
                  <th scope="col">Scor</th>
                  <th scope="col">Poziție</th>
                  <th scope="col">Suprafață</th>
                  <th scope="col">Grup</th>
                  <th scope="col">Coordonate</th>
                  {truthInfo && <th scope="col">Schimbare cunoscută</th>}
                  <th scope="col">Acțiuni</th>
                </tr>
              </thead>
              <tbody>
                {anomalyRows.map((row) => (
                  <tr
                    key={row.rank}
                    aria-current={selectedAnomaly === row.rank ? 'true' : undefined}
                  >
                    <th scope="row">{row.rank}</th>
                    <td>{fmt2(row.score)}</td>
                    <td>{row.positionText}</td>
                    <td>
                      <span aria-hidden="true">{Math.round(row.areaM2)} m²</span>
                      <span className="sr-only">{metriPatratiText(Math.round(row.areaM2))}</span>
                    </td>
                    <td>{row.groupText}</td>
                    <td>
                      <code aria-hidden="true">
                        {row.lat.toFixed(6)}, {row.lon.toFixed(6)}
                      </code>
                      <span className="sr-only">{row.coordsSpoken}</span>
                    </td>
                    {truthInfo && (
                      <td>
                        {row.known ? (
                          <>
                            <span aria-hidden="true">{row.known.zone} · {row.known.label}</span>
                            <span className="sr-only">
                              Schimbarea numărul {row.known.zone}, {row.known.label}
                            </span>
                          </>
                        ) : (
                          <>
                            <span aria-hidden="true">—</span>
                            <span className="sr-only">Nu se suprapune cu nicio schimbare cunoscută</span>
                          </>
                        )}
                      </td>
                    )}
                    <td>
                      <button
                        type="button"
                        className="btn btn-secondary btn-row"
                        onClick={() => selectAnomaly(row.feature, row.index)}
                      >
                        Selectează
                        <span className="sr-only"> anomalia {row.rank}</span>
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </dialog>

        {/* Floating Bottom Slider */}
        <div className="slider-widget" role="group" aria-label="Comparație între zboruri">
          <div className="slider-labels">
            <span className="label-before">Zbor inițial (T0)</span>
            <span className="slider-value">Zbor curent: {Math.round(opacity * 100)}%</span>
            <span className="label-after">Zbor curent (T1)</span>
          </div>
          <div className="slider-control-row">
            <input
              id="opacity-slider"
              type="range"
              min="0"
              max="1"
              step="0.01"
              value={opacity}
              onChange={handleSliderChange}
              className="opacity-slider"
              aria-label="Amestec între zborul inițial T0 și zborul curent T1"
              aria-valuetext={`${Math.round(opacity * 100)}% zbor curent T1, ${100 - Math.round(opacity * 100)}% zbor inițial T0`}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

