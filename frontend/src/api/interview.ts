/**
 * Prompt Clarification Interview API endpoints.
 */

import { fetchApi } from './client';
import type {
  InterviewStartRequest,
  InterviewAnswerRequest,
  InterviewSessionResponse,
  CompileResponse,
} from '@/types/api';

/**
 * Start an interview clarification session via POST /api/interview/start.
 */
export async function startInterview(request: InterviewStartRequest): Promise<InterviewSessionResponse> {
  return fetchApi<InterviewSessionResponse>('/api/interview/start', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Submit answers to clarification questions via POST /api/interview/{sessionId}/answer.
 */
export async function submitInterviewAnswers(
  sessionId: string,
  request: InterviewAnswerRequest
): Promise<InterviewSessionResponse> {
  return fetchApi<InterviewSessionResponse>(`/api/interview/${sessionId}/answer`, {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

/**
 * Compile final prompt from clarified interview requirements via POST /api/interview/{sessionId}/compile.
 */
export async function compileFromInterview(sessionId: string): Promise<CompileResponse> {
  return fetchApi<CompileResponse>(`/api/interview/${sessionId}/compile`, {
    method: 'POST',
  });
}

/**
 * Get interview session details via GET /api/interview/{sessionId}.
 */
export async function getInterviewSession(sessionId: string): Promise<InterviewSessionResponse> {
  return fetchApi<InterviewSessionResponse>(`/api/interview/${sessionId}`, {
    method: 'GET',
  });
}
