/**
 * Thin API client -- all backend calls go through here.
 * Uses the Vite proxy (/api -> localhost:8000) in dev.
 */

import type {
  AdvisorQuestionsResponse,
  AdvisorSuggestResponse,
  AIProvider,
  Asset,
  Condition,
  ConditionCreate,
  ConditionUpdate,
  Experiment,
  ExperimentCreate,
  ExportResult,
  PermuteOrdersResponse,
  QuestionAnswer,
  RefRecommendation,
  Run,
  Score,
  ScoreCreate,
} from '../types';

const BASE = import.meta.env.VITE_API_BASE ?? '/api';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status}: ${body}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

// -- Experiments ----------------------------------------------------

export const getExperiments = () => request<Experiment[]>('/experiments');

export const getExperiment = (id: number) =>
  request<Experiment>(`/experiments/${id}`);

export const createExperiment = (data: ExperimentCreate) =>
  request<Experiment>('/experiments', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

// -- Conditions -----------------------------------------------------

export const createCondition = (experimentId: number, data: ConditionCreate) =>
  request<Condition>(`/experiments/${experimentId}/conditions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

export const updateCondition = (conditionId: number, data: ConditionUpdate) =>
  request<Condition>(`/conditions/${conditionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

export const deleteCondition = (conditionId: number) =>
  request<void>(`/conditions/${conditionId}`, { method: 'DELETE' });

// -- Assets ---------------------------------------------------------

export const getAssets = () => request<Asset[]>('/assets');

export const getAsset = (id: number) => request<Asset>(`/assets/${id}`);

export const uploadAsset = async (file: File): Promise<Asset> => {
  const form = new FormData();
  form.append('file', file);
  return request<Asset>('/assets', { method: 'POST', body: form });
};

export const analyzeAsset = (id: number, provider: AIProvider = 'gemini') =>
  request<Record<string, unknown>>(`/assets/${id}/analyze?provider=${provider}`, { method: 'POST' });

// -- Runs -----------------------------------------------------------

export const launchRuns = (experimentId: number, repeatCount = 3) =>
  request<Run[]>(`/experiments/${experimentId}/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ repeat_count: repeatCount }),
  });

export const getRun = (id: number) => request<Run>(`/runs/${id}`);

// -- Scores ---------------------------------------------------------

export const getScore = (runId: number) =>
  request<Score | null>(`/runs/${runId}/score`);

export const createScore = (runId: number, data: ScoreCreate) =>
  request<Score>(`/runs/${runId}/score`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });

// -- Export ---------------------------------------------------------

export const exportExperiment = (experimentId: number) =>
  request<ExportResult>(`/experiments/${experimentId}/export`, {
    method: 'POST',
  });

// -- Hypothesis Advisor ---------------------------------------------

export const getAdvisorQuestions = (experimentId: number, provider: AIProvider = 'gemini') =>
  request<AdvisorQuestionsResponse>(
    `/experiments/${experimentId}/advisor/questions?provider=${provider}`,
    { method: 'POST' },
  );

export const getAdvisorConditions = (
  experimentId: number,
  answers: QuestionAnswer[],
  provider: AIProvider = 'gemini',
) =>
  request<AdvisorSuggestResponse>(
    `/experiments/${experimentId}/advisor/conditions?provider=${provider}`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ answers }),
    },
  );

export const permuteUploadOrders = (
  experimentId: number,
  strategies?: string[] | null,
) =>
  request<PermuteOrdersResponse>(
    `/experiments/${experimentId}/advisor/permute-orders`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(strategies ? { strategies } : {}),
    },
  );

// -- Reference Images -----------------------------------------------

export const getRefRecommendations = () =>
  request<RefRecommendation[]>('/refs/recommendations');

export const getRefInfo = () =>
  request<Record<string, unknown>>('/refs/info');
