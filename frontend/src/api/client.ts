/**
 * Prompt Compiler Central API Client.
 * Communicates with backend endpoints via Vite reverse proxy or configured base URL.
 */

import type { ApiErrorResponse } from '@/types/api';

export class ApiError extends Error {
  public status: number;
  public detail: string | unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

declare global {
  interface Window {
    __PROMPT_COMPILER_API_BASE__?: string;
    Clerk?: {
      session?: {
        getToken: () => Promise<string | null>;
      };
    };
  }
}

export type AuthTokenGetter = () => Promise<string | null>;
export type BackendUrlResolver = () => Promise<string | null>;

let authTokenGetter: AuthTokenGetter | null = null;
let backendUrlResolver: BackendUrlResolver | null = null;

export function setAuthTokenGetter(getter: AuthTokenGetter | null): void {
  authTokenGetter = getter;
}

export function getAuthTokenGetter(): AuthTokenGetter | null {
  return authTokenGetter;
}

export function setBackendUrlResolver(resolver: BackendUrlResolver | null): void {
  backendUrlResolver = resolver;
}

export function getBackendUrlResolver(): BackendUrlResolver | null {
  return backendUrlResolver;
}

let customApiBaseUrl: string | null = null;

export function setApiBaseUrl(url: string | null): void {
  customApiBaseUrl = url ? url.replace(/\/+$/, '') : null;
  if (typeof window !== 'undefined') {
    try {
      if (customApiBaseUrl) {
        sessionStorage.setItem('prompt_compiler_api_base', customApiBaseUrl);
      } else {
        sessionStorage.removeItem('prompt_compiler_api_base');
      }
    } catch {
      // ignore storage access issues
    }

    if (customApiBaseUrl) {
      window.dispatchEvent(
        new CustomEvent('prompt-compiler:backend-ready', {
          detail: customApiBaseUrl,
        })
      );
    }
  }
}

export function getApiBaseUrl(): string {
  if (customApiBaseUrl) {
    return customApiBaseUrl;
  }
  if (typeof window !== 'undefined') {
    if (window.__PROMPT_COMPILER_API_BASE__) {
      return window.__PROMPT_COMPILER_API_BASE__.replace(/\/+$/, '');
    }
    try {
      const stored = sessionStorage.getItem('prompt_compiler_api_base');
      if (stored) {
        customApiBaseUrl = stored.replace(/\/+$/, '');
        return customApiBaseUrl;
      }
    } catch {
      // ignore storage access issues
    }
  }
  if (import.meta.env.VITE_API_BASE_URL) {
    return import.meta.env.VITE_API_BASE_URL.replace(/\/+$/, '');
  }
  return '';
}

function isDesktopEnv(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    Boolean((window as unknown as { isTauri?: boolean }).isTauri) ||
    '__TAURI_INTERNALS__' in window ||
    '__TAURI__' in window
  );
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  let base = getApiBaseUrl();

  // If in desktop environment and base URL is not yet established, attempt dynamic resolution
  if (!base && isDesktopEnv()) {
    if (backendUrlResolver) {
      try {
        const resolved = await backendUrlResolver();
        if (resolved) {
          base = resolved;
        }
      } catch (err) {
        console.warn('[client] Failed to dynamically resolve backend URL:', err);
      }
    }
    // Re-check after resolver attempt
    if (!base) {
      base = getApiBaseUrl();
    }
  }

  // In desktop app, never execute relative fetch without an active base URL (causes WebKit pattern error)
  if (!base && isDesktopEnv()) {
    throw new ApiError(
      503,
      'Local Engine is starting up or unreachable. Please wait a moment and try again.'
    );
  }

  const url = `${base}${endpoint}`;

  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body && typeof options.body === 'string') {
    headers.set('Content-Type', 'application/json');
  }

  // Attach Authorization header if not already provided
  if (!headers.has('Authorization')) {
    let token: string | null = null;
    if (authTokenGetter) {
      try {
        token = await authTokenGetter();
      } catch (err) {
        console.warn('[client] Failed to get auth token from getter:', err);
      }
    } else if (typeof window !== 'undefined' && window.Clerk?.session) {
      try {
        token = await window.Clerk.session.getToken();
      } catch (err) {
        console.warn('[client] Failed to get auth token from window.Clerk:', err);
      }
    }
    if (token) {
      headers.set('Authorization', `Bearer ${token}`);
    }
  }

  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Network request failed';
    throw new ApiError(0, `Cannot connect to Prompt Compiler backend. Please check that the server is running. (${message})`);
  }

  if (!response.ok) {
    let errorDetail = `Request failed with status ${response.status}`;
    try {
      const errJson = (await response.json()) as ApiErrorResponse;
      if (errJson && errJson.detail) {
        if (typeof errJson.detail === 'string') {
          errorDetail = errJson.detail;
        } else if (Array.isArray(errJson.detail)) {
          errorDetail = errJson.detail.map((e) => e.msg).join('; ');
        }
      }
    } catch {
      // response was not JSON
    }

    // Friendly translations for specific status codes
    let friendlyMessage = errorDetail;
    if (response.status === 401) {
      friendlyMessage = 'Authentication required or session expired. Please sign in again.';
      if (typeof window !== 'undefined') {
        window.dispatchEvent(
          new CustomEvent('prompt-compiler:auth-required', {
            detail: { status: 401, message: friendlyMessage, detail: errorDetail },
          })
        );
      }
    } else if (response.status === 503) {
      friendlyMessage = 'Local AI service (Ollama) is unavailable. Please verify that Ollama is running (`ollama serve`).';
    } else if (response.status === 504) {
      friendlyMessage = 'Inference request timed out. The local model took too long to complete compilation.';
    } else if (response.status === 502) {
      friendlyMessage = `Local AI pipeline error: ${errorDetail}`;
    } else if (response.status === 422) {
      friendlyMessage = `Validation error: ${errorDetail}`;
    }

    throw new ApiError(response.status, friendlyMessage, errorDetail);
  }

  return (await response.json()) as T;
}
