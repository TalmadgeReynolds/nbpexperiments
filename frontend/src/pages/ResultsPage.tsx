import { useState } from 'react';
import { getRun, getScore, createScore } from '../api/client';
import type { Run, Score, ScoreCreate } from '../types';

interface RunWithScore {
  run: Run;
  score: Score | null;
}

const emptyScore = (): ScoreCreate => ({
  identity_score: 5,
  object_score: 5,
  style_score: 5,
  environment_score: 5,
  hallucination: false,
  notes: '',
});

export default function ResultsPage() {
  const [runIdsStr, setRunIdsStr] = useState('');
  const [items, setItems] = useState<RunWithScore[]>([]);
  const [loading, setLoading] = useState(false);
  const [scoreForms, setScoreForms] = useState<Record<number, ScoreCreate>>({});

  const load = async () => {
    const ids = runIdsStr
      .split(',')
      .map((s) => Number(s.trim()))
      .filter(Boolean);
    if (!ids.length) return;
    setLoading(true);
    try {
      const results: RunWithScore[] = [];
      for (const id of ids) {
        try {
          const run = await getRun(id);
          const score = await getScore(id);
          results.push({ run, score });
        } catch {
          /* skip missing run */
        }
      }
      setItems(results);

      // Init score forms for unscored runs
      const forms: Record<number, ScoreCreate> = {};
      for (const item of results) {
        if (!item.score) {
          forms[item.run.id] = emptyScore();
        }
      }
      setScoreForms(forms);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmitScore = async (runId: number) => {
    const form = scoreForms[runId];
    if (!form) return;
    try {
      await createScore(runId, form);
      load();
    } catch (e) {
      alert(String(e));
    }
  };

  const updateForm = (runId: number, patch: Partial<ScoreCreate>) => {
    setScoreForms((prev) => ({
      ...prev,
      [runId]: { ...prev[runId], ...patch },
    }));
  };

  return (
    <>
      <h1>Results &amp; Scoring</h1>

      <div className="card mt-2">
        <div className="form-row">
          <label>Run IDs (comma-separated)</label>
          <input
            value={runIdsStr}
            onChange={(e) => setRunIdsStr(e.target.value)}
            placeholder="e.g. 1,2,3"
          />
        </div>
        <button onClick={load} disabled={loading}>
          {loading ? 'Loading…' : 'Load Runs'}
        </button>
      </div>

      {items.length > 0 && (
        <div className="run-grid mt-2">
          {items.map(({ run, score }) => (
            <div key={run.id} className="card">
              <div className="flex justify-between items-center mb-1">
                <span className="mono text-sm">Run #{run.id}</span>
                <span className={`badge ${run.status}`}>{run.status}</span>
              </div>

              <p className="text-sm text-muted mb-1">
                Condition {run.condition_id} · Repeat {run.repeat_index}
                {run.latency_ms != null && ` · ${run.latency_ms}ms`}
              </p>

              {/* Output image */}
              {run.output_image_path ? (
                <img
                  src={`/${run.output_image_path}`}
                  alt={`Run ${run.id} output`}
                  style={{
                    width: '100%',
                    borderRadius: 6,
                    marginBottom: '0.75rem',
                    display: 'block',
                  }}
                />
              ) : (
                <div
                  style={{
                    background: 'var(--bg)',
                    borderRadius: 6,
                    padding: '2rem',
                    textAlign: 'center',
                    marginBottom: '0.75rem',
                  }}
                >
                  <span className="text-sm text-muted">No output image</span>
                </div>
              )}

              {/* Score display or form */}
              {score ? (
                <div className="text-sm">
                  <p>
                    <strong>Scores:</strong> Id={score.identity_score} Obj={score.object_score}{' '}
                    Sty={score.style_score} Env={score.environment_score}
                  </p>
                  <p>
                    Hallucination:{' '}
                    <span className={score.hallucination ? 'text-danger' : 'text-success'}>
                      {score.hallucination ? 'YES' : 'No'}
                    </span>
                  </p>
                  {score.notes && <p className="text-muted mt-1">{score.notes}</p>}
                </div>
              ) : scoreForms[run.id] ? (
                <div>
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.5rem' }}>
                    {(['identity_score', 'object_score', 'style_score', 'environment_score'] as const).map(
                      (field) => (
                        <div key={field} className="form-row">
                          <label>{field.replace('_score', '').replace(/^\w/, (c) => c.toUpperCase())} (1–10)</label>
                          <input
                            type="number"
                            min={1}
                            max={10}
                            value={scoreForms[run.id][field]}
                            onChange={(e) => updateForm(run.id, { [field]: Number(e.target.value) })}
                          />
                        </div>
                      ),
                    )}
                  </div>
                  <div className="form-row flex items-center gap-1">
                    <input
                      type="checkbox"
                      id={`halluc-${run.id}`}
                      checked={scoreForms[run.id].hallucination ?? false}
                      onChange={(e) => updateForm(run.id, { hallucination: e.target.checked })}
                      style={{ width: 'auto' }}
                    />
                    <label htmlFor={`halluc-${run.id}`} style={{ marginBottom: 0 }}>
                      Hallucination
                    </label>
                  </div>
                  <div className="form-row">
                    <label>Notes</label>
                    <textarea
                      rows={2}
                      value={scoreForms[run.id].notes ?? ''}
                      onChange={(e) => updateForm(run.id, { notes: e.target.value })}
                    />
                  </div>
                  <button onClick={() => handleSubmitScore(run.id)}>Submit Score</button>
                </div>
              ) : null}

              {/* Telemetry panel */}
              {run.telemetry && (
                <details className="mt-1">
                  <summary className="text-sm text-muted" style={{ cursor: 'pointer' }}>
                    Telemetry
                  </summary>
                  <div className="text-sm mt-1">
                    <p>Thinking: {run.telemetry.thinking_level ?? '—'}</p>
                    <p>Signature: {run.telemetry.thought_signature ?? '—'}</p>
                    <p>Latency: {run.telemetry.latency_ms ?? '—'}ms</p>
                    <p>Allocation: {run.telemetry.allocation_parse_status ?? '—'}</p>
                    {run.telemetry.thought_summary_raw && (
                      <details className="mt-1">
                        <summary className="text-muted" style={{ cursor: 'pointer' }}>
                          Thought Summary
                        </summary>
                        <pre className="mono text-sm" style={{ whiteSpace: 'pre-wrap', marginTop: '0.5rem' }}>
                          {run.telemetry.thought_summary_raw}
                        </pre>
                      </details>
                    )}
                  </div>
                </details>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}
