/**
 * Prompt Compilation API endpoints.
 */

import { fetchApi } from './client';
import type { CompileRequest, CompileResponse } from '@/types/api';

/**
 * Execute end-to-end prompt compilation via POST /api/compile.
 * Normalizes all array fields to prevent null-dereference errors in UI components.
 */
export async function compilePrompt(request: CompileRequest): Promise<CompileResponse> {
  const data = await fetchApi<CompileResponse>('/api/compile', {
    method: 'POST',
    body: JSON.stringify(request),
  });

  return {
    ...data,
    result: data.result || '',
    target_agent: data.target_agent || request.target_agent || 'generic',
    knowledge_references: Array.isArray(data.knowledge_references) ? data.knowledge_references : [],
    requirements: data.requirements
      ? {
          ...data.requirements,
          confirmed_requirements: Array.isArray(data.requirements.confirmed_requirements)
            ? data.requirements.confirmed_requirements
            : [],
          missing_information: Array.isArray(data.requirements.missing_information)
            ? data.requirements.missing_information
            : [],
          constraints: Array.isArray(data.requirements.constraints)
            ? data.requirements.constraints
            : [],
          assumptions: Array.isArray(data.requirements.assumptions)
            ? data.requirements.assumptions
            : [],
        }
      : null,
    validation: data.validation
      ? {
          ...data.validation,
          issues: Array.isArray(data.validation.issues) ? data.validation.issues : [],
          preserved_requirements: Array.isArray(data.validation.preserved_requirements)
            ? data.validation.preserved_requirements
            : [],
          missing_requirements: Array.isArray(data.validation.missing_requirements)
            ? data.validation.missing_requirements
            : [],
          violated_constraints: Array.isArray(data.validation.violated_constraints)
            ? data.validation.violated_constraints
            : [],
          invented_requirements: Array.isArray(data.validation.invented_requirements)
            ? data.validation.invented_requirements
            : [],
        }
      : null,
  };
}
