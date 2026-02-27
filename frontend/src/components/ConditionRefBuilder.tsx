import { useEffect, useState, useCallback } from 'react';
import { getAssets } from '../api/client';
import type { Asset } from '../types';

/**
 * Visual per-condition reference image builder.
 *
 * Shows a 14-position strip with thumbnails. Users can:
 * - Click an asset from the pool to add it
 * - Drag to reorder within the strip
 * - Click × to remove
 * - Use "Add All" / "Smart Order" shortcuts
 *
 * Category colors are advisory (the model decides allocation).
 */

const BASE = import.meta.env.VITE_API_BASE ?? '/api';

// Advisory category based on UPLOAD POSITION (not enforced by API)
function positionHint(pos: number): { label: string; color: string; bg: string } {
  if (pos < 5) return { label: 'CHAR', color: '#6366f1', bg: '#eef2ff' };
  if (pos < 11) return { label: 'OBJ', color: '#d97706', bg: '#fef9c3' };
  return { label: 'WORLD', color: '#16a34a', bg: '#dcfce7' };
}

interface Props {
  /** Ordered list of asset IDs in this condition's upload plan */
  value: number[];
  /** Called when the plan changes */
  onChange: (plan: number[]) => void;
  /** If true, hide editing controls (for displaying existing conditions) */
  readOnly?: boolean;
  /** Max ref slots (default 14) */
  maxSlots?: number;
  /** Pre-fetched assets — when provided, skips the internal GET /assets call */
  assets?: Asset[];
}

export default function ConditionRefBuilder({
  value,
  onChange,
  readOnly = false,
  maxSlots = 14,
  assets: propAssets,
}: Props) {
  const [fetchedAssets, setFetchedAssets] = useState<Asset[]>([]);
  const [loading, setLoading] = useState(!propAssets);
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const [dragOverIdx, setDragOverIdx] = useState<number | null>(null);

  // Only fetch if parent didn't provide assets
  useEffect(() => {
    if (propAssets) return;
    getAssets()
      .then(setFetchedAssets)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [propAssets]);

  const assets = propAssets ?? fetchedAssets;

  const getAssetById = useCallback(
    (id: number) => assets.find((a) => a.id === id),
    [assets],
  );

  const unusedAssets = assets.filter((a) => !value.includes(a.id));

  // ── Actions ──────────────────────────────────────────────────

  const handleAdd = (assetId: number) => {
    if (readOnly || value.length >= maxSlots) return;
    onChange([...value, assetId]);
  };

  const handleRemove = (index: number) => {
    if (readOnly) return;
    onChange(value.filter((_, i) => i !== index));
  };

  const handleAddAll = () => {
    if (readOnly) return;
    const allIds = assets.map((a) => a.id).slice(0, maxSlots);
    onChange(allIds);
  };

  const handleSmartOrder = () => {
    if (readOnly) return;
    // Group by QC category: characters first, objects, then world
    const chars: number[] = [];
    const objs: number[] = [];
    const worlds: number[] = [];
    const unknown: number[] = [];

    for (const a of assets) {
      const role = a.qc?.role_guess ?? '';
      if (['human_identity', 'composition_pose'].includes(role)) chars.push(a.id);
      else if (['object_fidelity', 'texture_material', 'mixed'].includes(role)) objs.push(a.id);
      else if (['environment_plate', 'style_look'].includes(role)) worlds.push(a.id);
      else unknown.push(a.id);
    }
    onChange([...chars, ...objs, ...worlds, ...unknown].slice(0, maxSlots));
  };

  // ── Drag & Drop ──────────────────────────────────────────────

  const handleDragStart = (idx: number) => {
    if (readOnly) return;
    setDragIdx(idx);
  };

  const handleDragOver = (e: React.DragEvent, idx: number) => {
    e.preventDefault();
    setDragOverIdx(idx);
  };

  const handleDrop = (targetIdx: number) => {
    if (dragIdx === null || dragIdx === targetIdx || readOnly) return;
    const next = [...value];
    const [moved] = next.splice(dragIdx, 1);
    next.splice(targetIdx, 0, moved);
    onChange(next);
    setDragIdx(null);
    setDragOverIdx(null);
  };

  const handleDragEnd = () => {
    setDragIdx(null);
    setDragOverIdx(null);
  };

  // ── Thumbnail helper ──────────────────────────────────────────

  const Thumb = ({ assetId, size = 36 }: { assetId: number; size?: number }) => (
    <img
      src={`${BASE}/assets/${assetId}/file`}
      alt={`#${assetId}`}
      style={{
        width: size,
        height: size,
        objectFit: 'cover',
        borderRadius: 3,
      }}
      onError={(e) => {
        const el = e.target as HTMLImageElement;
        el.style.display = 'none';
      }}
    />
  );

  // ── Render ────────────────────────────────────────────────────

  if (loading) {
    return (
      <div style={{ padding: 12, fontSize: '0.82rem', color: 'var(--muted)' }}>
        Loading assets…
      </div>
    );
  }

  if (assets.length === 0) {
    return (
      <div style={{
        padding: 12,
        fontSize: '0.82rem',
        color: 'var(--muted)',
        background: 'rgba(239,68,68,0.06)',
        borderRadius: 6,
      }}>
        ⚠️ No assets uploaded yet. Go to <strong>Assets & Reference QC</strong> to upload reference images first.
      </div>
    );
  }

  return (
    <div>
      {/* ── Header + Actions ─────────────────────────────── */}
      {!readOnly && (
        <div className="flex justify-between items-center" style={{ marginBottom: 8 }}>
          <div className="text-sm text-muted">
            {value.length}/{maxSlots} positions filled · drag to reorder
          </div>
          <div className="flex gap-1">
            {value.length < assets.length && (
              <button
                className="secondary"
                style={{ fontSize: '0.72rem', padding: '2px 7px' }}
                onClick={handleAddAll}
              >
                📎 All {Math.min(assets.length, maxSlots)}
              </button>
            )}
            <button
              className="secondary"
              style={{ fontSize: '0.72rem', padding: '2px 7px' }}
              onClick={handleSmartOrder}
            >
              ✨ Smart order
            </button>
            {value.length > 0 && (
              <button
                className="secondary"
                style={{ fontSize: '0.72rem', padding: '2px 7px' }}
                onClick={() => onChange([])}
              >
                Clear
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── 14-position visual strip ─────────────────────── */}
      <div style={{
        display: 'flex',
        gap: 4,
        flexWrap: 'wrap',
      }}>
        {Array.from({ length: readOnly ? value.length : maxSlots }, (_, i) => {
          const assetId = value[i];
          const asset = assetId != null ? getAssetById(assetId) : null;
          const hint = positionHint(i);
          const isDragging = dragIdx === i;
          const isDragOver = dragOverIdx === i && dragIdx !== i;

          return (
            <div
              key={i}
              draggable={!readOnly && assetId != null}
              onDragStart={() => handleDragStart(i)}
              onDragOver={(e) => handleDragOver(e, i)}
              onDrop={() => handleDrop(i)}
              onDragEnd={handleDragEnd}
              style={{
                width: readOnly ? 52 : 62,
                height: readOnly ? 64 : 74,
                border: isDragOver
                  ? '2px solid var(--accent)'
                  : assetId != null
                    ? `2px solid ${hint.color}33`
                    : '2px dashed var(--border)',
                borderRadius: 6,
                background: assetId != null ? hint.bg : 'var(--surface)',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                position: 'relative',
                cursor: !readOnly && assetId != null ? 'grab' : 'default',
                opacity: isDragging ? 0.4 : 1,
                transition: 'border-color 0.15s, opacity 0.15s',
              }}
            >
              {/* Position number */}
              <div style={{
                position: 'absolute',
                top: 1,
                left: 3,
                fontSize: '0.6rem',
                fontWeight: 700,
                color: 'var(--muted)',
              }}>
                {i + 1}
              </div>

              {/* Category hint */}
              <div style={{
                position: 'absolute',
                top: 1,
                right: 3,
                fontSize: '0.5rem',
                fontWeight: 700,
                color: hint.color,
                opacity: 0.7,
              }}>
                {hint.label}
              </div>

              {assetId != null ? (
                <>
                  <div style={{ marginTop: 10 }}>
                    <Thumb assetId={assetId} size={readOnly ? 30 : 36} />
                  </div>
                  <div style={{
                    fontSize: '0.6rem',
                    color: 'var(--text)',
                    fontWeight: 600,
                    marginTop: 1,
                  }}>
                    #{assetId}
                  </div>

                  {/* QC role badge */}
                  {asset?.qc?.role_guess && (
                    <div style={{
                      fontSize: '0.45rem',
                      color: hint.color,
                      fontWeight: 600,
                      maxWidth: '100%',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                      padding: '0 2px',
                    }}>
                      {asset.qc.role_guess.replace('_', ' ')}
                    </div>
                  )}

                  {/* Remove button */}
                  {!readOnly && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleRemove(i); }}
                      style={{
                        position: 'absolute',
                        top: -5,
                        right: -5,
                        width: 15,
                        height: 15,
                        borderRadius: '50%',
                        background: 'var(--danger, #ef4444)',
                        color: '#fff',
                        border: 'none',
                        fontSize: '0.6rem',
                        cursor: 'pointer',
                        lineHeight: '15px',
                        padding: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                      }}
                    >
                      ×
                    </button>
                  )}
                </>
              ) : (
                <div style={{ color: 'var(--border)', fontSize: 16 }}>+</div>
              )}
            </div>
          );
        })}
      </div>

      {/* ── Asset pool (click to add) ──────────────────────── */}
      {!readOnly && unusedAssets.length > 0 && value.length < maxSlots && (
        <div style={{ marginTop: 10 }}>
          <div className="text-sm text-muted" style={{ marginBottom: 4, fontSize: '0.72rem' }}>
            Available assets (click to add):
          </div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {unusedAssets.map((a) => (
              <button
                key={a.id}
                onClick={() => handleAdd(a.id)}
                style={{
                  width: 48,
                  height: 56,
                  border: '1px solid var(--border)',
                  borderRadius: 4,
                  cursor: 'pointer',
                  padding: 0,
                  background: 'var(--surface)',
                  display: 'flex',
                  flexDirection: 'column',
                  alignItems: 'center',
                  justifyContent: 'center',
                  gap: 1,
                }}
                title={`#${a.id} ${a.qc?.role_guess ?? 'unanalyzed'}`}
              >
                <Thumb assetId={a.id} size={30} />
                <span style={{ fontSize: '0.6rem', fontWeight: 600 }}>#{a.id}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Legend ────────────────────────────────────────────── */}
      {!readOnly && (
        <div style={{
          display: 'flex',
          gap: 12,
          marginTop: 8,
          fontSize: '0.65rem',
          color: 'var(--muted)',
        }}>
          <span><span style={{ color: '#6366f1' }}>■</span> Pos 1-5: likely character</span>
          <span><span style={{ color: '#d97706' }}>■</span> Pos 6-11: likely object</span>
          <span><span style={{ color: '#16a34a' }}>■</span> Pos 12-14: likely world</span>
          <span style={{ fontStyle: 'italic' }}>(advisory — model decides)</span>
        </div>
      )}
    </div>
  );
}
