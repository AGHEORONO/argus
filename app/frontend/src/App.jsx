import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';

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
  const reportHeadingRef = useRef(null);

  // Existing states
  const [opacity, setOpacity] = useState(0.5);
  const [status, setStatus] = useState('Inițializare...');
  const [isProcessing, setIsProcessing] = useState(false);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);

  // Ingest panel states
  const [flightId, setFlightId] = useState('test');
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
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: true }), 'top-left');

    map.on('load', () => {
      // 1. Before Raster Layer
      map.addSource('before-source', {
        type: 'raster',
        tiles: [`${API_BASE}/tiles/before/{z}/{x}/{y}.png`],
        tileSize: 256,
        bounds: [-78.43263, 0.01054, -78.42882, 0.01614],
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
        bounds: [-78.43263, 0.01054, -78.42882, 0.01614],
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

      map.addLayer({
        id: 'anomalies-line',
        type: 'line',
        source: 'anomalies-source',
        paint: {
          'line-color': '#f87171',
          'line-width': 2.5,
        },
      });

      // Hover / Click Popup on Anomalies
      map.on('click', 'anomalies-fill', (e) => {
        if (!e.features || !e.features.length) return;
        const feature = e.features[0];
        const props = feature.properties || {};
        new maplibregl.Popup()
          .setLngLat(e.lngLat)
          .setHTML(
            `<strong>Anomalie #${props.rank || ''}</strong><br/>` +
            `Scor: ${Number(props.anomaly_score || 0).toFixed(4)}<br/>` +
            `Patch: ${props.patch_index || ''}`
          )
          .addTo(map);
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

  const applyGeoJsonResult = (geojson) => {
    if (mapRef.current && mapRef.current.getSource('anomalies-source')) {
      mapRef.current.getSource('anomalies-source').setData(geojson);
    }
    if (geojson && geojson.features) {
      setAnomalies(geojson.features);
    }
  };

  const flyToAnomaly = (feature, index) => {
    setSelectedAnomaly(feature.id ?? index);
    // Activarea muta doar camera pe un canvas WebGL — fara acest anunt, controlul nu produce
    // niciun efect perceptibil pentru cine nu vede harta.
    const rank = feature.properties?.rank ?? index + 1;
    const score = Number(feature.properties?.anomaly_score || 0).toFixed(2);
    announceStatus(`Harta centrată pe anomalia ${rank}, scor ${score}.`);
    if (!mapRef.current || !feature.geometry) return;

    const coords = feature.geometry.coordinates[0];
    const avgLng = coords.reduce((sum, c) => sum + c[0], 0) / coords.length;
    const avgLat = coords.reduce((sum, c) => sum + c[1], 0) / coords.length;

    mapRef.current.flyTo({
      center: [avgLng, avgLat],
      zoom: 18.5,
      speed: 1.2,
    });
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

        <div className="header-status">
          <div className={`status-badge ${isProcessing ? 'loading' : ''}`} role="status">
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
                              Number(photo.blur_score).toFixed(2)
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

        {/* Side Panel: Anomalies Inspector */}
        {anomalies.length > 0 && (
          <aside className="side-panel" aria-labelledby="anomalies-heading">
            <div className="panel-header">
              <h2 id="anomalies-heading">Candidați Anomalii</h2>
              <span className="anomaly-count-badge" aria-label={`${anomalies.length} candidați`}>
                {anomalies.length}
              </span>
            </div>
            <div className="candidates-list">
              {anomalies.map((f, i) => (
                <button
                  key={f.id || i}
                  type="button"
                  className="candidate-item"
                  aria-current={selectedAnomaly === (f.id ?? i) ? 'true' : undefined}
                  aria-label={`Anomalia ${f.properties?.rank || i + 1}, scor ${Number(
                    f.properties?.anomaly_score || 0
                  ).toFixed(2)}. Centrează harta.`}
                  onClick={() => flyToAnomaly(f, i)}
                >
                  <span className="candidate-rank">#{f.properties?.rank || i + 1}</span>
                  <span className="candidate-score">
                    Scor: {Number(f.properties?.anomaly_score || 0).toFixed(4)}
                  </span>
                </button>
              ))}
            </div>
          </aside>
        )}

        {/* Floating Bottom Slider */}
        <div className="slider-widget">
          <div className="slider-labels">
            <span className="label-before">Before (T0)</span>
            <span className="slider-value">After: {Math.round(opacity * 100)}%</span>
            <span className="label-after">After (T1)</span>
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
              aria-label="Tranziție între zborul Before și zborul After"
              aria-valuetext={`After ${Math.round(opacity * 100)}%`}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

