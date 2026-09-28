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
});
