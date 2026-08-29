import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

/**
 * Modul `desktop` fixeaza VITE_API_BASE pe sirul gol, adica "aceeasi origine".
 *
 * Deliberat aici si nu intr-un `.env.desktop`: `.gitignore` ignora `.env*`, deci fisierul
 * n-ar ajunge pe alta masina si build-ul de desktop ar cadea tacut inapoi pe adresa absoluta
 * de dezvoltare. Pe Windows mai e o capcana in plus — `$env:VITE_API_BASE = ""` in PowerShell
 * STERGE variabila in loc s-o goleasca, deci nici pe calea aia nu se poate transmite.
 */
export default defineConfig(({ mode }) => ({
  plugins: [react()],
  define: mode === 'desktop'
    ? { 'import.meta.env.VITE_API_BASE': JSON.stringify('') }
    : {},
  server: {
    host: '127.0.0.1',
    port: 5173,
  },
}));
