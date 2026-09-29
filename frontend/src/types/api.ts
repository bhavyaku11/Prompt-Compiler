/**
 * TypeScript domain schemas for Prompt Compiler API contracts.
 * Matches backend Pydantic models in `backend/app/schemas/`.
 */

export type AgentTarget = 'generic' | 'cursor' | 'claude_code' | 'cline' | 'windsurf';

export interface AgentPreset {
  id: string;
  name: string;
  description: string;
  instruction_style: string;
  sections: string[];
  formatting_rules: string[];
  metadata: Record<string, unknown>;
}

export interface CompileRequest {
  input: string;
  interview_mode?: boolean;
  interview_session_id?: string | null;
  project_id?: string | null;
  target_agent?: string;
  enable_knowledge_retrieval?: boolean;
}

export interface RequirementSummary {
  intent: string;
  task_type: string;
  domain: string;
  confirmed_requirements?: string[] | null;
  missing_information?: string[] | null;
  constraints?: string[] | null;
  assumptions?: string[] | null;
  project_context_summary?: string | null;
}

export interface ValidationIssueSummary {
  category: string;
  severity: 'error' | 'warning' | 'info' | string;
  message: string;
}

export interface ValidationSummary {
  overall_valid: boolean;
  issues?: ValidationIssueSummary[] | null;
  preserved_requirements?: string[] | null;
  missing_requirements?: string[] | null;
  violated_constraints?: string[] | null;
  invented_requirements?: string[] | null;
  missing_information_preserved?: boolean;
  task_type_valid?: boolean;
  structure_valid?: boolean;
}

export interface KnowledgeReference {
  chunk_id: string;
  source_id: string;
  source_name: string;
  source_type: string;
  score: number;
  matched_queries: string[];
}

export interface KnowledgeRetrievalTelemetry {
  attempted: boolean;
  skipped: boolean;
  skip_reason?: string | null;
  raw_count: number;
  filtered_count: number;
  latency_ms: number;
  query_used?: string | null;
  queries_attempted: string[];
  successful_queries: number;
  failed_queries: number;
  results_before_deduplication: number;
  results_after_deduplication: number;
  results_after_threshold: number;
  final_result_count: number;
  sources_represented: string[];
}

export interface CompileResponse {
  input: string;
  result: string;
  task_type?: string | null;
  template_name?: string | null;
  requirements?: RequirementSummary | null;
  validation?: ValidationSummary | null;
  refinement_attempts: number;
  interview_session_id?: string | null;
  project_id?: string | null;
  target_agent: string;
  knowledge_references?: KnowledgeReference[] | null;
  knowledge_telemetry?: KnowledgeRetrievalTelemetry | null;
}

export interface Project {
  project_id: string;
  name: string;
  description: string;
  root_path?: string | null;
  created_at: number;
  updated_at: number;
}

export interface ProjectCreate {
  name: string;
  description?: string;
  root_path?: string | null;
}

export interface ProjectUpdate {
  name?: string;
  description?: string;
  root_path?: string | null;
}

export interface ProjectMemory {
  memory_id: string;
  project_id: string;
  category: string;
  content: string;
  source: string;
  confidence: number;
  status: string;
  created_at: number;
  updated_at: number;
}

export interface ProjectContext {
  project_id: string;
  project_name: string;
  description: string;
  active_memories_count: number;
  memories_by_category: Record<string, ProjectMemory[]>;
  context_string: string;
}

export interface KnowledgeSource {
  source_id: string;
  project_id: string;
  source_type: string;
  source_name: string;
  content_hash: string;
  chunk_count: number;
  created_at: string;
  updated_at: string;
}

export interface InterviewStartRequest {
  input: string;
  project_id?: string | null;
  target_agent?: string;
  enable_knowledge_retrieval?: boolean;
}

export interface InterviewQuestion {
  id: string;
  topic: string;
  question: string;
  options: string[];
  allow_custom: boolean;
}

export interface InterviewAnswer {
  question_id: string;
  answer: string;
}

export interface InterviewAnswerRequest {
  answers: InterviewAnswer[];
}

export interface InterviewSessionResponse {
  session_id: string;
  status: 'in_progress' | 'ready' | 'compiled' | string;
  turn: number;
  questions: InterviewQuestion[];
  current_analysis?: RequirementSummary | null;
  project_id?: string | null;
  target_agent: string;
  enable_knowledge_retrieval: boolean;
}

export interface HealthResponse {
  status: string;
  service: string;
}

export interface OllamaStatus {
  status: 'available' | 'unavailable' | string;
  model: string;
  model_available: boolean;
  details?: string | null;
}

export interface DatabaseStatus {
  status: 'ready' | 'error' | string;
  details?: string | null;
}

export interface RuntimeInfo {
  mode: 'development' | 'desktop' | string;
  app_name: string;
  version: string;
  host: string;
  port: number;
  data_dir?: string | null;
}

export interface RuntimeStatusResponse {
  backend: string;
  database: DatabaseStatus;
  ollama: OllamaStatus;
  runtime: RuntimeInfo;
}

export interface ApiErrorResponse {
  detail: string | Array<{ loc: (string | number)[]; msg: string; type: string }>;
}

export interface DocumentIngestionResult {
  path: string;
  relative_path: string;
  source_type?: string | null;
  status: 'indexed' | 'unchanged' | 'skipped' | 'failed' | string;
  source_id?: string | null;
  chunk_count: number;
  content_hash?: string | null;
  error?: string | null;
}

export interface BatchDocumentIngestionResponse {
  project_id: string;
  total: number;
  indexed: number;
  unchanged: number;
  skipped: number;
  failed: number;
  results: DocumentIngestionResult[];
}

export interface IngestDirectoryRequest {
  directory_path?: string | null;
  project_root?: string | null;
  recursive?: boolean;
}

export interface CompilationHistoryItem {
  id: string;
  prompt: string;
  compiledPrompt: string;
  targetAgent: string;
  timestamp: string;
  dateStr?: string;
  projectId?: string | null;
  result?: CompileResponse;
}


