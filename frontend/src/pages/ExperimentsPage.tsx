import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { getExperiments, createExperiment } from '../api/client';
import type { Experiment, ExperimentCreate } from '../types';

export default function ExperimentsPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [loading, setLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);

  const [form, setForm] = useState<ExperimentCreate>({
    name: '',
    hypothesis: '',
    telemetry_enabled: false,
    model_name: 'nano-banana-pro',
  });

  const load = async () => {
    try {
      const data = await getExperiments();
      setExperiments(data);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleCreate = async () => {
    if (!form.name.trim()) return;
    try {
      await createExperiment(form);
      setForm({ name: '', hypothesis: '', telemetry_enabled: false, model_name: 'nano-banana-pro' });
      setShowForm(false);
      load();
    } catch (e) {
      alert(String(e));
    }
  };

  return (
    <>
      <div className="flex justify-between items-center mb-1">
        <h1>Experiments</h1>
        <button onClick={() => setShowForm(!showForm)}>
          {showForm ? 'Cancel' : '+ New Experiment'}
        </button>
      </div>

      {showForm && (
        <div className="card">
          <h2>Create Experiment</h2>
          <div className="form-row">
            <label>Name</label>
            <input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="e.g. Identity Preservation Test"
            />
          </div>
          <div className="form-row">
            <label>Hypothesis</label>
            <textarea
              rows={2}
              value={form.hypothesis ?? ''}
              onChange={(e) => setForm({ ...form, hypothesis: e.target.value })}
              placeholder="Optional hypothesis..."
            />
          </div>
          <div className="form-row">
            <label>Model</label>
            <input
              value={form.model_name ?? 'nano-banana-pro'}
              onChange={(e) => setForm({ ...form, model_name: e.target.value })}
            />
          </div>
          <div className="form-row flex items-center gap-1">
            <input
              type="checkbox"
              id="telemetry"
              checked={form.telemetry_enabled ?? false}
              onChange={(e) => setForm({ ...form, telemetry_enabled: e.target.checked })}
              style={{ width: 'auto' }}
            />
            <label htmlFor="telemetry" style={{ marginBottom: 0 }}>
              Enable Telemetry
            </label>
          </div>
          <button onClick={handleCreate}>Create</button>
        </div>
      )}

      {loading ? (
        <p className="text-muted">Loading…</p>
      ) : experiments.length === 0 ? (
        <p className="text-muted mt-2">No experiments yet. Create one to get started.</p>
      ) : (
        <table className="mt-2">
          <thead>
            <tr>
              <th>ID</th>
              <th>Name</th>
              <th>Model</th>
              <th>Telemetry</th>
              <th>Conditions</th>
              <th>Created</th>
            </tr>
          </thead>
          <tbody>
            {experiments.map((exp) => (
              <tr key={exp.id}>
                <td className="mono">{exp.id}</td>
                <td>
                  <Link to={`/experiments/${exp.id}`}>{exp.name}</Link>
                </td>
                <td className="text-sm text-muted">{exp.model_name}</td>
                <td>
                  <span className={exp.telemetry_enabled ? 'text-success' : 'text-muted'}>
                    {exp.telemetry_enabled ? 'ON' : 'OFF'}
                  </span>
                </td>
                <td>{exp.conditions.length}</td>
                <td className="text-sm text-muted">
                  {new Date(exp.created_at).toLocaleDateString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </>
  );
}
