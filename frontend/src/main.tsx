import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import './index.css';
import App from './App.tsx';
import { initTauriBridge } from './api/tauri-bridge';

// Initialise Tauri ↔ backend bridge (no-op in browser/Vite dev mode).
initTauriBridge().catch(console.error);

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);

