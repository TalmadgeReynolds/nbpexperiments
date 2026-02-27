import { useEffect, useState, useRef } from 'react';
import { getAssets, uploadAsset, analyzeAsset } from '../api/client';
import type { Asset } from '../types';

export default function AssetsPage() {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [analyzingId, setAnalyzingId] = useState<number | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      setAssets(await getAssets());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  const handleUpload = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await uploadAsset(file);
      if (fileRef.current) fileRef.current.value = '';
      load();
    } catch (e) {
      alert(String(e));
    } finally {
      setUploading(false);
    }
  };

  const handleAnalyze = async (id: number) => {
    setAnalyzingId(id);
    try {
      await analyzeAsset(id);
      load();
    } catch (e) {
      alert(String(e));
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <>
      <h1>Assets &amp; Reference QC</h1>

      {/* Upload */}
      <div className="card mt-2">
        <h2>Upload Asset</h2>
        <div className="flex items-center gap-1">
          <input type="file" ref={fileRef} accept="image/*" style={{ flex: 1 }} />
          <button onClick={handleUpload} disabled={uploading}>
            {uploading ? 'Uploading…' : 'Upload'}
          </button>
        </div>
      </div>

      {/* Asset list */}
      {loading ? (
        <p className="text-muted mt-2">Loading…</p>
      ) : assets.length === 0 ? (
        <p className="text-muted mt-2">No assets uploaded yet.</p>
      ) : (
        <table className="mt-2">
          <thead>
            <tr>
              <th>ID</th>
              <th>File</th>
              <th>Hash</th>
              <th>QC Status</th>
              <th>Role Guess</th>
              <th>Confidence</th>
              <th>Ambiguity</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {assets.map((a) => (
              <tr key={a.id}>
                <td className="mono">{a.id}</td>
                <td className="text-sm" style={{ maxWidth: 200, overflow: 'hidden', textOverflow: 'ellipsis' }}>
                  {a.file_path.split('/').pop()}
                </td>
                <td className="mono text-sm">{a.hash.slice(0, 12)}…</td>
                <td>
                  {a.qc ? (
                    <span className="text-success text-sm">Analyzed</span>
                  ) : (
                    <span className="text-warning text-sm">Pending</span>
                  )}
                </td>
                <td className="text-sm">{a.qc?.role_guess ?? '—'}</td>
                <td className="mono text-sm">
                  {a.qc ? `${(a.qc.role_confidence * 100).toFixed(0)}%` : '—'}
                </td>
                <td className="mono text-sm">
                  {a.qc ? a.qc.ambiguity_score.toFixed(2) : '—'}
                </td>
                <td>
                  {!a.qc && (
                    <button
                      className="secondary"
                      onClick={() => handleAnalyze(a.id)}
                      disabled={analyzingId === a.id}
                    >
                      {analyzingId === a.id ? 'Analyzing…' : 'Analyze'}
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {/* QC detail panels */}
      {assets.filter((a) => a.qc).length > 0 && (
        <div className="mt-2">
          <h2 className="mb-1">QC Details</h2>
          {assets
            .filter((a) => a.qc)
            .map((a) => (
              <div key={a.id} className="card">
                <h2>
                  Asset #{a.id} — {a.qc!.role_guess}
                  {a.qc!.ambiguity_score > 0.5 && (
                    <span className="text-warning text-sm"> ⚠ High ambiguity</span>
                  )}
                </h2>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.75rem' }}>
                  {a.qc!.quality_json && (
                    <div>
                      <label>Quality</label>
                      <pre className="text-sm mono" style={{ whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(a.qc!.quality_json, null, 2)}
                      </pre>
                    </div>
                  )}
                  {a.qc!.face_json && (
                    <div>
                      <label>Face</label>
                      <pre className="text-sm mono" style={{ whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(a.qc!.face_json, null, 2)}
                      </pre>
                    </div>
                  )}
                  {a.qc!.environment_json && (
                    <div>
                      <label>Environment</label>
                      <pre className="text-sm mono" style={{ whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(a.qc!.environment_json, null, 2)}
                      </pre>
                    </div>
                  )}
                  {a.qc!.lighting_json && (
                    <div>
                      <label>Lighting</label>
                      <pre className="text-sm mono" style={{ whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(a.qc!.lighting_json, null, 2)}
                      </pre>
                    </div>
                  )}
                  {a.qc!.style_json && (
                    <div>
                      <label>Style</label>
                      <pre className="text-sm mono" style={{ whiteSpace: 'pre-wrap' }}>
                        {JSON.stringify(a.qc!.style_json, null, 2)}
                      </pre>
                    </div>
                  )}
                </div>
              </div>
            ))}
        </div>
      )}
    </>
  );
}
