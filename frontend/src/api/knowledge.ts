/**
 * Vector Knowledge Base API endpoints.
 */

import { fetchApi } from './client';
import type {
  KnowledgeSource,
  BatchDocumentIngestionResponse,
  IngestDirectoryRequest,
} from '@/types/api';

/**
 * List indexed knowledge sources for a project from GET /api/projects/{projectId}/knowledge/sources.
 */
export async function getKnowledgeSources(projectId: string): Promise<KnowledgeSource[]> {
  return fetchApi<KnowledgeSource[]>(`/api/projects/${projectId}/knowledge/sources`, {
    method: 'GET',
  });
}

/**
 * Recursively discover and ingest supported files within a project directory via
 * POST /api/projects/{projectId}/knowledge/ingest/directory.
 */
export async function ingestProjectDirectory(
  projectId: string,
  request?: IngestDirectoryRequest
): Promise<BatchDocumentIngestionResponse> {
  return fetchApi<BatchDocumentIngestionResponse>(
    `/api/projects/${projectId}/knowledge/ingest/directory`,
    {
      method: 'POST',
      body: JSON.stringify(request ?? {}),
    }
  );
}
