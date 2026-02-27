import { useEffect, useState, useCallback } from 'react';
import { getExperiments, getRun } from '../api/client';
import type { Experiment, Run } from '../types';

export default function RunMonitorPage() {
  const [experiments, setExperiments] = useState<Experiment[]>([]);
  const [selectedExpId, setSelectedExpId] = useState<number | null>(null);
  const [runs, setRuns] = useState<Run[]>([]);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    getExperiments().then(setExperiments).catch(console.error);
  }, []);

  // After selecting an experiment, we need the run IDs.
  // The backend doesn't have a "list runs for experiment" endpoint yet,
  // so we launch runs from ExperimentDetailPage and monitor by run IDs.
  // For now, use a simple input to specify run IDs to monitor.
  const [runIdsStr, setRunIdsStr] = useState('');

  const loadRuns = useCallback(async () => {
    const ids = runIdsStr
      .split(',')
      .map((s) => Number(s.trim()))
      .filter(Boolean);
    if (ids.length === 0) return;

    try {
      const results = await Promise.all(ids.map((id) => getRun(id).catch(() => null)));
      setRuns(results.filter((r): r is Run => r !== null));
    } catch (e) {
      console.error(e);
    }
  }, [runIdsStr]);

  // Poll every 3s when enabled
  useEffect(() => {
    if (!polling) return;
    const interval = setInterval(loadRuns, 3000);
    return () => clearInterval(interval);
  }, [polling, loadRuns]);

  const experiment = experiments.find((e) => e.id === selectedExpId);

  return (
    <>
      <h1>Run Monitor</h1>

      <div className="card mt-2">
        <div className="form-row">
          <label>Experiment</label>
          <select
            value={selectedExpId ?? ''}
            onChange={(e) => setSelectedExpId(e.target.value ? Number(e.target.value) : null)}
          >
            <option value="">— select —</option>
            {experiments.map((exp) => (
              <option key={exp.id} value={exp.id}>
                {exp.name} (#{exp.id})
              </option>
            ))}
          </select>
        </div>

        <div className="form-row">
          <label>Run IDs to monitor (comma-separated)</label>
          <input
            value={runIdsStr}
            onChange={(e) => setRunIdsStr(e.target.value)}
            placeholder="e.g. 1,2,3,4"
          />
        </div>

        <div className="flex gap-1">
          <button onClick={loadRuns}>Refresh</button>
          <button
            className={polling ? 'danger' : 'secondary'}
            onClick={() => {
              if (!polling) loadRuns();
              setPolling(!polling);
            }}
          >
            {polling ? 'Stop Polling' : 'Start Polling (3s)'}
          </button>
        </div>
      </div>

      {runs.length > 0 && (
        <>
          {/* Summary bar */}
          <div className="flex gap-2 mt-2 mb-1">
            <span className="text-sm">
              Total: {runs.length} ·{' '}
              <span className="text-success">{runs.filter((r) => r.status === 'succeeded').length} succeeded</span> ·{' '}
              <span style={{ color: '#60a5fa' }}>{runs.filter((r) => r.status === 'running').length} running</span> ·{' '}
              <span className="text-muted">{runs.filter((r) => r.status === 'queued').length} queued</span> ·{' '}
              <span className="text-danger">{runs.filter((r) => r.status === 'failed').length} failed</span>
            </span>
          </div>

          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Condition</th>
                <th>Repeat</th>
                <th>Status</th>
                <th>Latency</th>
                {experiment?.telemetry_enabled && <th>Telemetry</th>}
              </tr>
            </thead>
            <tbody>
              {runs.map((r) => (
                <tr key={r.id}>
                  <td className="mono">{r.id}</td>
                  <td>{r.condition_id}</td>
                  <td>{r.repeat_index}</td>
                  <td>
                    <span className={`badge ${r.status}`}>{r.status}</span>
                  </td>
                  <td className="mono text-sm">
                    {r.latency_ms != null ? `${r.latency_ms}ms` : '—'}
                  </td>
                  {experiment?.telemetry_enabled && (
                    <td className="text-sm">
                      {r.telemetry ? (
                        <span className="text-success">
                          {r.telemetry.thinking_level ?? '—'} ·{' '}
                          {r.telemetry.thought_signature ? '🔒' : '🔓'}
                        </span>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </>
  );
}
