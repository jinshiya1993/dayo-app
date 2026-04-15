import { useState, useEffect } from 'react';
import { plans } from '../services/api';

export default function WeeklyMealInline() {
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [activeMeal, setActiveMeal] = useState(null);
  const [actionMode, setActionMode] = useState(null);
  const [changeText, setChangeText] = useState('');
  const [swapping, setSwapping] = useState(false);

  useEffect(() => { loadWeek(); }, []);

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

  const mealDots = { breakfast: '#F59E0B', lunch: '#2D7A5B', dinner: '#DC3545' };
  const dayColors = ['#FFF8F0', '#F0FFF8', '#FFF0F5', '#F0F0FF', '#FFF8F0', '#F0FFF8', '#FFF0F5'];

  if (loading) {
    return <div style={{ padding: '0 16px 14px', fontSize: 12, color: '#888' }}>Loading week...</div>;
  }

  const futureDays = days.filter(d => !d.is_today);
  const hasUnplanned = futureDays.some(d => !d.has_plan);

  return (
    <div style={{ marginBottom: 14 }}>
      {hasUnplanned && (
        <div style={{ padding: '0 16px', marginBottom: 8 }}>
          <button
            onClick={handleGenerateWeek}
            disabled={generating}
            style={{
              width: '100%', padding: '8px', background: '#FFF8F0',
              border: '0.5px solid #EDE8E3', borderRadius: 10,
              fontSize: 12, color: '#C2855A', fontWeight: 600, cursor: 'pointer',
              opacity: generating ? 0.6 : 1,
            }}
          >
            {generating ? 'Generating...' : 'Generate meals for empty days'}
          </button>
        </div>
      )}

      <div className="meal-scroll">
        {futureDays.map((day, idx) => {
          const isActive = activeMeal && activeMeal.date === day.date;

          return (
            <div key={day.date} style={{
              minWidth: 130, maxWidth: 130, background: 'white',
              borderRadius: 14, border: '0.5px solid #EDE8E3',
              overflow: 'hidden', flexShrink: 0,
            }}>
              {/* Day header with color */}
              <div style={{
                padding: '10px 10px 8px', background: dayColors[idx % dayColors.length],
                textAlign: 'center',
              }}>
                <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'Georgia, serif' }}>
                  {day.day_name.slice(0, 3)}
                </div>
                <div style={{ fontSize: 10, color: '#888' }}>
                  {new Date(day.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                </div>
              </div>

              {/* Meals */}
              <div style={{ padding: '8px 10px' }}>
                {!day.has_plan ? (
                  <div style={{ fontSize: 11, color: '#AAA', fontStyle: 'italic', padding: '4px 0' }}>No plan</div>
                ) : (
                  ['breakfast', 'lunch', 'dinner'].map((mt) => {
                    const name = day.meals[mt];
                    if (!name) return null;
                    const isTapped = isActive && activeMeal.mealType === mt;

                    return (
                      <div key={mt} style={{ marginBottom: 6 }}>
                        <div
                          onClick={(e) => {
                            e.stopPropagation();
                            if (isTapped) { setActiveMeal(null); setActionMode(null); setChangeText(''); }
                            else { setActiveMeal({ date: day.date, mealType: mt }); setActionMode(null); setChangeText(''); }
                          }}
                          style={{ cursor: 'pointer' }}
                        >
                          <div style={{
                            width: 6, height: 6, borderRadius: '50%', background: mealDots[mt],
                            display: 'inline-block', marginRight: 4, verticalAlign: 'middle',
                          }} />
                          <span style={{ fontSize: 11, color: '#1a1a1a', lineHeight: 1.4 }}>
                            {name}
                          </span>
                        </div>

                        {isTapped && !swapping && (
                          <div style={{ marginTop: 4 }}>
                            {!actionMode && (
                              <div style={{ display: 'flex', gap: 3 }}>
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleSwap(day.date, mt); }}
                                  style={{
                                    flex: 1, padding: '4px 0', background: '#FFF8F0', border: '0.5px solid #EDE8E3',
                                    borderRadius: 6, fontSize: 9, color: '#9B4000', cursor: 'pointer', fontWeight: 500,
                                  }}
                                >
                                  🔄 Swap
                                </button>
                                <button
                                  onClick={(e) => { e.stopPropagation(); setActionMode('change'); }}
                                  style={{
                                    flex: 1, padding: '4px 0', background: '#FFF8F0', border: '0.5px solid #EDE8E3',
                                    borderRadius: 6, fontSize: 9, color: '#9B4000', cursor: 'pointer', fontWeight: 500,
                                  }}
                                >
                                  ✏️ Change
                                </button>
                              </div>
                            )}
                            {actionMode === 'change' && (
                              <div style={{ display: 'flex', gap: 3, marginTop: 3 }}>
                                <input
                                  value={changeText}
                                  onChange={(e) => setChangeText(e.target.value)}
                                  placeholder="e.g. biryani"
                                  onKeyDown={(e) => e.key === 'Enter' && handleChange(day.date, mt)}
                                  onClick={(e) => e.stopPropagation()}
                                  style={{
                                    flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 6,
                                    padding: '4px 6px', fontSize: 10, outline: 'none', minWidth: 0,
                                  }}
                                  autoFocus
                                />
                                <button
                                  onClick={(e) => { e.stopPropagation(); handleChange(day.date, mt); }}
                                  style={{
                                    background: '#C2855A', border: 'none', borderRadius: 6,
                                    padding: '4px 8px', fontSize: 10, color: 'white', cursor: 'pointer',
                                  }}
                                >
                                  Go
                                </button>
                              </div>
                            )}
                          </div>
                        )}
                        {isTapped && swapping && (
                          <div style={{ fontSize: 9, color: '#888', padding: '2px 0' }}>Updating...</div>
                        )}
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
