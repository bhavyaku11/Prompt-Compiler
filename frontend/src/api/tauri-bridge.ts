/**
 * Tauri sidecar bridge.
 *
 * In Tauri desktop builds, the Rust layer spawns the FastAPI sidecar and
 * emits a "backend-ready" event with the local base URL once it's healthy.
 * This module listens for that event and wires it into the API client.
 *
 * In the browser (Vite dev mode), this module is a no-op — the Vite proxy
 * forwards `/api` requests to the running backend directly.
 */

import { setApiBaseUrl, getApiBaseUrl, setBackendUrlResolver } from './client.ts';

/** True when running inside a Tauri window. */
export function isTauri(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    Boolean((window as unknown as { isTauri?: boolean }).isTauri) ||
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window
  );
}

/**
 * Probe local ports (18000..18020, plus 8000 fallback) to find an active Prompt Compiler backend.
 */
export async function probeLocalBackend(): Promise<string | null> {
  const ports = Array.from({ length: 21 }, (_, i) => 18000 + i);
  ports.unshift(8000);

  for (const port of ports) {
    try {
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 250);
      const res = await fetch(`http://127.0.0.1:${port}/api/health`, {
        signal: controller.signal,
      });
      clearTimeout(timeoutId);
      if (res.ok) {
        const data = await res.json();
        if (data && data.status === 'ok') {
          const url = `http://127.0.0.1:${port}`;
          console.info(`[tauri-bridge] probed active local engine at ${url}`);
          setApiBaseUrl(url);
          return url;
        }
      }
    } catch {
      // Continue checking next candidate port
    }
  }
  return null;
}

/**
 * Resolve the backend URL through cache, Tauri command, or port probing.
 */
export async function resolveBackendUrl(): Promise<string | null> {
  const current = getApiBaseUrl();
  if (current) return current;

  // Attempt Tauri IPC invoke
  if (isTauri()) {
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      const url = await invoke<string | null>('get_backend_url');
      if (url) {
        setApiBaseUrl(url);
        return url;
      }
    } catch (err) {
      console.debug('[tauri-bridge] get_backend_url invoke not available yet:', err);
    }
  }

  // Fallback to rapid loopback probing
  return await probeLocalBackend();
}

/**
 * Open the native macOS directory picker and return the chosen directory path.
 *
 * In Tauri desktop mode:
 *   - Invokes the native macOS directory picker dialog via @tauri-apps/plugin-dialog
 *   - Restricts selection strictly to directories (directory: true, multiple: false)
 *   - Returns the absolute path as string, or null if cancelled
 *
 * In browser mode (Vite dev mode):
 *   - Safely returns null without throwing or crashing
 */
export async function selectProjectFolder(defaultPath?: string): Promise<string | null> {
  if (!isTauri()) {
    console.info('[tauri-bridge] Native folder picker is only available in desktop app mode.');
    return null;
  }

  try {
    const { open } = await import('@tauri-apps/plugin-dialog');
    const selected = await open({
      directory: true,
      multiple: false,
      title: 'Select Project Root Folder',
      defaultPath: defaultPath || undefined,
    });

    if (typeof selected === 'string' && selected.trim()) {
      return selected.trim();
    }
    return null;
  } catch (err) {
    console.error('[tauri-bridge] Failed to open native folder picker:', err);
    return null;
  }
}

/**
 * Initialise the Tauri ↔ frontend bridge.
 * Call this once, early in the app lifecycle (e.g. from main.tsx).
 */
export async function initTauriBridge(): Promise<void> {
  // Always register backend resolver for desktop environments
  setBackendUrlResolver(resolveBackendUrl);

  if (!isTauri()) {
    // Browser / Vite dev mode — nothing to do.
    return;
  }

  // 1. Immediately attempt URL resolution from cache / Tauri / probing
  resolveBackendUrl().catch((err) => {
    console.debug('[tauri-bridge] Early URL resolution attempt:', err);
  });

  // 2. Set up event listeners for sidecar lifecycle
  try {
    const { listen } = await import('@tauri-apps/api/event');

    // "backend-ready" carries the base URL string, e.g. "http://127.0.0.1:18000"
    await listen<string>('backend-ready', (event) => {
      const baseUrl = event.payload;
      if (baseUrl) {
        console.info(`[tauri-bridge] backend ready event received: ${baseUrl}`);
        setApiBaseUrl(baseUrl);
      }
    });

    // "backend-failed" means the sidecar could not start.
    await listen<string>('backend-failed', (event) => {
      console.error(`[tauri-bridge] backend failed event received: ${event.payload}`);
      window.dispatchEvent(
        new CustomEvent('prompt-compiler:backend-failed', {
          detail: event.payload,
        })
      );
    });

    console.info('[tauri-bridge] listening for backend-ready / backend-failed events');
  } catch (err) {
    console.warn('[tauri-bridge] failed to set up Tauri event listeners:', err);
  }
}

/**
 * Open an external URL in Google Chrome (with default browser fallback).
 * In Tauri desktop mode:
 *   - Attempts Rust IPC command `open_in_browser`
 *   - Calls backend `/api/auth/open-browser` as robust fallback
 * In browser mode:
 *   - Opens target in a new window/tab
 */
export async function openExternalUrl(url: string): Promise<boolean> {
  if (!url || (!url.startsWith('http://') && !url.startsWith('https://'))) {
    console.warn('[tauri-bridge] Invalid URL scheme for openExternalUrl:', url);
    return false;
  }

  if (isTauri()) {
    // 1. Try Tauri IPC command
    try {
      const { invoke } = await import('@tauri-apps/api/core');
      await invoke('open_in_browser', { url });
      return true;
    } catch (err) {
      console.debug('[tauri-bridge] Tauri open_in_browser invoke error, falling back to backend:', err);
    }

    // 2. Fallback to FastAPI sidecar open-browser endpoint
    try {
      const base = getApiBaseUrl() || (await resolveBackendUrl()) || 'http://127.0.0.1:18000';
      const res = await fetch(`${base}/api/auth/open-browser`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url }),
      });
      if (res.ok) {
        return true;
      }
    } catch (err) {
      console.warn('[tauri-bridge] Backend open-browser endpoint error:', err);
    }
  }

  // 3. Fallback to standard browser window.open
  if (typeof window !== 'undefined') {
    window.open(url, '_blank');
    return true;
  }
  return false;
}


