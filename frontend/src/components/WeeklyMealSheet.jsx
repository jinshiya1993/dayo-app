import { useState, useEffect } from 'react';
import { plans } from '../services/api';

export default function WeeklyMealSheet({ open, onClose }) {
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [activeMeal, setActiveMeal] = useState(null); // {date, mealType}
  const [actionMode, setActionMode] = useState(null); // 'swap' | 'change'
  const [changeText, setChangeText] = useState('');
  const [swapping, setSwapping] = useState(false);

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    async function fetchWeek() {
      setLoading(true);
      setDays([]);
      const res = await plans.weekly();
      if (cancelled) return;
      if (Array.isArray(res)) setDays(res);
      setLoading(false);
    }
    fetchWeek();
    return () => { cancelled = true; };
  }, [open]);

  async function loadWeek() {
    setLoading(true);
    const res = await plans.weekly();
    if (Array.isArray(res)) setDays(res);
    setLoading(false);
  }

  async function handleGenerateWeek() {
    setGenerating(true);
    await plans.generateWeek();
    await loadWeek();
    setGenerating(false);
  }

  async function handleSwap(date, mealType) {
    setSwapping(true);
    const res = await plans.swapMeal(date, mealType);
    if (!res.error) await loadWeek();
    setSwapping(false);
    setActiveMeal(null);
    setActionMode(null);
  }

  async function handleChange(date, mealType) {
    if (!changeText.trim()) return;
    setSwapping(true);
    const res = await plans.changeMeal(date, mealType, changeText.trim());
    if (!res.error) await loadWeek();
    setSwapping(false);
    setActiveMeal(null);
    setActionMode(null);
    setChangeText('');
  }

  if (!open) return null;

  const mealTypes = [
    { key: 'breakfast', label: 'B', color: '#F59E0B' },
    { key: 'lunch', label: 'L', color: '#2D7A5B' },
    { key: 'dinner', label: 'D', color: '#DC3545' },
  ];

  const hasUnplanned = days.some(d => !d.has_plan);

  return (
    <>
      {/* Backdrop */}
      <div onClick={onClose} style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.3)',
        zIndex: 998, animation: 'fadeIn 0.2s ease',
      }} />

      {/* Sheet */}
      <div style={{
        position: 'fixed', bottom: 0, left: 0, right: 0,
        background: 'white', borderRadius: '20px 20px 0 0',
        height: '75vh', overflowY: 'auto', zIndex: 999,
        padding: '20px 16px', paddingBottom: 80,
        animation: 'slideUp 0.3s ease',
        boxShadow: '0 -4px 20px rgba(0,0,0,0.1)',
      }}>
        {/* Handle */}
        <div style={{ width: 40, height: 4, borderRadius: 2, background: '#EDE8E3', margin: '0 auto 16px' }} />

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
          <div style={{ fontFamily: 'Georgia, serif', fontSize: 18, fontWeight: 700 }}>This week's meals</div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: 18, cursor: 'pointer', color: '#888' }}>
            ✕
          </button>
        </div>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 30, color: '#888' }}>Loading...</div>
        ) : (
          <>
            {/* Generate missing days */}
            {hasUnplanned && (
              <button
                onClick={handleGenerateWeek}
                disabled={generating}
                style={{
                  width: '100%', padding: '10px', background: '#FFF8F0',
                  border: '0.5px solid #EDE8E3', borderRadius: 10,
                  fontSize: 13, color: '#C2855A', fontWeight: 600, cursor: 'pointer',
                  marginBottom: 14, opacity: generating ? 0.6 : 1,
                }}
              >
                {generating ? 'Generating plans...' : 'Generate meals for empty days'}
              </button>
            )}

            {/* Days */}
            {days.map((day) => {
              const isActive = activeMeal && activeMeal.date === day.date;

              return (
                <div key={day.date} style={{
                  marginBottom: 10, background: day.is_today ? '#FFF8F0' : '#FAFAFA',
                  borderRadius: 12, border: day.is_today ? '1px solid #C2855A' : '0.5px solid #EDE8E3',
                  padding: '10px 12px',
                }}>
                  {/* Day header */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 13, fontWeight: 600, color: day.is_today ? '#C2855A' : '#1a1a1a' }}>
                      {day.is_today ? 'Today' : day.day_name}
                    </span>
                    <span style={{ fontSize: 11, color: '#888' }}>
                      {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                    </span>
                  </div>

                  {!day.has_plan ? (
                    <div style={{ fontSize: 12, color: '#AAA', fontStyle: 'italic' }}>No plan yet</div>
                  ) : (
                    /* Meal rows */
                    mealTypes.map(({ key, label, color }) => {
                      const name = day.meals[key];
                      if (!name) return null;
                      const isTapped = isActive && activeMeal.mealType === key;

                      return (
                        <div key={key}>
                          <div
                            onClick={() => {
                              if (isTapped) { setActiveMeal(null); setActionMode(null); setChangeText(''); }
                              else { setActiveMeal({ date: day.date, mealType: key }); setActionMode(null); setChangeText(''); }
                            }}
                            style={{
                              display: 'flex', alignItems: 'center', gap: 8, padding: '5px 0',
                              cursor: 'pointer',
                            }}
                          >
                            <div style={{
                              width: 20, height: 20, borderRadius: '50%', background: color,
                              display: 'flex', alignItems: 'center', justifyContent: 'center',
                              fontSize: 10, color: 'white', fontWeight: 700, flexShrink: 0,
                            }}>
                              {label}
                            </div>
                            <span style={{ fontSize: 13, flex: 1, color: '#1a1a1a' }}>{name}</span>
                          </div>

                          {/* Actions for tapped meal */}
                          {isTapped && !swapping && (
                            <div style={{ marginLeft: 28, marginBottom: 6 }}>
                              {!actionMode && (
                                <div style={{ display: 'flex', gap: 6 }}>
                                  <button
                                    onClick={() => handleSwap(day.date, key)}
                                    style={{
                                      flex: 1, padding: '5px 0', background: '#FFF8F0', border: '0.5px solid #EDE8E3',
                                      borderRadius: 8, fontSize: 11, color: '#9B4000', cursor: 'pointer', fontWeight: 500,
                                    }}
                                  >
                                    🔄 Swap
                                  </button>
                                  <button
                                    onClick={() => setActionMode('change')}
                                    style={{
                                      flex: 1, padding: '5px 0', background: '#FFF8F0', border: '0.5px solid #EDE8E3',
                                      borderRadius: 8, fontSize: 11, color: '#9B4000', cursor: 'pointer', fontWeight: 500,
                                    }}
                                  >
                                    ✏️ Change
                                  </button>
                                </div>
                              )}
                              {actionMode === 'change' && (
                                <div style={{ display: 'flex', gap: 4, marginTop: 4 }}>
                                  <input
                                    value={changeText}
                                    onChange={(e) => setChangeText(e.target.value)}
                                    placeholder="e.g. English breakfast"
                                    onKeyDown={(e) => e.key === 'Enter' && handleChange(day.date, key)}
                                    style={{
                                      flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 8,
                                      padding: '6px 10px', fontSize: 12, outline: 'none',
                                    }}
                                    autoFocus
                                  />
                                  <button
                                    onClick={() => handleChange(day.date, key)}
                                    style={{
                                      background: '#C2855A', border: 'none', borderRadius: 8,
                                      padding: '6px 12px', fontSize: 12, color: 'white', cursor: 'pointer',
                                    }}
                                  >
                                    Go
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                          {isTapped && swapping && (
                            <div style={{ marginLeft: 28, marginBottom: 6, fontSize: 11, color: '#888' }}>Updating...</div>
                          )}
                        </div>
                      );
                    })
                  )}
                </div>
              );
            })}
          </>
        )}
      </div>

      <style>{`
        @keyframes slideUp {
          from { transform: translateY(100%); }
          to { transform: translateY(0); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </>
  );
}
