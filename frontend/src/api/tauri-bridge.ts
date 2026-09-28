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

import { setApiBaseUrl } from './client.ts';

/** True when running inside a Tauri window. */
export function isTauri(): boolean {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window;
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
  if (!isTauri()) {
    // Browser / Vite dev mode — nothing to do.
    return;
  }

  try {
    const { listen } = await import('@tauri-apps/api/event');

    // "backend-ready" carries the base URL string, e.g. "http://127.0.0.1:18000"
    const unlistenReady = await listen<string>('backend-ready', (event) => {
      const baseUrl = event.payload;
      if (baseUrl) {
        console.info(`[tauri-bridge] backend ready at ${baseUrl}`);
        setApiBaseUrl(baseUrl);
      }
      // We only need to set this once — unlisten to avoid memory leaks.
      unlistenReady();
    });

    // "backend-failed" means the sidecar could not start.
    const unlistenFailed = await listen<string>('backend-failed', (event) => {
      console.error(`[tauri-bridge] backend failed: ${event.payload}`);
      // Surface to the user via a global custom event so the UI can react.
      window.dispatchEvent(
        new CustomEvent('prompt-compiler:backend-failed', {
          detail: event.payload,
        })
      );
      unlistenFailed();
    });

    console.info('[tauri-bridge] listening for backend-ready / backend-failed events');
  } catch (err) {
    // @tauri-apps/api not available (e.g., running in a plain browser after
    // the Tauri check somehow failed). Fail gracefully.
    console.warn('[tauri-bridge] failed to set up Tauri event listeners:', err);
  }
}

