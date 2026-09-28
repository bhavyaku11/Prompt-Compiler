/**
 * Agent Presets API endpoints.
 */

import { fetchApi } from './client';
import type { AgentPreset } from '@/types/api';

/**
 * List supported target AI coding agent formatting presets from GET /api/presets.
 */
export async function getAgentPresets(): Promise<AgentPreset[]> {
  return fetchApi<AgentPreset[]>('/api/presets', {
    method: 'GET',
  });
}
