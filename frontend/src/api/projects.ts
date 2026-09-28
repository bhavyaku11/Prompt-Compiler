/**
 * Project and Project Memory API endpoints.
 */

import { fetchApi } from './client';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  ProjectContext,
  ProjectMemory,
} from '@/types/api';

/**
 * List projects from GET /api/projects.
 */
export async function getProjects(limit = 50, offset = 0): Promise<Project[]> {
  return fetchApi<Project[]>(`/api/projects?limit=${limit}&offset=${offset}`, {
    method: 'GET',
  });
}

/**
 * Get project metadata by ID from GET /api/projects/{projectId}.
 */
export async function getProject(projectId: string): Promise<Project> {
  return fetchApi<Project>(`/api/projects/${projectId}`, {
    method: 'GET',
  });
}

/**
 * Create a new development project via POST /api/projects.
 */
export async function createProject(data: ProjectCreate): Promise<Project> {
  return fetchApi<Project>('/api/projects', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update project metadata via PATCH /api/projects/{projectId}.
 */
export async function updateProject(projectId: string, data: ProjectUpdate): Promise<Project> {
  return fetchApi<Project>(`/api/projects/${projectId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Retrieve aggregated, deterministically sorted project context via GET /api/projects/{projectId}/context.
 */
export async function getProjectContext(projectId: string): Promise<ProjectContext> {
  return fetchApi<ProjectContext>(`/api/projects/${projectId}/context`, {
    method: 'GET',
  });
}

/**
 * List active memories for a project via GET /api/projects/{projectId}/memories.
 */
export async function getProjectMemories(projectId: string): Promise<ProjectMemory[]> {
  return fetchApi<ProjectMemory[]>(`/api/projects/${projectId}/memories`, {
    method: 'GET',
  });
}
