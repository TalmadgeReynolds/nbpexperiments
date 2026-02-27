import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { getExperiment, getAssets, createCondition, updateCondition, deleteCondition, launchRuns, permuteUploadOrders } from '../api/client';
import type { Asset, Experiment, ConditionCreate, Run } from '../types';
import HypothesisAdvisor from '../components/HypothesisAdvisor';
import ConditionRefBuilder from '../components/ConditionRefBuilder';

const NBP_PROMPT_TEMPLATE =
  'A photorealistic [shot type] of [subject], [action or expression], ' +
  'set in [environment]. The scene is illuminated by [lighting description], ' +
  'creating a [mood] atmosphere. Captured with [camera/lens details], ' +
  'emphasizing [key textures and details].';

export default function ExperimentDetailPage() {
  const { id } = useParams<{ id: string }>();
  const [experiment, setExperiment] = useState<Experiment | null>(null);
  const [assets, setAssets] = useState<Asset[]>([]);
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
  const [refImageIds, setRefImageIds] = useState<number[]>([]);

  // Track which condition is being edited (full edit: name + prompt + refs)
  const [editingCondId, setEditingCondId] = useState<number | null>(null);
  const [editName, setEditName] = useState('');
  const [editPrompt, setEditPrompt] = useState('');
  const [editPlan, setEditPlan] = useState<number[]>([]);
  const [saving, setSaving] = useState(false);

  // Upload-order permutation
  const [permuting, setPermuting] = useState(false);
  const [permuteResult, setPermuteResult] = useState<string | null>(null);

  const load = async () => {
    if (!id) return;
    try {
      const [data, assetList] = await Promise.all([
        getExperiment(Number(id)),
        getAssets(),
      ]);
      setExperiment(data);
      setAssets(assetList);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, [id]);

  const handleAddCondition = async () => {
    if (!id || !condForm.name.trim() || !condForm.prompt.trim()) return;
    const uploadPlan = refImageIds.length > 0 ? refImageIds : null;
    try {
      await createCondition(Number(id), { ...condForm, upload_plan: uploadPlan });
      setCondForm({ name: '', prompt: '', upload_plan: null });
      setRefImageIds([]);
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

  const handlePermuteOrders = async () => {
    if (!id) return;
    setPermuting(true);
    setPermuteResult(null);
    try {
      const resp = await permuteUploadOrders(Number(id));
      setPermuteResult(
        resp.created_count > 0
          ? `✓ Created ${resp.created_count} order-permutation condition${resp.created_count !== 1 ? 's' : ''}`
          : 'No new permutations generated (conditions may lack ref images or have < 2 refs).'
      );
      load();
    } catch (e) {
      setPermuteResult(`Error: ${String(e)}`);
    } finally {
      setPermuting(false);
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

      {/* ── Hypothesis Advisor ──────────────────────────────────── */}
      {experiment.hypothesis && (
        <div className="mt-1">
          <HypothesisAdvisor
            experimentId={experiment.id}
            hypothesis={experiment.hypothesis}
            onConditionsAdded={load}
          />
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
            <div className="flex justify-between items-center" style={{ marginBottom: 4 }}>
              <label style={{ margin: 0 }}>Prompt</label>
              {!condForm.prompt && (
                <button
                  type="button"
                  className="secondary"
                  style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                  onClick={() => setCondForm({ ...condForm, prompt: NBP_PROMPT_TEMPLATE })}
                >
                  📋 Use template
                </button>
              )}
            </div>
            <textarea
              rows={3}
              value={condForm.prompt}
              onChange={(e) => setCondForm({ ...condForm, prompt: e.target.value })}
              placeholder={NBP_PROMPT_TEMPLATE}
            />
          </div>
          <div className="form-row">
            <label>Reference Images (upload order)</label>
            <ConditionRefBuilder value={refImageIds} onChange={setRefImageIds} assets={assets} />
          </div>
          <button onClick={handleAddCondition}>Add Condition</button>
        </div>
      )}

      {experiment.conditions.length === 0 ? (
        <p className="text-muted text-sm">No conditions yet.</p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          {experiment.conditions.map((c) => {
            const isEditing = editingCondId === c.id;

            const startEditing = () => {
              setEditingCondId(c.id);
              setEditName(c.name);
              setEditPrompt(c.prompt);
              setEditPlan(c.upload_plan ?? []);
            };

            const cancelEditing = () => {
              setEditingCondId(null);
              setEditName('');
              setEditPrompt('');
              setEditPlan([]);
            };

            const saveCondition = async () => {
              setSaving(true);
              try {
                await updateCondition(c.id, {
                  name: editName !== c.name ? editName : undefined,
                  prompt: editPrompt !== c.prompt ? editPrompt : undefined,
                  upload_plan: editPlan.length > 0 ? editPlan : [],
                });
                setEditingCondId(null);
                setEditName('');
                setEditPrompt('');
                setEditPlan([]);
                load();
              } catch (e) {
                alert(String(e));
              } finally {
                setSaving(false);
              }
            };

            return (
              <div key={c.id} className="card" style={{ padding: 12 }}>
                {isEditing ? (
                  /* ── Full Edit Mode ────────────────────────── */
                  <>
                    <div style={{ marginBottom: 8 }}>
                      <span className="mono text-muted" style={{ fontSize: '0.75rem' }}>#{c.id}</span>
                      <span className="text-sm text-muted" style={{ marginLeft: 8 }}>Editing condition</span>
                    </div>
                    <div className="form-row" style={{ marginBottom: 8 }}>
                      <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Name</label>
                      <input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        placeholder="Condition name"
                      />
                    </div>
                    <div className="form-row" style={{ marginBottom: 8 }}>
                      <div className="flex justify-between items-center" style={{ marginBottom: 4 }}>
                        <label style={{ fontSize: '0.82rem', fontWeight: 600, margin: 0 }}>Prompt</label>
                        <button
                          type="button"
                          className="secondary"
                          style={{ fontSize: '0.68rem', padding: '1px 6px' }}
                          onClick={() => setEditPrompt(NBP_PROMPT_TEMPLATE)}
                        >
                          📋 Reset to template
                        </button>
                      </div>
                      <textarea
                        rows={3}
                        value={editPrompt}
                        onChange={(e) => setEditPrompt(e.target.value)}
                        placeholder={NBP_PROMPT_TEMPLATE}
                        style={{ width: '100%' }}
                      />
                    </div>
                    <div className="form-row" style={{ marginBottom: 8 }}>
                      <label style={{ fontSize: '0.82rem', fontWeight: 600 }}>Reference Images</label>
                      <ConditionRefBuilder
                        value={editPlan}
                        onChange={setEditPlan}
                        assets={assets}
                      />
                    </div>
                    <div className="flex gap-1">
                      <button
                        style={{ fontSize: '0.82rem', padding: '4px 12px' }}
                        onClick={saveCondition}
                        disabled={saving || !editName.trim() || !editPrompt.trim()}
                      >
                        {saving ? 'Saving…' : '💾 Save'}
                      </button>
                      <button
                        className="secondary"
                        style={{ fontSize: '0.82rem', padding: '4px 12px' }}
                        onClick={cancelEditing}
                      >
                        Cancel
                      </button>
                    </div>
                  </>
                ) : (
                  /* ── Read Mode ─────────────────────────────── */
                  <>
                    <div className="flex justify-between items-center" style={{ marginBottom: 6 }}>
                      <div>
                        <span className="mono text-muted" style={{ fontSize: '0.75rem' }}>#{c.id}</span>
                        <strong style={{ marginLeft: 8, fontSize: '0.9rem' }}>{c.name}</strong>
                      </div>
                      <div className="flex items-center gap-1">
                        <span className="text-sm text-muted">
                          {c.upload_plan ? `${c.upload_plan.length} refs` : 'No refs'}
                        </span>
                        <button
                          className="secondary"
                          style={{ fontSize: '0.72rem', padding: '2px 8px' }}
                          onClick={startEditing}
                        >
                          ✏️ Edit
                        </button>
                        <button
                          className="secondary"
                          style={{ fontSize: '0.72rem', padding: '2px 8px', color: 'var(--danger, #ef4444)' }}
                          onClick={async () => {
                            if (!confirm(`Delete condition "${c.name}"?`)) return;
                            try {
                              await deleteCondition(c.id);
                              load();
                            } catch (e) {
                              alert(String(e));
                            }
                          }}
                        >
                          🗑️
                        </button>
                      </div>
                    </div>
                    <p className="text-sm" style={{
                      color: 'var(--text)',
                      marginBottom: 8,
                      lineHeight: 1.4,
                      whiteSpace: 'pre-wrap',
                    }}>
                      {c.prompt}
                    </p>

                    {c.upload_plan && c.upload_plan.length > 0 ? (
                      <ConditionRefBuilder
                        value={c.upload_plan}
                        onChange={() => {}}
                        readOnly
                        assets={assets}
                      />
                    ) : (
                      <button
                        className="secondary"
                        style={{ fontSize: '0.78rem', padding: '4px 10px', marginTop: 4 }}
                        onClick={startEditing}
                      >
                        + Assign reference images
                      </button>
                    )}
                  </>
                )}
              </div>
            );
          })}
        </div>
      )}

      {/* ── Permute Upload Orders (toggleable post-step) ─────── */}
      {experiment.conditions.length > 0 && (
        <div className="card mt-2" style={{ borderLeft: '3px solid var(--warning, #f59e0b)' }}>
          <div className="flex justify-between items-center">
            <div>
              <h3 style={{ margin: 0, fontSize: '0.95rem' }}>🔀 Upload-Order Permutations</h3>
              <p className="text-sm text-muted" style={{ marginTop: 4 }}>
                Generate conditions with the same prompts but different reference image upload orders.
                Useful for testing whether image ordering affects generation results.
              </p>
            </div>
            <button
              onClick={handlePermuteOrders}
              disabled={permuting}
              className="secondary"
            >
              {permuting ? 'Generating…' : '🔀 Permute Orders'}
            </button>
          </div>
          {permuteResult && (
            <p className={`text-sm mt-1 ${permuteResult.startsWith('✓') ? 'text-success' : permuteResult.startsWith('Error') ? 'text-danger' : 'text-muted'}`}>
              {permuteResult}
            </p>
          )}
        </div>
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
