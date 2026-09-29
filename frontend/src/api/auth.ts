/**
 * Authentication and Desktop Session Utility Module.
 * Coordinates token management, sidecar backend session invalidation,
 * Clerk state cleanup, and seamless sign-out transitions.
 */

import { getApiBaseUrl, setAuthTokenGetter } from './client.ts';
import { resolveBackendUrl } from './tauri-bridge.ts';

export interface DesktopUser {
  id?: string;
  email?: string;
  firstName?: string;
  lastName?: string;
  imageUrl?: string | null;
}

/**
 * Retrieve cached desktop session token from sessionStorage or localStorage.
 */
export function getDesktopToken(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return (
      sessionStorage.getItem('desktop_auth_token') ||
      localStorage.getItem('desktop_auth_token')
    );
  } catch {
    return null;
  }
}

/**
 * Retrieve cached desktop user profile.
 */
export function getDesktopUser(): DesktopUser | null {
  if (typeof window === 'undefined') return null;
  try {
    const raw =
      sessionStorage.getItem('desktop_auth_user') ||
      localStorage.getItem('desktop_auth_user');
    if (!raw) return null;
    return JSON.parse(raw) as DesktopUser;
  } catch {
    return null;
  }
}

/**
 * Invalidate desktop session on the backend sidecar and clear all local storage tokens.
 */
export async function clearDesktopSession(): Promise<void> {
  // 1. Clear web storage
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.removeItem('desktop_auth_token');
      sessionStorage.removeItem('desktop_auth_user');
      localStorage.removeItem('desktop_auth_token');
      localStorage.removeItem('desktop_auth_user');
    } catch {
      // ignore storage access restrictions
    }
  }

  // 2. Clear in-memory token getter
  setAuthTokenGetter(null);

  // 3. Clear session in backend sidecar
  try {
    const base =
      getApiBaseUrl() || (await resolveBackendUrl()) || 'http://127.0.0.1:18000';
    await fetch(`${base}/api/auth/desktop-session`, {
      method: 'DELETE',
    });
  } catch (err) {
    console.debug('[auth] Failed to DELETE backend desktop-session:', err);
  }
}

/**
 * Comprehensive application sign-out function.
 * Clears tokens, terminates sidecar session, safely invokes Clerk signOut,
 * prevents auto-redirect race conditions, and triggers navigation callback.
 */
export async function signOutApp(
  clerkSignOut?: (options?: { redirectUrl?: string }) => Promise<void>,
  onComplete?: () => void
): Promise<void> {
  // 1. Mark explicit sign-out flag to prevent AuthView redirect bouncing
  if (typeof window !== 'undefined') {
    try {
      sessionStorage.setItem('pc_signed_out', 'true');
    } catch {
      // ignore
    }
  }

  // 2. Clear desktop session tokens locally and on backend sidecar
  await clearDesktopSession();

  // 3. Notify app components of signed-out status
  if (typeof window !== 'undefined') {
    window.dispatchEvent(new CustomEvent('prompt-compiler:signed-out'));
  }

  // 4. Safely invoke Clerk signOut with bounded timeout (prevents hanging if ClerkJs not ready)
  if (clerkSignOut) {
    try {
      await Promise.race([
        clerkSignOut({ redirectUrl: '/auth' }),
        new Promise((resolve) => setTimeout(resolve, 800)),
      ]);
    } catch (err) {
      console.debug('[auth] Clerk sign out notice / fallback:', err);
    }
  }

  // 5. Execute navigation callback
  if (onComplete) {
    onComplete();
  }
}
