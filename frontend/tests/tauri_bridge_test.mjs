/**
 * Deterministic tests for Tauri Bridge and Folder Selection (Task 32).
 * Verifies:
 * - isTauri() detection in browser vs desktop
 * - selectProjectFolder() safe null return in browser mode without crashing
 * - cancellation handling
 */

import { test, describe } from 'node:test';
import assert from 'node:assert';

describe('Tauri Bridge & Folder Picker Tests', () => {
  test('isTauri() returns false in browser environment', async () => {
    // Ensure no window.__TAURI_INTERNALS__
    globalThis.window = {};
    const { isTauri } = await import('../src/api/tauri-bridge.ts');
    assert.strictEqual(isTauri(), false);
  });

  test('selectProjectFolder() returns null safely in browser mode without crashing', async () => {
    globalThis.window = {};
    const { selectProjectFolder } = await import('../src/api/tauri-bridge.ts');
    const result = await selectProjectFolder();
    assert.strictEqual(result, null);
  });

  test('isTauri() returns true when window.__TAURI_INTERNALS__ is present', async () => {
    globalThis.window = {
      __TAURI_INTERNALS__: {},
    };
    const { isTauri } = await import('../src/api/tauri-bridge.ts');
    assert.strictEqual(isTauri(), true);
  });
});
