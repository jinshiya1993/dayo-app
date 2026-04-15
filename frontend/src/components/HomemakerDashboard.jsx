import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

export default function HomemakerDashboard({ plan, profileData, childList, onPlanDay, planning }) {
  const navigate = useNavigate();
  const d = plan?.plan_data || {};
  const meals = d.meals || {};
  const snacks = meals.snacks || [];
  const classAlerts = d.class_alerts || [];
  const kidsActivities = d.kids_activities || [];
  const groceryData = d.grocery_list || {};
  const housework = (d.housework || []).slice(0, 4);
  const selfcare = d.selfcare || {};
  const notes = d.notes || '';

  const [checkedHousework, setCheckedHousework] = useState([]);
  const [checkedGrocery, setCheckedGrocery] = useState([]);
  const [expandGrocery, setExpandGrocery] = useState(false);

  // Flatten grocery items for progress tracking
  const allGroceryItems = Object.entries(groceryData).flatMap(([cat, items]) =>
    (items || []).map((item, i) => ({ category: cat, name: item, key: `${cat}-${i}` }))
  );
  const groceryTotal = allGroceryItems.length;
  const groceryBought = checkedGrocery.length;

  function toggleHousework(idx) {
    setCheckedHousework((prev) =>
      prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]
    );
  }

  function toggleGroceryItem(key) {
    setCheckedGrocery((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  // Quick chips
  const chips = ['Quick dinner idea'];
  if (childList?.length > 0) chips.push(`${childList[0].name} is sick`);
  if (classAlerts.length > 0) chips.push(`${classAlerts[0].class} leave time`);
  chips.push('Skip grocery');

  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  // Separate together activities
  const togetherActivities = kidsActivities.filter((a) =>
    a.child && (a.child.includes('&') || a.child.toLowerCase().includes('together'))
  );
  const individualActivities = kidsActivities.filter((a) =>
    !a.child || (!a.child.includes('&') && !a.child.toLowerCase().includes('together'))
  );

  return (
    <>
      {/* ── 1. Greeting Strip ────────────────────────────── */}
      <div style={{
        background: '#1a1a1a', borderRadius: 14, padding: '20px',
        margin: '0 16px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
      }}>
        <div>
          <div style={{ color: '#888', fontSize: 12 }}>Your plan is ready</div>
          <div style={{ color: 'white', fontFamily: 'Georgia, serif', fontSize: 20, fontWeight: 700, margin: '2px 0' }}>
            {profileData?.display_name || 'there'}
          </div>
          <div style={{ color: '#888', fontSize: 12 }}>{dateStr}</div>
        </div>
        <button onClick={onPlanDay} disabled={planning} style={{
          background: '#C2855A', color: 'white', border: 'none', borderRadius: 20,
          padding: '10px 18px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
          opacity: planning ? 0.6 : 1,
        }}>
          {planning ? 'Planning...' : 'Plan my week'}
        </button>
      </div>

      {/* ── 2. Class Alerts ──────────────────────────────── */}
      {classAlerts.length > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 10 }}>
          {classAlerts.map((cls, i) => (
            <div key={i} style={{
              background: '#FFF3CD', borderRadius: 20, padding: '10px 16px',
              display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
            }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#F59E0B', flexShrink: 0 }} />
              <div style={{ flex: 1, fontSize: 13, color: '#856404' }}>
                <strong>{cls.class}</strong> — {cls.child} — {cls.time}
              </div>
              <div style={{ fontSize: 11, color: '#856404', fontWeight: 600 }}>
                Leave {cls.leave_by}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── 3. Today's Meals ─────────────────────────────── */}
      <div className="section-header">
        <div className="section-title">Today's Meals</div>
      </div>
      <div className="meal-scroll">
        {['breakfast', 'lunch', 'dinner'].map((type) => {
          const meal = meals[type];
          if (!meal) return null;
          const emojis = { breakfast: '🥞', lunch: '🍛', dinner: '🍲' };
          const bgs = { breakfast: '#FFF8F0', lunch: '#F0FFF8', dinner: '#FFF5F0' };
          return (
            <div key={type} style={{
              minWidth: 150, maxWidth: 150, background: 'white',
              borderRadius: 14, border: '0.5px solid #EDE8E3', overflow: 'hidden', flexShrink: 0,
            }}>
              <div style={{ height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 36, background: bgs[type] }}>
                {emojis[type]}
              </div>
              <div style={{ padding: '10px 12px' }}>
                <div style={{
                  display: 'inline-block', background: '#FFF8F0', color: '#C2855A',
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10, marginBottom: 4,
                }}>
                  {type}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3, marginBottom: 2 }}>{meal.name}</div>
                {meal.prep_mins > 0 && (
                  <div style={{ fontSize: 11, color: '#888' }}>{meal.prep_mins} min prep</div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Snack pill strip */}
      {snacks.length > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 14 }}>
          <div style={{
            display: 'inline-flex', alignItems: 'center', gap: 6,
            background: '#F5F0FF', borderRadius: 20, padding: '6px 14px',
          }}>
            <span style={{ fontSize: 13 }}>🍪</span>
            <span style={{ fontSize: 12, color: '#6B46C1', fontWeight: 600 }}>Snacks:</span>
            <span style={{ fontSize: 12, color: '#6B46C1' }}>{snacks.join('  •  ')}</span>
          </div>
        </div>
      )}

      {/* ── 4. Grocery List ──────────────────────────────── */}
      {groceryTotal > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 16 }}>
          <div style={{ background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3', padding: '16px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
              <div style={{ fontFamily: 'Georgia, serif', fontSize: 16, fontWeight: 700 }}>Grocery List</div>
              <div style={{ fontSize: 12, color: '#888' }}>{groceryBought}/{groceryTotal} bought</div>
            </div>

            {/* Progress bar */}
            <div style={{ height: 4, borderRadius: 2, background: '#EDE8E3', marginBottom: 14 }}>
              <div style={{ height: 4, borderRadius: 2, background: '#C2855A', width: `${groceryTotal > 0 ? (groceryBought / groceryTotal) * 100 : 0}%`, transition: 'width 0.3s' }} />
            </div>

            {/* Items */}
            {allGroceryItems.slice(0, expandGrocery ? undefined : 5).map((item) => (
              <div key={item.key} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
                borderBottom: '0.5px solid #EDE8E3',
              }}>
                <div onClick={() => toggleGroceryItem(item.key)} style={{
                  width: 22, height: 22, borderRadius: '50%',
                  border: checkedGrocery.includes(item.key) ? 'none' : '1.5px solid #EDE8E3',
                  background: checkedGrocery.includes(item.key) ? '#C2855A' : 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', fontSize: 11, flexShrink: 0, cursor: 'pointer',
                }}>
                  {checkedGrocery.includes(item.key) && '✓'}
                </div>
                <div style={{ flex: 1 }}>
                  <span style={{
                    fontSize: 14,
                    textDecoration: checkedGrocery.includes(item.key) ? 'line-through' : 'none',
                    color: checkedGrocery.includes(item.key) ? '#AAA' : '#1a1a1a',
                  }}>
                    {item.name}
                  </span>
                  <span style={{ fontSize: 10, color: '#AAA', marginLeft: 6 }}>{item.category}</span>
                </div>
              </div>
            ))}

            {/* Expander */}
            {groceryTotal > 5 && (
              <button onClick={() => setExpandGrocery(!expandGrocery)} style={{
                width: '100%', padding: '10px', border: 'none', background: 'none',
                color: '#C2855A', fontSize: 13, fontWeight: 600, cursor: 'pointer', marginTop: 4,
              }}>
                {expandGrocery ? 'Show less' : `See all ${groceryTotal} items`}
              </button>
            )}
          </div>
        </div>
      )}

      {/* ── 5. Kids Activities ───────────────────────────── */}
      {kidsActivities.length > 0 && (
        <>
          <div className="section-header">
            <div className="section-title">Kids Activities</div>
          </div>

          {/* Individual activities — 2 column grid */}
          {individualActivities.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, padding: '0 16px', marginBottom: 10 }}>
              {individualActivities.map((act, i) => {
                const colors = [
                  { bg: '#FFF8F0', text: '#C2855A', badge: '#C2855A' },
                  { bg: '#F5F0FF', text: '#6B46C1', badge: '#6B46C1' },
                  { bg: '#F0FFF8', text: '#2D7A5B', badge: '#2D7A5B' },
                  { bg: '#FFF5F0', text: '#9B4000', badge: '#9B4000' },
                ];
                const c = colors[i % colors.length];
                const actEmojis = ['🎨', '🧸', '📚', '⚽', '🎵', '🧩'];
                return (
                  <div key={i} style={{ background: c.bg, borderRadius: 14, border: '0.5px solid #EDE8E3', overflow: 'hidden' }}>
                    <div style={{ height: 52, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 26 }}>
                      {actEmojis[i % actEmojis.length]}
                    </div>
                    <div style={{ padding: '8px 12px 12px' }}>
                      {/* Child badge */}
                      <div style={{
                        display: 'inline-block', background: c.badge, color: 'white',
                        fontSize: 9, fontWeight: 700, padding: '2px 8px', borderRadius: 10, marginBottom: 4,
                        textTransform: 'uppercase', letterSpacing: 0.5,
                      }}>
                        {act.child} {act.age ? `· ${act.age}y` : ''}
                      </div>
                      <div style={{ fontWeight: 700, fontSize: 13, color: c.text, lineHeight: 1.3, marginBottom: 3 }}>
                        {act.activity}
                      </div>
                      {act.description && (
                        <div style={{ fontSize: 11, color: '#888', marginBottom: 4 }}>{act.description}</div>
                      )}
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 6 }}>
                        {(act.materials || []).slice(0, 3).map((m, mi) => (
                          <span key={mi} style={{ fontSize: 9, background: 'rgba(0,0,0,0.06)', borderRadius: 6, padding: '2px 6px' }}>{m}</span>
                        ))}
                      </div>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <span style={{ fontSize: 10, color: '#888' }}>{act.duration}</span>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}

          {/* Together activities — full width dark card */}
          {togetherActivities.map((act, i) => (
            <div key={`together-${i}`} style={{
              background: '#1a1a1a', borderRadius: 14, padding: '16px',
              margin: '0 16px 10px', display: 'flex', gap: 12, alignItems: 'center',
            }}>
              <div style={{ fontSize: 28 }}>👨‍👩‍👧‍👦</div>
              <div style={{ flex: 1 }}>
                <div style={{ fontSize: 10, color: '#C2855A', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Together Time
                </div>
                <div style={{ color: 'white', fontWeight: 700, fontSize: 14, marginTop: 2 }}>{act.activity}</div>
                {act.description && <div style={{ color: '#888', fontSize: 11, marginTop: 2 }}>{act.description}</div>}
                <div style={{ color: '#666', fontSize: 10, marginTop: 4 }}>{act.duration}</div>
              </div>
            </div>
          ))}

          <div style={{ height: 6 }} />
        </>
      )}

      {/* ── 6. Housework Strip ───────────────────────────── */}
      {housework.length > 0 && (
        <>
          <div className="section-header">
            <div className="section-title">Housework</div>
            <span style={{ fontSize: 12, color: '#888' }}>
              {checkedHousework.length}/{housework.length} done
            </span>
          </div>
          <div style={{ display: 'flex', gap: 10, padding: '0 16px', marginBottom: 16, overflowX: 'auto' }}>
            {housework.map((task, idx) => (
              <div key={idx} onClick={() => toggleHousework(idx)} style={{
                minWidth: 100, textAlign: 'center', cursor: 'pointer', padding: '12px 8px',
              }}>
                {/* Circular checkbox */}
                <div style={{
                  width: 40, height: 40, borderRadius: '50%', margin: '0 auto 8px',
                  border: checkedHousework.includes(idx) ? 'none' : '2px solid #EDE8E3',
                  background: checkedHousework.includes(idx) ? '#C2855A' : 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', fontSize: 16, transition: 'all 0.2s',
                }}>
                  {checkedHousework.includes(idx) ? '✓' : ['🧹', '👕', '🧽', '🗑️'][idx % 4]}
                </div>
                <div style={{
                  fontSize: 11, fontWeight: 500,
                  color: checkedHousework.includes(idx) ? '#AAA' : '#1a1a1a',
                  textDecoration: checkedHousework.includes(idx) ? 'line-through' : 'none',
                  lineHeight: 1.3,
                }}>
                  {task.length > 25 ? task.slice(0, 25) + '...' : task}
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* ── 7. Me Time Card ──────────────────────────────── */}
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{
          background: '#F5EEFF', borderRadius: 14, padding: '16px',
          display: 'flex', alignItems: 'center', gap: 14,
        }}>
          <div style={{
            width: 44, height: 44, borderRadius: 12,
            background: '#E8DCFF', display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 22,
          }}>
            🧘
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700, fontSize: 14, color: '#6B46C1' }}>Me Time</div>
            <div style={{ fontSize: 12, color: '#8B5CF6', marginTop: 2 }}>
              {selfcare.activity || 'Take a break and relax'}
              {selfcare.time && ` · ${selfcare.time}`}
              {selfcare.duration && ` · ${selfcare.duration}`}
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#8B5CF6', fontWeight: 600 }}>Protected</div>
        </div>
      </div>

      {/* ── Notes ─────────────────────────────────────────── */}
      {notes && (
        <div style={{ padding: '0 16px', marginBottom: 14 }}>
          <div style={{
            background: '#FFF8F0', borderRadius: 14, padding: '12px 14px',
            fontSize: 13, color: '#9B4000', display: 'flex', gap: 8, alignItems: 'flex-start',
          }}>
            <span>💡</span>
            <span>{notes}</span>
          </div>
        </div>
      )}

      {/* ── 8. Quick Chat Chips ───────────────────────────── */}
      <div style={{ padding: '0 16px', marginBottom: 24 }}>
        <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
          {chips.map((chip) => (
            <button key={chip} onClick={() => navigate('/chat', { state: { prefill: chip } })}
              style={{
                padding: '9px 16px', borderRadius: 20, border: '0.5px solid #EDE8E3',
                background: 'white', fontSize: 12, whiteSpace: 'nowrap', cursor: 'pointer',
                color: '#1a1a1a', fontWeight: 500,
              }}>
              {chip}
            </button>
          ))}
        </div>
      </div>
    </>
  );
}
