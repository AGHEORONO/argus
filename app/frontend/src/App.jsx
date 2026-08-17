import React, { useEffect, useRef, useState } from 'react';
import maplibregl from 'maplibre-gl';

const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000';
const DEFAULT_CENTER = [-78.43072, 0.01334];
const DEFAULT_ZOOM = 16.5;

export default function App() {
  const mapContainer = useRef(null);
  const mapRef = useRef(null);
  const [opacity, setOpacity] = useState(0.5);
  const [status, setStatus] = useState('Inițializare...');
  const [isProcessing, setIsProcessing] = useState(false);
  const [anomalies, setAnomalies] = useState([]);
  const [selectedAnomaly, setSelectedAnomaly] = useState(null);

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

    return () => map.remove();
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
            setStatus(`Stare: ${statusData.status}`);

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

  const flyToAnomaly = (feature) => {
    setSelectedAnomaly(feature);
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
          <div className={`status-badge ${isProcessing ? 'loading' : ''}`}>
            <span className="status-dot"></span>
            <span>{status}</span>
          </div>
        </div>
      </header>

      {/* Map Container */}
      <div id="map" ref={mapContainer} />

      {/* Side Panel: Anomalies Inspector */}
      {anomalies.length > 0 && (
        <aside className="side-panel">
          <div className="panel-header">
            <h2>Candidați Anomalii</h2>
            <span className="anomaly-count-badge">{anomalies.length}</span>
          </div>
          <div className="candidates-list">
            {anomalies.map((f, i) => (
              <div
                key={f.id || i}
                className="candidate-item"
                onClick={() => flyToAnomaly(f)}
              >
                <span className="candidate-rank">#{f.properties?.rank || i + 1}</span>
                <span className="candidate-score">
                  Scor: {Number(f.properties?.anomaly_score || 0).toFixed(4)}
                </span>
              </div>
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
            aria-label="Slider tranziție Before After"
          />
        </div>
      </div>
    </div>
  );
}
