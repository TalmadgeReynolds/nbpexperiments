import { useState } from 'react';
import { getAdvisorQuestions, getAdvisorConditions, createCondition } from '../api/client';
import type {
  AdvisorQuestion,
  AIProvider,
  QuestionAnswer,
  SuggestedCondition,
} from '../types';
import ConditionRefBuilder from './ConditionRefBuilder';
import ProviderPicker from './ProviderPicker';

type Step = 'idle' | 'loading-questions' | 'answering' | 'loading-conditions' | 'reviewing';

interface Props {
  experimentId: number;
  hypothesis: string;
  onConditionsAdded: () => void;
}

export default function HypothesisAdvisor({ experimentId, onConditionsAdded }: Props) {
  const [step, setStep] = useState<Step>('idle');
  const [questions, setQuestions] = useState<AdvisorQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [suggestions, setSuggestions] = useState<SuggestedCondition[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [error, setError] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [provider, setProvider] = useState<AIProvider>('gemini');

  const handleStart = async () => {
    setStep('loading-questions');
    setError(null);
    try {
      const resp = await getAdvisorQuestions(experimentId, provider);
      setQuestions(resp.questions);
      // Pre-fill answer fields
      const init: Record<string, string> = {};
      resp.questions.forEach((q) => { init[q.id] = ''; });
      setAnswers(init);
      setStep('answering');
    } catch (e) {
      setError(String(e));
      setStep('idle');
    }
  };

  const handleSubmitAnswers = async () => {
    const qa: QuestionAnswer[] = questions.map((q) => ({
      question: q.question,
      answer: answers[q.id] || '',
    }));
    const unanswered = qa.filter((a) => !a.answer.trim());
    if (unanswered.length > 0) {
      setError('Please answer all questions before continuing.');
      return;
    }
    setStep('loading-conditions');
    setError(null);
    try {
      const resp = await getAdvisorConditions(experimentId, qa, provider);
      setSuggestions(resp.conditions);
      setSelected(new Set(resp.conditions.map((_, i) => i)));
      setStep('reviewing');
    } catch (e) {
      setError(String(e));
      setStep('answering');
    }
  };

  const toggleSelection = (idx: number) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const handleAccept = async () => {
    setAdding(true);
    setError(null);
    try {
      for (const idx of Array.from(selected).sort()) {
        const s = suggestions[idx];
        await createCondition(experimentId, {
          name: s.name,
          prompt: s.prompt,
          upload_plan: s.upload_plan,
        });
      }
      onConditionsAdded();
      setStep('idle');
      setSuggestions([]);
      setQuestions([]);
      setAnswers({});
    } catch (e) {
      setError(String(e));
    } finally {
      setAdding(false);
    }
  };

  // ── Idle ──────────────────────────────────────────────────────
  if (step === 'idle') {
    return (
      <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
        <div className="flex justify-between items-center">
          <div>
            <h3 style={{ margin: 0, fontSize: '0.95rem' }}>✨ Hypothesis Advisor</h3>
            <p className="text-sm text-muted" style={{ marginTop: 4 }}>
              Let AI analyze your hypothesis and suggest experimental conditions
            </p>
          </div>
          <div className="flex items-center gap-1">
            <ProviderPicker value={provider} onChange={setProvider} />
            <button onClick={handleStart}>Get Started</button>
          </div>
        </div>
        {error && <p className="text-sm" style={{ color: 'var(--danger)', marginTop: 8 }}>{error}</p>}
      </div>
    );
  }

  // ── Loading ───────────────────────────────────────────────────
  if (step === 'loading-questions' || step === 'loading-conditions') {
    return (
      <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>✨ Hypothesis Advisor</h3>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginTop: 12 }}>
          <div className="spinner" />
          <span className="text-sm text-muted">
            {step === 'loading-questions'
              ? 'Analyzing your hypothesis…'
              : 'Designing conditions based on your answers…'}
          </span>
        </div>
      </div>
    );
  }

  // ── Answering questions ───────────────────────────────────────
  if (step === 'answering') {
    return (
      <div className="card" style={{ borderLeft: '3px solid var(--accent)' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>✨ Hypothesis Advisor — Clarifying Questions</h3>
        <p className="text-sm text-muted" style={{ marginTop: 4 }}>
          Answer these questions to help design the best conditions for your experiment.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 16, marginTop: 16 }}>
          {questions.map((q, i) => (
            <div key={q.id} style={{ borderBottom: '1px solid var(--border)', paddingBottom: 12 }}>
              <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                {i + 1}. {q.question}
              </label>
              {q.why && (
                <p className="text-sm text-muted" style={{ marginTop: 2, marginBottom: 6 }}>
                  💡 {q.why}
                </p>
              )}
              {q.options && q.options.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: 4, marginTop: 6 }}>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {q.options.map((opt) => (
                      <button
                        key={opt}
                        className={answers[q.id] === opt ? '' : 'secondary'}
                        style={{ fontSize: '0.8rem', padding: '4px 10px' }}
                        onClick={() => setAnswers({ ...answers, [q.id]: opt })}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                  <input
                    value={answers[q.id] || ''}
                    onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                    placeholder="Or type a custom answer…"
                    style={{ marginTop: 4 }}
                  />
                </div>
              ) : (
                <textarea
                  rows={2}
                  value={answers[q.id] || ''}
                  onChange={(e) => setAnswers({ ...answers, [q.id]: e.target.value })}
                  placeholder="Your answer…"
                  style={{ marginTop: 6 }}
                />
              )}
            </div>
          ))}
        </div>

        {error && <p className="text-sm" style={{ color: 'var(--danger)', marginTop: 8 }}>{error}</p>}

        <div className="flex gap-1" style={{ marginTop: 16 }}>
          <button onClick={handleSubmitAnswers}>Suggest Conditions →</button>
          <button className="secondary" onClick={() => { setStep('idle'); setError(null); }}>Cancel</button>
        </div>
      </div>
    );
  }

  // ── Reviewing suggestions ─────────────────────────────────────
  if (step === 'reviewing') {
    return (
      <div className="card" style={{ borderLeft: '3px solid var(--success)' }}>
        <h3 style={{ margin: 0, fontSize: '0.95rem' }}>✨ Suggested Conditions</h3>
        <p className="text-sm text-muted" style={{ marginTop: 4 }}>
          Select the conditions you want to add to your experiment.
        </p>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 16 }}>
          {suggestions.map((s, i) => (
            <div
              key={i}
              onClick={() => toggleSelection(i)}
              style={{
                border: `1px solid ${selected.has(i) ? 'var(--accent)' : 'var(--border)'}`,
                borderRadius: 8,
                padding: 12,
                cursor: 'pointer',
                background: selected.has(i) ? 'rgba(99,102,241,0.08)' : 'transparent',
                transition: 'all 0.15s',
              }}
            >
              <div className="flex items-center gap-1">
                <span style={{ fontSize: '1.1rem' }}>{selected.has(i) ? '☑' : '☐'}</span>
                <strong style={{ fontSize: '0.9rem' }}>{s.name}</strong>
              </div>
              <p className="text-sm" style={{ marginTop: 4, color: 'var(--text)' }}>
                <span className="text-muted">Prompt:</span> {s.prompt}
              </p>
              {s.rationale && (
                <p className="text-sm text-muted" style={{ marginTop: 4, fontStyle: 'italic' }}>
                  {s.rationale}
                </p>
              )}
              {s.ref_strategy && (
                <p className="text-sm" style={{ marginTop: 4, color: 'var(--accent)' }}>
                  📎 {s.ref_strategy}
                </p>
              )}
              {s.upload_plan && s.upload_plan.length > 0 && (
                <div style={{ marginTop: 6 }}>
                  <ConditionRefBuilder
                    value={s.upload_plan}
                    onChange={() => {}}
                    readOnly
                  />
                </div>
              )}
            </div>
          ))}
        </div>

        {error && <p className="text-sm" style={{ color: 'var(--danger)', marginTop: 8 }}>{error}</p>}

        <div className="flex gap-1" style={{ marginTop: 16 }}>
          <button onClick={handleAccept} disabled={adding || selected.size === 0}>
            {adding ? 'Adding…' : `Add ${selected.size} Condition${selected.size !== 1 ? 's' : ''}`}
          </button>
          <button className="secondary" onClick={() => setStep('answering')}>← Back to Questions</button>
          <button className="secondary" onClick={() => { setStep('idle'); setError(null); }}>Cancel</button>
        </div>
      </div>
    );
  }

  return null;
}
