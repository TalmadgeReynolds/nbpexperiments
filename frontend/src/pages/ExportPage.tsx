import { useEffect, useState } from 'react';
import { getExperiments, exportExperiment } from '../api/client';
import type { Experiment, ExportResult } from '../types';

export default function ExportPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [result, setResult] = useState<ExportResult | null>(null);
  const [exporting, setExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getExperiments().then(setExperiments).catch(console.error);
  }, []);

  const handleExport = async () => {
    if (!selectedId) return;
    setExporting(true);
    setError(null);
    setResult(null);
    try {
      const res = await exportExperiment(selectedId);
      setResult(res);
    } catch (e) {
      setError(String(e));
    } finally {
      setExporting(false);
    }
  };

  const selected = experiments.find((e) => e.id === selectedId);

  return (
    <>
      <h1>Export</h1>

      <div className="card mt-2">
        <div className="form-row">
          <label>Experiment</label>
          <select
            value={selectedId ?? ''}
            onChange={(e) => {
              setSelectedId(e.target.value ? Number(e.target.value) : null);
              setResult(null);
              setError(null);
            }}
          >
            <option value="">— select —</option>
            {experiments.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name} (#{exp.id})
              </option>
            ))}
          </select>
        </div>

        {selected && (
          <div className="text-sm text-muted mb-1">
            Model: {selected.model_name} · Conditions: {selected.conditions.length} · Telemetry:{' '}
            <span className={selected.telemetry_enabled ? 'text-success' : 'text-muted'}>
              {selected.telemetry_enabled ? 'ON' : 'OFF'}
            </span>
          </div>
        )}

        <button onClick={handleExport} disabled={!selectedId || exporting}>
          {exporting ? 'Generating…' : 'Generate Export Bundle'}
        </button>
      </div>

      {error && (
        <div className="card mt-2" style={{ borderColor: 'var(--danger)' }}>
          <p className="text-danger text-sm">{error}</p>
        </div>
      )}

      {result && (
        <div className="card mt-2" style={{ borderColor: 'var(--success)' }}>
          <h2>✓ Export Complete</h2>
          <table>
            <tbody>
              <tr>
                <td className="text-muted">Bundle Path</td>
                <td className="mono text-sm">{result.bundle_path}</td>
              </tr>
              <tr>
                <td className="text-muted">Total Runs</td>
                <td>{result.run_count}</td>
              </tr>
              <tr>
                <td className="text-muted">Scored Runs</td>
                <td>{result.scored_count}</td>
              </tr>
              <tr>
                <td className="text-muted">Telemetry Included</td>
                <td>
                  <span className={result.telemetry_included ? 'text-success' : 'text-muted'}>
                    {result.telemetry_included ? 'Yes' : 'No'}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
          <p className="text-sm text-muted mt-1">
            Bundle contents: manifest.json, scores.csv, image_grid.png, runs/
            {result.telemetry_included && ', telemetry_appendix.csv, allocation_reports.jsonl'}
          </p>
        </div>
      )}
    </>
  );
}
