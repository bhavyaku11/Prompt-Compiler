/**
 * Service health check API endpoints.
 */

import { fetchApi } from './client';
import type { HealthResponse } from '@/types/api';

/**
 * Ping backend health via GET /api/health.
 */
export async function getHealth(): Promise<HealthResponse> {
  return fetchApi<HealthResponse>('/api/health', {
    method: 'GET',
  });
}
