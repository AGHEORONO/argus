import React from 'react';
import ReactDOM from 'react-dom/client';

// Fonturile si CSS-ul hartii se impacheteaza in build, nu se cer de la Google Fonts si unpkg.
// Aplicatia de desktop ruleaza si fara internet: de pe un CDN ar lipsi exact atunci, iar
// harta ar ramane fara stiluri si textul ar cadea pe fontul de sistem.
// Doar greutatile chiar folosite (400/500/600), ca sa nu se importe toata familia.
import '@fontsource/ibm-plex-sans/400.css';
import '@fontsource/ibm-plex-sans/500.css';
import '@fontsource/ibm-plex-sans/600.css';
import '@fontsource/ibm-plex-mono/400.css';
import '@fontsource/ibm-plex-mono/500.css';
import 'maplibre-gl/dist/maplibre-gl.css';

import App from './App.jsx';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
