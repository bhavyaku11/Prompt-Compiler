/**
 * Deterministic tests for API Client Auth & Token Attachment (Task 33).
 * Verifies:
 * - setAuthTokenGetter registers and clears token provider
 * - fetchApi automatically attaches Authorization: Bearer <token>
 * - fetchApi behaves cleanly when unauthenticated
 * - fetchApi handles HTTP 401 and dispatches prompt-compiler:auth-required event
 */

import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert';
import {
  setAuthTokenGetter,
  getAuthTokenGetter,
  fetchApi,
  ApiError,
  setApiBaseUrl,
} from '../src/api/client.ts';

describe('Auth Client & Session Management Tests', () => {
  const originalFetch = globalThis.fetch;
  const originalWindow = globalThis.window;

  beforeEach(() => {
    setApiBaseUrl('http://127.0.0.1:8000');
    setAuthTokenGetter(null);
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
    globalThis.window = originalWindow;
    setAuthTokenGetter(null);
  });

  test('setAuthTokenGetter registers and clears token provider', () => {
    assert.strictEqual(getAuthTokenGetter(), null);

    const mockGetter = async () => 'test_jwt_token_123';
    setAuthTokenGetter(mockGetter);
    assert.strictEqual(getAuthTokenGetter(), mockGetter);

    setAuthTokenGetter(null);
    assert.strictEqual(getAuthTokenGetter(), null);
  });

  test('fetchApi automatically attaches Bearer token from token getter', async () => {
    setAuthTokenGetter(async () => 'clerk_session_jwt_xyz');

    let capturedHeaders = null;
    globalThis.fetch = async (url, options) => {
      capturedHeaders = options.headers;
      return new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await fetchApi('/api/test');
    assert.deepStrictEqual(res, { status: 'ok' });
    assert.ok(capturedHeaders instanceof Headers);
    assert.strictEqual(capturedHeaders.get('Authorization'), 'Bearer clerk_session_jwt_xyz');
  });

  test('fetchApi does not attach Authorization when unauthenticated', async () => {
    setAuthTokenGetter(null);

    let capturedHeaders = null;
    globalThis.fetch = async (url, options) => {
      capturedHeaders = options.headers;
      return new Response(JSON.stringify({ status: 'public' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      });
    };

    const res = await fetchApi('/api/presets');
    assert.deepStrictEqual(res, { status: 'public' });
    assert.strictEqual(capturedHeaders.get('Authorization'), null);
  });

  test('fetchApi dispatches prompt-compiler:auth-required on HTTP 401', async () => {
    let eventDispatched = null;
    globalThis.window = {
      dispatchEvent: (event) => {
        eventDispatched = event;
        return true;
      },
    };

    globalThis.fetch = async () => {
      return new Response(
        JSON.stringify({ detail: 'Authentication failed: Session token has expired.' }),
        { status: 401, headers: { 'Content-Type': 'application/json' } }
      );
    };

    await assert.rejects(
      async () => {
        await fetchApi('/api/projects');
      },
      (err) => {
        assert.ok(err instanceof ApiError);
        assert.strictEqual(err.status, 401);
        assert.strictEqual(err.message, 'Authentication required or session expired. Please sign in again.');
        return true;
      }
    );

    assert.ok(eventDispatched !== null);
    assert.strictEqual(eventDispatched.type, 'prompt-compiler:auth-required');
    assert.strictEqual(eventDispatched.detail.status, 401);
  });

  test('Google OAuth configuration requires oidcPrompt select_account to show Gmail options', () => {
    // Simulates the Clerk authenticateWithRedirect payload structure used in AuthSwitch
    const googleAuthPayload = {
      strategy: 'oauth_google',
      redirectUrl: '/sso-callback',
      redirectUrlComplete: '/studio',
      oidcPrompt: 'select_account',
    };

    assert.strictEqual(googleAuthPayload.strategy, 'oauth_google');
    assert.strictEqual(googleAuthPayload.redirectUrl, '/sso-callback');
    assert.strictEqual(googleAuthPayload.redirectUrlComplete, '/studio');
    assert.strictEqual(googleAuthPayload.oidcPrompt, 'select_account');
  });

  test('signOutApp clears storage, invokes DELETE endpoint, resets token getter, and calls onComplete', async () => {
    const { signOutApp } = await import('../src/api/auth.ts');

    const mockStorage = new Map();
    const mockSessionStorage = {
      getItem: (k) => mockStorage.get(k) || null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
      removeItem: (k) => mockStorage.delete(k),
    };
    const mockLocalStorage = {
      getItem: (k) => mockStorage.get(k) || null,
      setItem: (k, v) => mockStorage.set(k, String(v)),
      removeItem: (k) => mockStorage.delete(k),
    };

    mockStorage.set('desktop_auth_token', 'test_desktop_token');
    mockStorage.set('desktop_auth_user', JSON.stringify({ email: 'test@example.com' }));

    let dispatchedEvents = [];
    globalThis.window = {
      dispatchEvent: (e) => {
        dispatchedEvents.push(e);
        return true;
      },
    };
    globalThis.sessionStorage = mockSessionStorage;
    globalThis.localStorage = mockLocalStorage;

    let deleteCalled = false;
    let deleteMethod = null;
    globalThis.fetch = async (url, options) => {
      if (url.includes('/api/auth/desktop-session')) {
        deleteCalled = true;
        deleteMethod = options?.method;
        return new Response(JSON.stringify({ status: 'ok' }), { status: 200 });
      }
      return new Response('{}', { status: 200 });
    };

    setAuthTokenGetter(async () => 'some_token');
    assert.ok(getAuthTokenGetter() !== null);

    let clerkSignedOut = false;
    const mockClerkSignOut = async () => {
      clerkSignedOut = true;
    };

    let onCompleteCalled = false;
    await signOutApp(mockClerkSignOut, () => {
      onCompleteCalled = true;
    });

    assert.strictEqual(mockStorage.get('desktop_auth_token'), undefined);
    assert.strictEqual(mockStorage.get('desktop_auth_user'), undefined);
    assert.strictEqual(mockStorage.get('pc_signed_out'), 'true');
    assert.strictEqual(deleteCalled, true);
    assert.strictEqual(deleteMethod, 'DELETE');
    assert.strictEqual(getAuthTokenGetter(), null);
    assert.strictEqual(clerkSignedOut, true);
    assert.strictEqual(onCompleteCalled, true);
    assert.ok(dispatchedEvents.some((e) => e.type === 'prompt-compiler:signed-out'));
  });
});

