import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getExperiment, createCondition, launchRuns } from '../api/client';
import type { Experiment, ConditionCreate, Run } from '../types';

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCondForm, setShowCondForm] = useState(false);
  const [runs, setRuns] = useState<Run[]>([]);
  const [repeatCount, setRepeatCount] = useState(3);
  const [launching, setLaunching] = useState(false);

  const [condForm, setCondForm] = useState<ConditionCreate>({
    name: '',
    prompt: '',
    upload_plan: null,
  });
  const [uploadPlanStr, setUploadPlanStr] = useState('');

  const load = async () => {
    if (!id) return;
    try {
      const data = await getExperiment(Number(id));
      setExperiment(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleAddCondition = async () => {
    if (!id || !condForm.name.trim() || !condForm.prompt.trim()) return;
    const uploadPlan = uploadPlanStr.trim()
      ? uploadPlanStr.split(',').map((s) => Number(s.trim())).filter(Boolean)
      : null;
    try {
      await createCondition(Number(id), { ...condForm, upload_plan: uploadPlan });
      setCondForm({ name: '', prompt: '', upload_plan: null });
      setUploadPlanStr('');
      setShowCondForm(false);
      load();
    } catch (e) {
      alert(String(e));
    }
  };

  const handleLaunchRuns = async () => {
    if (!id) return;
    setLaunching(true);
    try {
      const newRuns = await launchRuns(Number(id), repeatCount);
      setRuns(newRuns);
    } catch (e) {
      alert(String(e));
    } finally {
      setLaunching(false);
    }
  };

  if (loading) return <p className="text-muted">Loading…</p>;
  if (!experiment) return <p className="text-danger">Experiment not found.</p>;

  return (
    <>
      <div className="flex justify-between items-center mb-1">
        <div>
          <h1>{experiment.name}</h1>
          <p className="text-sm text-muted">
            {experiment.model_name} · Telemetry{' '}
            <span className={experiment.telemetry_enabled ? 'text-success' : 'text-muted'}>
              {experiment.telemetry_enabled ? 'ON' : 'OFF'}
            </span>
          </p>
        </div>
      </div>

      {experiment.hypothesis && (
        <div className="card">
          <h2>Hypothesis</h2>
          <p className="text-sm">{experiment.hypothesis}</p>
        </div>
      )}

      {/* ── Conditions ──────────────────────────────────────────── */}
      <div className="flex justify-between items-center mt-2 mb-1">
        <h2>Conditions ({experiment.conditions.length})</h2>
        <button className="secondary" onClick={() => setShowCondForm(!showCondForm)}>
          {showCondForm ? 'Cancel' : '+ Add Condition'}
        </button>
      </div>

      {showCondForm && (
        <div className="card">
          <div className="form-row">
            <label>Name</label>
            <input
              value={condForm.name}
              onChange={(e) => setCondForm({ ...condForm, name: e.target.value })}
              placeholder="e.g. Baseline"
            />
          </div>
          <div className="form-row">
            <label>Prompt</label>
            <textarea
              rows={3}
              value={condForm.prompt}
              onChange={(e) => setCondForm({ ...condForm, prompt: e.target.value })}
              placeholder="Generation prompt for this condition…"
            />
          </div>
          <div className="form-row">
            <label>Upload Plan (comma-separated asset IDs)</label>
            <input
              value={uploadPlanStr}
              onChange={(e) => setUploadPlanStr(e.target.value)}
              placeholder="e.g. 1,2,3"
            />
          </div>
          <button onClick={handleAddCondition}>Add Condition</button>
        </div>
      )}

      {experiment.conditions.length === 0 ? (
        <p className="text-muted text-sm">No conditions yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Prompt</th>
              <th>Upload Plan</th>
            </tr>
          </thead>
          <tbody>
            {experiment.conditions.map((c) => (
              <tr key={c.id}>
                <td className="mono">{c.id}</td>
                <td>{c.name}</td>
                <td className="text-sm" style={{ maxWidth: 300, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {c.prompt}
                </td>
                <td className="mono text-sm">
                  {c.upload_plan ? c.upload_plan.join(', ') : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* ── Launch Runs ─────────────────────────────────────────── */}
      {experiment.conditions.length > 0 && (
        <div className="card mt-2">
          <h2>Launch Runs</h2>
          <div className="flex items-center gap-1">
            <div className="form-row" style={{ width: 120 }}>
              <label>Repeats</label>
              <input
                type="number"
                min={1}
                max={20}
                value={repeatCount}
                onChange={(e) => setRepeatCount(Number(e.target.value))}
              />
            </div>
            <button onClick={handleLaunchRuns} disabled={launching} style={{ alignSelf: 'flex-end' }}>
              {launching ? 'Launching…' : 'Launch'}
            </button>
          </div>

          {runs.length > 0 && (
            <div className="mt-1">
              <p className="text-sm text-success">
                ✓ Created {runs.length} runs
              </p>
              <table className="mt-1">
                <thead>
                  <tr>
                    <th>Run ID</th>
                    <th>Condition</th>
                    <th>Repeat</th>
                    <th>Status</th>
                  </tr>
                </thead>
                <tbody>
                  {runs.map((r) => (
                    <tr key={r.id}>
                      <td className="mono">{r.id}</td>
                      <td>{r.condition_id}</td>
                      <td>{r.repeat_index}</td>
                      <td><span className={`badge ${r.status}`}>{r.status}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </>
  );
}
