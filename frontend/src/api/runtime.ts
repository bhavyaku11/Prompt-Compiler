/**
 * Runtime and service health status API methods.
 */

import { fetchApi } from './client';
import type { RuntimeStatusResponse } from '@/types/api';

/**
 * Fetch consolidated runtime and service readiness status.
 * Safe, operational inspection endpoint returning backend, db, and Ollama status.
 */
export async function getRuntimeStatus(): Promise<RuntimeStatusResponse> {
  return fetchApi<RuntimeStatusResponse>('/api/runtime/status');
}
