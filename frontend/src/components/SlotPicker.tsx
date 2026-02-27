import { useEffect, useState } from 'react';
import { getAssets, getRefRecommendations } from '../api/client';
import type { Asset, RefRecommendation } from '../types';

/**
 * Reference Image Picker — ordered list of assets to send as references.
 *
 * The Gemini API takes images as a flat ordered list. You CANNOT target
 * specific internal slots. The model decides how to interpret each image
 * based on content and prompt context.
 *
 * Upload ORDER may influence priority — that's the experimental variable.
 */

const CATEGORY_COLORS: Record<string, string> = {
  character: '#6366f1',
  object: '#f59e0b',
  world: '#22c55e',
  unknown: '#94a3b8',
};

interface Props {
  /** Current ordered list of asset IDs */
  value: number[];
  /** Called whenever the list changes */
  onChange: (assetIds: number[]) => void;
  /** Compact mode for inline use */
  compact?: boolean;
}

export default function RefImagePicker({ value, onChange, compact = false }: Props) {
  const [assets, setAssets] = useState<Asset[]>([]);
  const [recommendations, setRecommendations] = useState<RefRecommendation[]>([]);
  const [loadingAssets, setLoadingAssets] = useState(true);

  useEffect(() => {
    (async () => {
      try {
        const [a, r] = await Promise.all([getAssets(), getRefRecommendations()]);
        setAssets(a);
        setRecommendations(r);
      } catch {
        // Assets may not be loaded yet
      } finally {
        setLoadingAssets(false);
      }
    })();
  }, []);

  const getAssetById = (id: number) => assets.find((a) => a.id === id);
  const getRec = (id: number) => recommendations.find((r) => r.asset_id === id);
  const availableAssets = assets.filter((a) => !value.includes(a.id));

  const handleAdd = (assetId: number) => {
    if (value.length >= 14) return;
    onChange([...value, assetId]);
  };

  const handleRemove = (index: number) => {
    onChange(value.filter((_, i) => i !== index));
  };

  const handleMoveUp = (index: number) => {
    if (index === 0) return;
    const next = [...value];
    [next[index - 1], next[index]] = [next[index], next[index - 1]];
    onChange(next);
  };

  const handleMoveDown = (index: number) => {
    if (index === value.length - 1) return;
    const next = [...value];
    [next[index], next[index + 1]] = [next[index + 1], next[index]];
    onChange(next);
  };

  const handleAddAll = () => {
    // Add all available assets (up to 14) in their current order
    const allIds = assets.map((a) => a.id).slice(0, 14);
    onChange(allIds);
  };

  const handleAutoOrder = () => {
    // Use recommendations to suggest a good order; fall back to all assets
    if (recommendations.length > 0) {
      const recOrder = recommendations.map((r) => r.asset_id);
      // Include any assets that aren't in recs at the end
      const recSet = new Set(recOrder);
      const remaining = assets.filter((a) => !recSet.has(a.id)).map((a) => a.id);
      const ordered = [...recOrder, ...remaining].filter((id) => assets.some((a) => a.id === id));
      onChange(ordered.slice(0, 14));
    } else {
      handleAddAll();
    }
  };

  const assetLabel = (a: Asset) => {
    const name = a.file_path.split('/').pop() ?? `Asset ${a.id}`;
    return `#${a.id} ${name}`;
  };

  const categoryBadge = (assetId: number) => {
    const rec = getRec(assetId);
    const asset = getAssetById(assetId);
    const role = rec?.role_guess ?? asset?.qc?.role_guess ?? null;
    const cat = rec?.likely_category ?? null;
    if (!role && !cat) return null;
    const color = CATEGORY_COLORS[cat ?? 'unknown'];
    return (
      <span
        style={{
          fontSize: '0.68rem',
          padding: '1px 5px',
          borderRadius: 3,
          background: `${color}22`,
          color,
          fontWeight: 600,
        }}
      >
        {role ?? cat}
      </span>
    );
  };

  if (loadingAssets) {
    return (
      <div style={{ padding: compact ? 8 : 16 }}>
        <div className="flex items-center gap-1">
          <div className="spinner" />
          <span className="text-sm text-muted">Loading assets…</span>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="flex justify-between items-center" style={{ marginBottom: compact ? 6 : 10 }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: compact ? '0.85rem' : '0.95rem' }}>
            📎 Reference Images
          </span>
          <span className="text-sm text-muted" style={{ marginLeft: 8 }}>
            {value.length}/14 · order = upload sequence
          </span>
        </div>
        <div className="flex gap-1">
          {value.length < assets.length && assets.length > 0 && (
            <button
              className="secondary"
              style={{ fontSize: '0.75rem', padding: '3px 8px' }}
              onClick={handleAddAll}
              title="Add all uploaded assets (up to 14)"
            >
              📎 Add all
            </button>
          )}
          {assets.length > 0 && (
            <button
              className="secondary"
              style={{ fontSize: '0.75rem', padding: '3px 8px' }}
              onClick={handleAutoOrder}
              title="Auto-order: characters first, then objects, then world"
            >
              ✨ Smart order
            </button>
          )}
          {value.length > 0 && (
            <button
              className="secondary"
              style={{ fontSize: '0.75rem', padding: '3px 8px' }}
              onClick={() => onChange([])}
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* Info note */}
      <div style={{
        fontSize: '0.75rem',
        color: 'var(--muted)',
        padding: '6px 10px',
        background: 'rgba(99,102,241,0.06)',
        borderRadius: 6,
        marginBottom: compact ? 6 : 10,
        lineHeight: 1.4,
      }}>
        💡 The model decides how to use each image (character, object, world) based on
        content & prompt. You control which images to include and their <strong>order</strong>.
      </div>

      {/* Ordered list */}
      {value.length > 0 && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginBottom: compact ? 6 : 10 }}>
          {value.map((assetId, index) => {
            const asset = getAssetById(assetId);
            return (
              <div
                key={`${assetId}-${index}`}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 6,
                  padding: '4px 8px',
                  background: 'var(--surface)',
                  border: '1px solid var(--border)',
                  borderRadius: 6,
                  fontSize: '0.82rem',
                }}
              >
                <span style={{
                  width: 22,
                  height: 22,
                  borderRadius: '50%',
                  background: 'var(--accent)',
                  color: '#fff',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  fontSize: '0.7rem',
                  fontWeight: 700,
                  flexShrink: 0,
                }}>
                  {index + 1}
                </span>
                <span style={{ flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {asset ? assetLabel(asset) : `Asset #${assetId}`}
                </span>
                {categoryBadge(assetId)}
                <div className="flex gap-1" style={{ flexShrink: 0 }}>
                  <button
                    className="secondary"
                    style={{ fontSize: '0.65rem', padding: '1px 4px', lineHeight: 1 }}
                    onClick={() => handleMoveUp(index)}
                    disabled={index === 0}
                    title="Move up"
                  >↑</button>
                  <button
                    className="secondary"
                    style={{ fontSize: '0.65rem', padding: '1px 4px', lineHeight: 1 }}
                    onClick={() => handleMoveDown(index)}
                    disabled={index === value.length - 1}
                    title="Move down"
                  >↓</button>
                  <button
                    className="secondary"
                    style={{ fontSize: '0.65rem', padding: '1px 4px', lineHeight: 1, color: 'var(--danger)' }}
                    onClick={() => handleRemove(index)}
                    title="Remove"
                  >✕</button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add asset dropdown */}
      {value.length < 14 && availableAssets.length > 0 && (
        <select
          value=""
          onChange={(e) => {
            if (e.target.value) handleAdd(Number(e.target.value));
          }}
          style={{
            fontSize: '0.82rem',
            padding: '4px 8px',
            background: 'var(--surface)',
            width: '100%',
          }}
        >
          <option value="">+ Add reference image…</option>
          {availableAssets.map((a) => {
            const rec = getRec(a.id);
            const cat = rec?.likely_category;
            return (
              <option key={a.id} value={a.id}>
                {assetLabel(a)}
                {a.qc?.role_guess ? ` (${a.qc.role_guess})` : ''}
                {cat ? ` [${cat}]` : ''}
              </option>
            );
          })}
        </select>
      )}
    </div>
  );
}


/**
 * Read-only mini visualization of an upload plan.
 * Shows count and category color dots.
 */
export function RefPlanBadge({ assetIds }: { assetIds: number[] | null }) {
  if (!assetIds || assetIds.length === 0) {
    return <span className="text-muted text-sm">No refs</span>;
  }

  return (
    <span className="text-sm" style={{ fontWeight: 500, display: 'inline-flex', alignItems: 'center', gap: 3, flexWrap: 'wrap' }}>
      <span style={{ marginRight: 2 }}>📎{assetIds.length}</span>
      {assetIds.map((id, i) => (
        <span key={`${id}-${i}`} style={{ display: 'inline-flex', alignItems: 'center', gap: 2 }}>
          {i > 0 && <span className="text-muted" style={{ fontSize: '0.6rem' }}>→</span>}
          <span style={{
            fontSize: '0.7rem',
            padding: '1px 4px',
            borderRadius: 3,
            background: 'var(--surface)',
            border: '1px solid var(--border)',
          }}>
            #{id}
          </span>
        </span>
      ))}
    </span>
  );
}
