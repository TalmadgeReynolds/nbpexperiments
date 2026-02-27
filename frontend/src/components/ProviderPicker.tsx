import type { AIProvider } from '../types';

interface Props {
  value: AIProvider;
  onChange: (p: AIProvider) => void;
  /** Compact inline style (default) vs label above */
  inline?: boolean;
}

/**
 * Gemini / Claude toggle used anywhere AI is invoked.
 */
export default function ProviderPicker({ value, onChange, inline = true }: Props) {
  const options: { value: AIProvider; label: string; icon: string }[] = [
    { value: 'gemini', label: 'Gemini', icon: '💎' },
    { value: 'claude', label: 'Claude', icon: '🟠' },
  ];

  if (inline) {
    return (
      <span style={{ display: 'inline-flex', gap: 2, background: 'var(--surface)', borderRadius: 6, padding: 2 }}>
        {options.map((o) => (
          <button
            key={o.value}
            className={value === o.value ? '' : 'secondary'}
            style={{
              fontSize: '0.72rem',
              padding: '2px 8px',
              borderRadius: 4,
              minWidth: 0,
            }}
            onClick={(e) => { e.preventDefault(); onChange(o.value); }}
            type="button"
          >
            {o.icon} {o.label}
          </button>
        ))}
      </span>
    );
  }

  return (
    <div className="form-row" style={{ width: 160 }}>
      <label>AI Provider</label>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value as AIProvider)}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.icon} {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}
