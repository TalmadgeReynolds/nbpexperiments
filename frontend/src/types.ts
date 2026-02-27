/* -- Domain types matching backend Pydantic schemas -- */

// -- AI Provider ----------------------------------------------------

export type AIProvider = 'gemini' | 'claude';

// -- Experiments ----------------------------------------------------

export interface Experiment {
  id: number;
  name: string;
  hypothesis: string | null;
  telemetry_enabled: boolean;
  model_name: string;
  render_settings: Record<string, unknown> | null;
  created_at: string;
  conditions: Condition[];
}

export interface ExperimentCreate {
  name: string;
  hypothesis?: string | null;
  telemetry_enabled?: boolean;
  model_name?: string;
  render_settings?: Record<string, unknown> | null;
}

// -- Reference Images (no slot targeting -- ordered list only) ------

export type RefCategory = 'character' | 'object' | 'world';

export interface RefRecommendation {
  asset_id: number;
  role_guess: string;
  likely_category: RefCategory;
  confidence: number;
  position: number;
  note: string | null;
}

// -- Conditions -----------------------------------------------------

export interface Condition {
  id: number;
  experiment_id: number;
  name: string;
  prompt: string;
  upload_plan: number[] | null;
  created_at: string;
}

export interface ConditionCreate {
  name: string;
  prompt: string;
  upload_plan?: number[] | null;
}

export interface ConditionUpdate {
  name?: string;
  prompt?: string;
  upload_plan?: number[] | null;
}

// -- Assets ---------------------------------------------------------

export interface AssetQC {
  id: number;
  asset_id: number;
  role_guess: string;
  role_confidence: number;
  ambiguity_score: number;
  quality_json: Record<string, unknown> | null;
  face_json: Record<string, unknown> | null;
  environment_json: Record<string, unknown> | null;
  lighting_json: Record<string, unknown> | null;
  style_json: Record<string, unknown> | null;
}

export interface Asset {
  id: number;
  file_path: string;
  hash: string;
  uploaded_at: string;
  qc: AssetQC | null;
}

// -- Runs -----------------------------------------------------------

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed';

export interface RunTelemetry {
  id: number;
  run_id: number;
  thought_summary_raw: string | null;
  thought_signature: string | null;
  usage_metadata_json: Record<string, unknown> | null;
  safety_metadata_json: unknown;
  thinking_level: string | null;
  latency_ms: number | null;
  allocation_report_json: Record<string, unknown> | null;
  allocation_parse_status: string | null;
}

export interface Run {
  id: number;
  condition_id: number;
  repeat_index: number;
  status: RunStatus;
  output_image_path: string | null;
  latency_ms: number | null;
  created_at: string;
  telemetry: RunTelemetry | null;
}

// -- Scores ---------------------------------------------------------

export interface Score {
  id: number;
  run_id: number;
  identity_score: number;
  object_score: number;
  style_score: number;
  environment_score: number;
  hallucination: boolean;
  notes: string | null;
  created_at: string;
}

export interface ScoreCreate {
  identity_score: number;
  object_score: number;
  style_score: number;
  environment_score: number;
  hallucination?: boolean;
  notes?: string | null;
}

// -- Export ----------------------------------------------------------

export interface ExportResult {
  bundle_path: string;
  run_count: number;
  scored_count: number;
  telemetry_included: boolean;
}

// -- Hypothesis Advisor ---------------------------------------------

export interface AdvisorQuestion {
  id: string;
  question: string;
  why: string | null;
  options: string[] | null;
}

export interface AdvisorQuestionsResponse {
  experiment_id: number;
  hypothesis: string;
  questions: AdvisorQuestion[];
}

export interface QuestionAnswer {
  question: string;
  answer: string;
}

export interface SuggestedCondition {
  name: string;
  prompt: string;
  rationale: string | null;
  upload_plan: number[] | null;
  ref_strategy: string | null;
}

export interface AdvisorSuggestResponse {
  experiment_id: number;
  conditions: SuggestedCondition[];
}

// -- Upload-Order Permutations --------------------------------------

export interface PermuteOrdersResponse {
  experiment_id: number;
  created_count: number;
  conditions: SuggestedCondition[];
}
