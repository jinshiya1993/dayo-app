import { useState, useEffect, useRef, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { plans, grocery } from '../services/api';

const MEAL_LABELS = { breakfast: 'BREAKFAST', lunch: 'LUNCH', dinner: 'DINNER' };
const MEAL_TIMES = { breakfast: '07:00', lunch: '13:00', dinner: '19:00' };

// Match the warm palette used elsewhere in Dayo.
const MEAL_ICON_COLORS = {
  breakfast: { bg: '#F5E8D5', fg: '#B07A2A' },
  lunch:     { bg: '#DCE9F3', fg: '#4A7BA8' },
  dinner:    { bg: '#E2EBE5', fg: '#2D5F4C' },
};

const HIDDEN_TAG_PATTERNS = [
  /pcos/i, /diabet/i, /heart-?healthy/i, /anti-?inflammatory/i,
  /low gi/i, /postpartum/i, /lactation/i,
];
const isVisibleTag = (t) => !HIDDEN_TAG_PATTERNS.some((re) => re.test(t || ''));

export default function WeeklyMealInline({ onClose }) {
  const navigate = useNavigate();
  const [days, setDays] = useState([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [genError, setGenError] = useState('');
  const [swappingDay, setSwappingDay] = useState(null);
  const [locking, setLocking] = useState(false);
  const [lockedDone, setLockedDone] = useState(false);
  const [activeIdx, setActiveIdx] = useState(0);
  const trackRef = useRef(null);

  useEffect(() => { loadWeek(); }, []);

  // Backend's WeeklyMealsView.get() runs ensure_meals_ahead. If that
  // succeeds the response already has all 7 days planned. If it fails
  // silently (Gemini error etc.) days come back with has_plan: false —
  // in that case we explicitly call generateWeek as a defensive fallback
  // so the user still gets a populated week.
  async function loadWeek() {
    setLoading(true);
    setGenError('');
    const res = await plans.weekly();
    if (!Array.isArray(res)) { setLoading(false); return; }

    const missing = res.some((d) => !d.has_plan);
    if (!missing) {
      setDays(res);
      setLoading(false);
      return;
    }

    // Some days unplanned — backfill via explicit generateWeek call.
    setLoading(false);
    setGenerating(true);
    const genRes = await plans.generateWeek();
    if (genRes?.error) {
      setGenError('Weekly plan generation failed. Check server logs and try again.');
      setDays(res);
      setGenerating(false);
      return;
    }
    const refreshed = await plans.weekly();
    if (Array.isArray(refreshed)) setDays(refreshed);
    setGenerating(false);
  }

  async function reloadWeek() {
    const res = await plans.weekly();
    if (Array.isArray(res)) setDays(res);
  }

  async function handleSwapDay(date) {
    setSwappingDay(date);
    // Swap all 3 meals serially. Backend swap-meal endpoint handles one
    // at a time, so we chain. Slow but works without a new endpoint.
    for (const mt of ['breakfast', 'lunch', 'dinner']) {
      await plans.swapMeal(date, mt);
    }
    await reloadWeek();
    setSwappingDay(null);
  }

  async function handleLockWeek() {
    setLocking(true);
    await grocery.generate();
    setLocking(false);
    setLockedDone(true);
    // Brief flash, then collapse the inline so the dashboard's grocery
    // section becomes visible. No /grocery route exists.
    setTimeout(() => {
      if (typeof onClose === 'function') onClose();
    }, 900);
  }

  // Track scroll position to update active dot indicator.
  function handleScroll() {
    const el = trackRef.current;
    if (!el) return;
    const cardWidth = el.firstChild ? el.firstChild.offsetWidth + 12 : el.clientWidth;
    const idx = Math.round(el.scrollLeft / cardWidth);
    if (idx !== activeIdx) setActiveIdx(idx);
  }

  function scrollToIdx(i) {
    const el = trackRef.current;
    if (!el || !el.children[i]) return;
    el.children[i].scrollIntoView({ behavior: 'smooth', inline: 'center', block: 'nearest' });
  }

  const stats = useMemo(() => computeStats(days), [days]);
  const insightBanner = useMemo(() => {
    const today = days.find((d) => d.is_today);
    return today?.meal_health_banner || '';
  }, [days]);

  if (loading || generating) return <SkeletonPanel generating={generating} />;

  return (
    <div style={shellStyle}>
      <div style={headerStyle}>
        <div style={eyebrowStyle}>Plan the week</div>
        <h2 style={titleStyle}>Your week, <em style={titleAccentStyle}>sorted</em></h2>
        <div style={subStyle}>
          {stats.mealsPlanned} meals planned around your schedule. Swap any you don't fancy.
        </div>
      </div>

      {genError && (
        <div style={errorBannerStyle}>
          <div>{genError}</div>
          <button onClick={loadWeek} style={errorRetryStyle}>Try again</button>
        </div>
      )}

      <div style={statsStripStyle}>
        <div style={statCellStyle}>
          <div style={statValueStyle}>{stats.mealsPlanned}</div>
          <div style={statLabelStyle}>Meals planned</div>
        </div>
        <div style={statCellStyle}>
          <div style={statValueStyle}>{stats.ingredients || '—'}</div>
          <div style={statLabelStyle}>Ingredients</div>
        </div>
        <div style={statCellStyle}>
          <div style={statValueStyle}>{stats.cookTime || '—'}</div>
          <div style={statLabelStyle}>Total cook time</div>
        </div>
      </div>

      {insightBanner && (
        <div style={insightStyle}>
          <div style={insightIconStyle}>
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                 strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a10 10 0 1 0 10 10" />
              <path d="M12 6v6l4 2" />
            </svg>
          </div>
          <div style={insightTextStyle}>{insightBanner}</div>
        </div>
      )}

      <div ref={trackRef} onScroll={handleScroll} style={trackStyle} className="weekly-track">
        {days.map((day, idx) => (
          <DayCard
            key={day.date}
            day={day}
            swapping={swappingDay === day.date}
            onSwapDay={() => handleSwapDay(day.date)}
            onOpenMeal={(mealType, meal) => navigate('/recipe', {
              state: { meal, mealType, planDate: day.date },
            })}
            onSaved={reloadWeek}
          />
        ))}
      </div>

      {days.length > 1 && (
        <div style={dotsRowStyle}>
          {days.map((_, i) => (
            <button
              key={i}
              onClick={() => scrollToIdx(i)}
              aria-label={`Go to day ${i + 1}`}
              style={i === activeIdx ? dotActiveStyle : dotStyle}
            />
          ))}
        </div>
      )}

      <button onClick={handleLockWeek} disabled={locking || lockedDone} style={lockBtnStyle}>
        {lockedDone ? '✓ Grocery list ready' : locking ? 'Building grocery list…' : 'Lock the week & make grocery list →'}
      </button>

      <style>{`
        .weekly-track::-webkit-scrollbar { display: none; }
      `}</style>
    </div>
  );
}

function DayCard({ day, swapping, onSwapDay, onOpenMeal, onSaved }) {
  const [editing, setEditing] = useState(false);
  const [drafts, setDrafts] = useState({ breakfast: '', lunch: '', dinner: '' });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState('');

  const dateLabel = new Date(day.date).toLocaleDateString('en-US', {
    month: 'short', day: 'numeric',
  });
  const dayShort = day.day_name?.slice(0, 3) || '';

  function startEditing() {
    setDrafts({
      breakfast: day.meals?.breakfast?.name || '',
      lunch: day.meals?.lunch?.name || '',
      dinner: day.meals?.dinner?.name || '',
    });
    setSaveError('');
    setEditing(true);
  }

  function cancelEditing() {
    setEditing(false);
    setSaveError('');
  }

  async function handleSave() {
    // Only persist meals whose name actually changed. Skip blanks — we
    // don't support deleting a meal from this UI.
    const changes = ['breakfast', 'lunch', 'dinner'].filter((mt) => {
      const next = (drafts[mt] || '').trim();
      const prev = (day.meals?.[mt]?.name || '').trim();
      return next && next !== prev;
    });

    if (changes.length === 0) {
      setEditing(false);
      return;
    }

    setSaving(true);
    setSaveError('');
    const results = await Promise.all(
      changes.map((mt) => plans.renameMeal(day.date, mt, drafts[mt].trim())),
    );
    setSaving(false);

    if (results.some((r) => r?.error)) {
      setSaveError("Couldn't update some meals. Try again.");
      return;
    }

    setEditing(false);
    if (typeof onSaved === 'function') await onSaved();
  }

  return (
    <article style={day.is_today ? cardTodayStyle : cardStyle}>
      <div style={cardHeadStyle}>
        <div>
          <div style={cardDayNameStyle}>
            {dayShort}{day.is_today && <em style={cardDayAccentStyle}> — Today</em>}
          </div>
          <div style={cardDayDateStyle}>{dateLabel.toUpperCase()}</div>
        </div>
      </div>

      {!day.has_plan ? (
        <div style={emptyStyle}>No plan for this day yet.</div>
      ) : editing ? (
        <div style={mealsStackStyle}>
          {['breakfast', 'lunch', 'dinner'].map((mt) => (
            <div key={mt} style={editRowStyle}>
              <div style={{ ...mealIconStyle, background: MEAL_ICON_COLORS[mt].bg, color: MEAL_ICON_COLORS[mt].fg }}>
                <MealIcon mealType={mt} />
              </div>
              <div style={mealInfoStyle}>
                <div style={mealTypeStyle}>{MEAL_LABELS[mt]} · {MEAL_TIMES[mt]}</div>
                <input
                  type="text"
                  value={drafts[mt]}
                  onChange={(e) => setDrafts((d) => ({ ...d, [mt]: e.target.value }))}
                  placeholder={`${MEAL_LABELS[mt].toLowerCase()} name`}
                  disabled={saving}
                  style={editInputStyle}
                />
              </div>
            </div>
          ))}
          {saveError && <div style={saveErrorStyle}>{saveError}</div>}
        </div>
      ) : (
        <div style={mealsStackStyle}>
          {['breakfast', 'lunch', 'dinner'].map((mt) => {
            const m = day.meals?.[mt];
            if (!m || !m.name) return null;
            return (
              <button
                key={mt}
                onClick={() => onOpenMeal(mt, m)}
                style={mealRowStyle}
                aria-label={`Open ${m.name}`}
              >
                <div style={{ ...mealIconStyle, background: MEAL_ICON_COLORS[mt].bg, color: MEAL_ICON_COLORS[mt].fg }}>
                  <MealIcon mealType={mt} />
                </div>
                <div style={mealInfoStyle}>
                  <div style={mealTypeStyle}>{MEAL_LABELS[mt]} · {MEAL_TIMES[mt]}</div>
                  <div style={mealTitleStyle}>{m.name}</div>
                  <div style={mealMetaStyle}>
                    {[
                      m.prep_mins ? `${m.prep_mins} min` : null,
                      m.kcal ? `${m.kcal} kcal` : null,
                      ...(Array.isArray(m.tags) ? m.tags.filter(isVisibleTag).slice(0, 1) : []),
                    ].filter(Boolean).join(' · ')}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}

      {day.has_plan && (
        <div style={cardFooterStyle}>
          {editing ? (
            <>
              <button onClick={cancelEditing} disabled={saving} style={cardActionStyle}>
                Cancel
              </button>
              <button onClick={handleSave} disabled={saving} style={cardSavePrimaryStyle}>
                {saving ? 'Saving…' : 'Save'}
              </button>
            </>
          ) : (
            <>
              <button onClick={onSwapDay} disabled={swapping} style={cardActionStyle}>
                {swapping ? '…' : '⇄ Swap day'}
              </button>
              <button onClick={startEditing} style={cardActionStyle}>
                ✎ Edit meals
              </button>
            </>
          )}
        </div>
      )}
    </article>
  );
}

function MealIcon({ mealType }) {
  const common = {
    width: 14, height: 14, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'currentColor', strokeWidth: 1.8, strokeLinecap: 'round', strokeLinejoin: 'round',
  };
  if (mealType === 'breakfast') {
    return (
      <svg {...common}>
        <circle cx="12" cy="12" r="4" />
        <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
      </svg>
    );
  }
  if (mealType === 'lunch') {
    return (
      <svg {...common}>
        <path d="M3 11h18" />
        <path d="M5 11V7a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2v4" />
        <path d="M7 21h10" />
      </svg>
    );
  }
  return (
    <svg {...common}>
      <path d="M6 13.87A4 4 0 0 1 7.41 6a5.11 5.11 0 0 1 1.05-1.54 5 5 0 0 1 7.08 0A5.11 5.11 0 0 1 16.59 6 4 4 0 0 1 18 13.87V21H6Z" />
      <line x1="6" y1="17" x2="18" y2="17" />
    </svg>
  );
}

function SkeletonPanel({ generating }) {
  return (
    <div style={shellStyle}>
      <div style={{ ...headerStyle, opacity: 0.7 }}>
        <div style={eyebrowStyle}>Plan the week</div>
        <h2 style={titleStyle}>
          {generating ? 'Creating your week…' : 'Loading your week…'}
        </h2>
        <div style={subStyle}>
          {generating
            ? 'Planning 7 days of meals around your schedule. This takes ~10 seconds.'
            : 'One moment.'}
        </div>
      </div>
      <div style={{ display: 'flex', gap: 12, padding: '4px 16px 12px', overflow: 'hidden' }}>
        {[0, 1].map((i) => (
          <div key={i} style={{
            flex: '0 0 calc(100% - 30px)', height: 220, borderRadius: 22,
            background: 'linear-gradient(90deg, #F2EEE7 0%, #FAF7F1 50%, #F2EEE7 100%)',
            backgroundSize: '200% 100%', animation: 'shimmer 1.4s infinite',
          }} />
        ))}
      </div>
      <style>{`@keyframes shimmer { 0% { background-position: 200% 0; } 100% { background-position: -200% 0; } }`}</style>
    </div>
  );
}

function computeStats(days) {
  const planned = days.filter((d) => d.has_plan);
  let mealsPlanned = 0;
  let prepMins = 0;
  const ingredientSet = new Set();

  for (const d of planned) {
    for (const mt of ['breakfast', 'lunch', 'dinner']) {
      const m = d.meals?.[mt];
      if (!m || !m.name) continue;
      mealsPlanned += 1;
      if (typeof m.prep_mins === 'number') prepMins += m.prep_mins;
      for (const ing of (m.ingredients || [])) {
        ingredientSet.add(String(ing).toLowerCase().split(/[,(]/)[0].trim());
      }
    }
  }

  const cookTime = prepMins
    ? prepMins >= 60 ? `~${Math.round(prepMins / 60)}h` : `${prepMins}m`
    : '';

  return {
    mealsPlanned,
    ingredients: ingredientSet.size || 0,
    cookTime,
  };
}

// ── Styles ────────────────────────────────────────────────────────
const shellStyle = {
  marginTop: 8, marginBottom: 14,
  display: 'flex', flexDirection: 'column', gap: 14,
};

const headerStyle = { padding: '0 16px' };
const eyebrowStyle = {
  fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
  color: '#2D5F4C', fontWeight: 500, marginBottom: 6,
};
const titleStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontWeight: 500, fontSize: 24,
  lineHeight: 1.1, letterSpacing: '-0.02em', margin: 0, marginBottom: 4, color: '#1A1A1A',
};
const titleAccentStyle = { fontStyle: 'italic', fontWeight: 400, color: '#2D5F4C' };
const subStyle = { fontSize: 12.5, color: '#5A5A5A', lineHeight: 1.5 };

const statsStripStyle = {
  margin: '0 16px',
  background: '#1A1A1A', color: '#FAF7F5',
  borderRadius: 16, padding: '12px 14px',
  display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8,
};
const statCellStyle = { display: 'flex', flexDirection: 'column', gap: 2 };
const statValueStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 18, fontWeight: 500, letterSpacing: '-0.01em',
};
const statLabelStyle = {
  fontSize: 9.5, letterSpacing: '0.06em', textTransform: 'uppercase',
  color: 'rgba(247,244,238,0.55)',
};

const insightStyle = {
  margin: '0 16px',
  background: '#E8F0EB',
  border: '1px solid rgba(45,95,76,0.15)',
  borderRadius: 14, padding: '12px 14px',
  display: 'flex', gap: 10, alignItems: 'flex-start',
};
const insightIconStyle = {
  width: 28, height: 28, borderRadius: 8,
  background: '#2D5F4C', color: 'white',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexShrink: 0,
};
const insightTextStyle = { fontSize: 12, color: '#1A1A1A', lineHeight: 1.45 };

const errorBannerStyle = {
  margin: '0 16px',
  background: '#FEF2F2',
  border: '1px solid #FCA5A5',
  borderRadius: 12, padding: '10px 14px',
  display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10,
  fontSize: 12, color: '#7F1D1D',
};
const errorRetryStyle = {
  background: '#7F1D1D', color: 'white', border: 'none',
  borderRadius: 999, padding: '6px 12px',
  fontSize: 11, fontWeight: 500, cursor: 'pointer', flexShrink: 0,
};

const trackStyle = {
  display: 'flex', overflowX: 'auto', scrollSnapType: 'x mandatory',
  gap: 12, padding: '4px 16px 12px',
  scrollbarWidth: 'none',
  WebkitOverflowScrolling: 'touch',
};

const cardStyle = {
  flex: '0 0 calc(100% - 30px)',
  scrollSnapAlign: 'center',
  background: 'white',
  border: '1px solid #E8E3D8',
  borderRadius: 22,
  padding: '18px 18px 16px',
  display: 'flex', flexDirection: 'column', gap: 14,
  position: 'relative', overflow: 'hidden',
  minHeight: 280,
};
const cardTodayStyle = {
  ...cardStyle,
  background: 'linear-gradient(135deg, #E8F0EB 0%, #FFFFFF 60%)',
  borderColor: 'rgba(45,95,76,0.25)',
};

const cardHeadStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
};
const cardDayNameStyle = {
  fontFamily: 'Fraunces, Georgia, serif',
  fontSize: 22, fontWeight: 500, lineHeight: 1, letterSpacing: '-0.01em',
};
const cardDayAccentStyle = { fontStyle: 'italic', fontWeight: 400, color: '#2D5F4C' };
const cardDayDateStyle = {
  fontSize: 10.5, color: '#9A9A9A',
  marginTop: 4, letterSpacing: '0.06em', textTransform: 'uppercase', fontWeight: 500,
};

const mealsStackStyle = { display: 'flex', flexDirection: 'column', gap: 8 };
const mealRowStyle = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '10px 12px',
  background: 'rgba(255,255,255,0.5)',
  border: '1px solid #E8E3D8',
  borderRadius: 14,
  cursor: 'pointer',
  textAlign: 'left',
  font: 'inherit',
  color: 'inherit',
  width: '100%',
  transition: 'transform 0.15s ease, border-color 0.15s ease',
};
const mealIconStyle = {
  width: 32, height: 32, borderRadius: 10,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexShrink: 0,
};
const mealInfoStyle = { flex: 1, minWidth: 0 };
const mealTypeStyle = {
  fontSize: 9.5, letterSpacing: '0.08em', textTransform: 'uppercase',
  color: '#9A9A9A', fontWeight: 500, marginBottom: 2,
};
const mealTitleStyle = {
  fontSize: 13, fontWeight: 500, color: '#1A1A1A', lineHeight: 1.25,
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
};
const mealMetaStyle = { fontSize: 11, color: '#5A5A5A', marginTop: 2 };

const cardFooterStyle = {
  display: 'flex', gap: 6, marginTop: 4,
};
const cardActionStyle = {
  flex: 1,
  background: 'transparent',
  border: '1px solid #E8E3D8',
  borderRadius: 999,
  padding: '8px 12px',
  fontSize: 11.5,
  color: '#5A5A5A', fontWeight: 500,
  cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 4,
};
const cardSavePrimaryStyle = {
  ...cardActionStyle,
  background: '#1A1A1A',
  borderColor: '#1A1A1A',
  color: '#FAF7F5',
};

const editRowStyle = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '10px 12px',
  background: 'rgba(255,255,255,0.5)',
  border: '1px solid #E8E3D8',
  borderRadius: 14,
};
const editInputStyle = {
  width: '100%',
  marginTop: 2,
  background: 'white',
  border: '1px solid #E8E3D8',
  borderRadius: 8,
  padding: '6px 8px',
  fontSize: 13,
  color: '#1A1A1A',
  fontFamily: 'inherit',
  outline: 'none',
};
const saveErrorStyle = {
  fontSize: 11.5, color: '#7F1D1D', padding: '4px 4px 0',
};

const dotsRowStyle = {
  display: 'flex', justifyContent: 'center', gap: 6, padding: '4px 0',
};
const dotStyle = {
  width: 6, height: 6, borderRadius: '50%',
  background: '#E8E3D8', border: 'none', padding: 0, cursor: 'pointer',
  transition: 'all 0.2s',
};
const dotActiveStyle = {
  ...dotStyle,
  width: 18, borderRadius: 4, background: '#1A1A1A',
};

const lockBtnStyle = {
  margin: '4px 16px 0',
  background: '#1A1A1A', color: '#FAF7F5',
  border: 'none', borderRadius: 999,
  padding: '14px 20px',
  fontSize: 14, fontWeight: 500, cursor: 'pointer',
  boxShadow: '0 4px 16px rgba(26,26,26,0.15)',
};

const emptyStyle = {
  padding: '20px 0', textAlign: 'center',
  fontSize: 12, color: '#9A9A9A', fontStyle: 'italic',
};
