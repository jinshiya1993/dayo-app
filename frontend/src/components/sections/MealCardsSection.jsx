import { useState, useEffect, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { plans, meals as mealsApi, members as membersApi } from '../../services/api';

const MEAL_TIMES = { breakfast: '07:00', lunch: '13:00', snack: '17:00', dinner: '19:00' };
const MEAL_LABELS = { breakfast: 'BREAKFAST', lunch: 'LUNCH', snack: 'SNACK', dinner: 'DINNER' };

// Condition tags read as clinical / redundant when every meal already
// respects the user's profile. Filter from display while keeping the
// data on the meal (still drives grocery + chat behaviour).
const HIDDEN_TAG_PATTERNS = [
  /pcos/i, /diabet/i, /heart-?healthy/i, /anti-?inflammatory/i,
  /low gi/i, /postpartum/i, /lactation/i,
];
const isVisibleTag = (t) => !HIDDEN_TAG_PATTERNS.some((re) => re.test(t || ''));

const ROLE_AVATAR_BG = {
  partner: '#C97D5A',
  child: '#C9A84C',
  helper: '#6B5B95',
  parent: '#1A1A1A',
  grandparent: '#1A1A1A',
  sibling: '#C97D5A',
  roommate: '#1A1A1A',
  other: '#1A1A1A',
};

export default function MealCardsSection({ data, planData, planDate, onPlanUpdate, profileData }) {
  const navigate = useNavigate();
  const meals = useMemo(() => normalizeMeals(data || {}), [data]);
  const banner = (planData && planData.meal_health_banner) || '';
  const todayKey = `meal_banner_shown_${new Date().toISOString().slice(0, 10)}`;
  const alreadyShownToday = sessionStorage.getItem(todayKey) === 'true';

  const [showBanner, setShowBanner] = useState(false);
  const [fading, setFading] = useState(false);
  const [loading, setLoading] = useState(null);
  const [favourites, setFavourites] = useState(new Set());
  const [memberList, setMemberList] = useState([]);
  const [featuredKey, setFeaturedKey] = useState(() => pickFeatured(meals));
  // Enrichments fetched lazily for old meals missing kcal/tags/pairings.
  // Keyed by meal_type, merged on top of `meals[k]` for display.
  const [enrichments, setEnrichments] = useState({});

  useEffect(() => {
    if (!banner || alreadyShownToday) return;
    sessionStorage.setItem(todayKey, 'true');
    setShowBanner(true);
    setFading(false);
    const fadeTimer = setTimeout(() => setFading(true), 4000);
    const hideTimer = setTimeout(() => setShowBanner(false), 5000);
    return () => { clearTimeout(fadeTimer); clearTimeout(hideTimer); };
  }, [banner]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    mealsApi.listFavourites().then(res => {
      if (!res.error && Array.isArray(res)) setFavourites(new Set(res.map(f => f.meal_name)));
    });
    membersApi.list().then(res => {
      if (!res.error && Array.isArray(res)) setMemberList(res);
    });
  }, []);

  // Re-pick featured when the meals object changes (e.g. after a swap).
  useEffect(() => { setFeaturedKey(pickFeatured(meals)); }, [meals.breakfast?.name, meals.lunch?.name, meals.dinner?.name, meals.snack?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-backfill kcal/tags/pairings/steps for old meals that predate the
  // schema. Backend is idempotent and runs in the background — we drop the
  // returned meal into `enrichments` so the meta lines populate without
  // refetching the whole plan. Drops on swap because the meal name changes.
  useEffect(() => {
    if (!planDate) return;
    ['breakfast', 'lunch', 'dinner', 'snack'].forEach((k) => {
      const m = meals[k];
      if (!m || !m.name) return;
      // Skip enrichment for legacy snack rows synthesized from a string
      // array — they have no real recipe context, only a joined label.
      if (k === 'snack' && m._legacy) return;
      const enriched = enrichments[k];
      const merged = enriched && enriched._for === m.name ? { ...m, ...enriched } : m;
      const hasKcal = typeof merged.kcal === 'number' && merged.kcal > 0;
      const hasTags = Array.isArray(merged.tags) && merged.tags.length > 0;
      const hasSteps = Array.isArray(merged.steps) && merged.steps.length > 0;
      if (hasKcal && hasTags && hasSteps) return;
      if (enriched && enriched._for === m.name && enriched._inflight) return;
      setEnrichments((prev) => ({ ...prev, [k]: { _for: m.name, _inflight: true } }));
      plans.extractRecipe(planDate, k).then((res) => {
        if (!res.error && res.meal) {
          setEnrichments((prev) => ({ ...prev, [k]: { _for: m.name, ...res.meal } }));
        } else {
          setEnrichments((prev) => ({ ...prev, [k]: { _for: m.name, _failed: true } }));
        }
      });
    });
  }, [planDate, meals.breakfast?.name, meals.lunch?.name, meals.dinner?.name, meals.snack?.name]); // eslint-disable-line react-hooks/exhaustive-deps

  const mergedMeal = (k) => {
    const m = meals[k];
    if (!m) return null;
    const e = enrichments[k];
    if (!e || e._for !== m.name) return m;
    const { _for, _inflight, _failed, ...rest } = e;
    return { ...m, ...rest };
  };

  // Build a name → avatar lookup. Includes the user themselves so AI can
  // reference them by name.
  const avatarMap = useMemo(() => {
    const map = new Map();
    const userName = profileData?.display_name;
    if (userName) {
      map.set(userName.trim().toLowerCase(), {
        name: userName, initial: initialOf(userName), bg: '#1A1A1A',
      });
    }
    memberList.forEach((m) => {
      if (!m.name) return;
      map.set(m.name.trim().toLowerCase(), {
        name: m.name, initial: initialOf(m.name),
        bg: ROLE_AVATAR_BG[m.role] || '#1A1A1A',
      });
    });
    return map;
  }, [memberList, profileData?.display_name]);

  async function handleSwap(mealType) {
    setLoading(mealType);
    const res = await plans.swapMeal(planDate, mealType);
    if (!res.error && res.plan_data) onPlanUpdate(res.plan_data);
    setLoading(null);
  }

  async function handleFavourite(mealType) {
    const meal = meals[mealType];
    if (!meal) return;
    const res = await mealsApi.toggleFavourite(meal.name, mealType, meal.description || '');
    if (res.error) return;
    setFavourites(prev => {
      const next = new Set(prev);
      if (res.favourited) next.add(meal.name);
      else next.delete(meal.name);
      return next;
    });
  }

  const orderedKeys = ['breakfast', 'lunch', 'snack', 'dinner'].filter((k) => meals[k]);
  const featured = featuredKey ? mergedMeal(featuredKey) : null;
  const subKeys = orderedKeys.filter((k) => k !== featuredKey);
  const subColumns = subKeys.length >= 3 ? '1fr 1fr 1fr' : '1fr 1fr';

  return (
    <>
      <div style={mealsHeaderStyle}>
        <div style={mealsTitleStyle}>Today's meals</div>
        <button onClick={() => navigate('/plan-week')} style={planWeekLinkStyle}>
          Plan week →
        </button>
      </div>

      {showBanner && banner && (
        <div style={{
          margin: '0 16px 10px', padding: '8px 14px',
          background: 'linear-gradient(135deg, #FFF8F0, #FFF0F5)',
          borderRadius: 12, border: '0.5px solid #EDE8E3',
          opacity: fading ? 0 : 1, transition: 'opacity 1s ease-out',
        }}>
          <span style={{ fontSize: 12, color: '#9B4000', lineHeight: 1.5, fontStyle: 'italic' }}>
            {banner}
          </span>
        </div>
      )}

      {featured && (
        <div style={{ padding: '0 16px', marginBottom: 10 }}>
          <FeaturedMealCard
            mealType={featuredKey}
            meal={featured}
            isFav={favourites.has(featured.name)}
            isLoading={loading === featuredKey}
            avatarMap={avatarMap}
            onFavourite={() => handleFavourite(featuredKey)}
            onSwap={() => handleSwap(featuredKey)}
            onViewRecipe={() => navigate('/recipe', {
              state: { meal: featured, mealType: featuredKey, planDate },
            })}
          />
        </div>
      )}

      {subKeys.length > 0 && (
        <div style={{
          display: 'grid', gridTemplateColumns: subColumns, gap: 10,
          padding: '0 16px', marginBottom: 14,
        }}>
          {subKeys.map((k) => (
            <SubMealCard
              key={k}
              mealType={k}
              meal={mergedMeal(k)}
              isLoading={loading === k}
              onClick={() => setFeaturedKey(k)}
            />
          ))}
        </div>
      )}

      <style>{`
        .meal-pill {
          transition: transform 0.15s ease, background 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
        }
        .meal-pill:hover:not(:disabled) {
          transform: translateY(-1px);
          box-shadow: 0 4px 12px rgba(26,26,26,0.08);
        }
        .meal-pill:not(.meal-pill--primary):not(.meal-pill--saved):hover:not(:disabled) {
          background: #FFF8F0;
          border-color: rgba(194,133,90,0.4);
        }
        .meal-pill--primary:hover:not(:disabled) {
          background: #2A2A2A;
        }
        .meal-pill--saved:hover:not(:disabled) {
          background: #FAEBDD;
          border-color: rgba(194,133,90,0.6);
        }
        .meal-pill:active:not(:disabled) {
          transform: translateY(0);
          box-shadow: none;
        }
      `}</style>
    </>
  );
}

function FeaturedMealCard({
  mealType, meal, isFav, isLoading, avatarMap,
  onFavourite, onSwap, onViewRecipe,
}) {
  const time = MEAL_TIMES[mealType] || '';
  const pairings = Array.isArray(meal.pairings) ? meal.pairings : [];

  return (
    <div style={featuredCardStyle}>
      <div style={mealTimeRowStyle}>
        <ClockIcon /> {MEAL_LABELS[mealType]} · {time}
      </div>

      <div style={featuredNameStyle}>{meal.name}</div>
      {(() => {
        const tags = (Array.isArray(meal.tags) ? meal.tags : [])
          .filter(isVisibleTag)
          .slice(0, 2);
        const parts = [
          ...tags,
          meal.prep_mins ? `${meal.prep_mins} min` : null,
          meal.kcal ? `${meal.kcal} kcal` : null,
        ].filter(Boolean);
        return parts.length > 0 ? (
          <div style={featuredMetaStyle}>{parts.join(' · ')}</div>
        ) : null;
      })()}

      {pairings.length > 0 && <PairingsFootnote pairings={pairings} />}

      <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
        <button className="meal-pill meal-pill--primary" onClick={onViewRecipe} style={mealPillStyle('primary')}>
          📖 View recipe
        </button>
        <button className="meal-pill" onClick={onSwap} disabled={isLoading} style={mealPillStyle()}>
          {isLoading ? '…' : '🔄 Swap'}
        </button>
        <button className={`meal-pill ${isFav ? 'meal-pill--saved' : ''}`} onClick={onFavourite} style={mealPillStyle(isFav ? 'saved' : null)}>
          {isFav ? '✓ Saved' : '＋ Add to list'}
        </button>
      </div>
    </div>
  );
}

function SubMealCard({ mealType, meal, isLoading, onClick }) {
  const time = MEAL_TIMES[mealType] || '';
  const meta = [
    meal.prep_mins ? `${meal.prep_mins} min` : null,
    meal.kcal ? `${meal.kcal} kcal` : null,
  ].filter(Boolean).join(' · ');
  return (
    <button onClick={onClick} style={subCardStyle}>
      <div style={subTimeStyle}>{MEAL_LABELS[mealType]} · {time}</div>
      <div style={subNameStyle} title={meal.name}>{isLoading ? '…' : meal.name}</div>
      {meta && <div style={subMetaStyle}>{meta}</div>}
    </button>
  );
}

// Side-pairings footnote — single small muted line per group.
function PairingsFootnote({ pairings }) {
  return (
    <div style={footnoteStyle}>
      {pairings.map((p, idx) => {
        const names = (p.for || '').split(/[,&]/).map((s) => s.trim()).filter(Boolean).join(' & ');
        return (
          <div key={idx} style={footnoteLineStyle}>
            🍚 <span style={footnoteSideStyle}>{p.with}</span>
            {names ? ` for ${names}` : ''}
            {p.why ? <span style={footnoteWhyStyle}> — {p.why}</span> : null}
          </div>
        );
      })}
    </div>
  );
}

function ClockIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
         style={{ verticalAlign: '-1px', marginRight: 4 }}>
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}

function initialOf(s) {
  return (s || '?').trim().charAt(0).toUpperCase() || '?';
}

// Pick which meal goes in the featured slot — the next upcoming one based
// on time of day. Windows: breakfast until 11:30, lunch until 16:00, snack
// 16:00–18:00 (when a snack exists), dinner after 18:00. Falls back to
// whatever meal is available if a slot is missing.
function pickFeatured(meals) {
  const now = new Date();
  const minutes = now.getHours() * 60 + now.getMinutes();

  if (minutes < 11 * 60 + 30 && meals.breakfast) return 'breakfast';
  if (minutes < 16 * 60 && meals.lunch) return 'lunch';
  if (minutes < 18 * 60) {
    if (meals.snack) return 'snack';
    if (meals.dinner) return 'dinner';
  }
  if (meals.dinner) return 'dinner';

  return ['breakfast', 'lunch', 'snack', 'dinner'].find((k) => meals[k]) || null;
}

// Normalize the meals payload so `snack` is always a meal object (or absent).
// Old DayPlans serialize snacks as an array of strings — keep only the first
// entry as the day's snack (we only want a single snack now). Marked _legacy
// so the lazy-enrich effect skips it (no real recipe to extract).
function normalizeMeals(raw) {
  const out = { ...raw };
  if (!out.snack && Array.isArray(raw.snacks) && raw.snacks.length > 0) {
    out.snack = { name: String(raw.snacks[0]).trim(), _legacy: true };
  }
  return out;
}

// ── Styles ──────────────────────────────────────────────────────
const mealsHeaderStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '0 16px', marginBottom: 10,
};
const mealsTitleStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 16, fontWeight: 500,
  letterSpacing: '-0.01em',
};
const planWeekLinkStyle = {
  fontSize: 12, color: '#C2855A', fontWeight: 500, background: 'transparent',
  border: 'none', cursor: 'pointer', padding: 0,
};

const featuredCardStyle = {
  background: 'linear-gradient(135deg, #FFF8F0 0%, #FFFFFF 100%)',
  border: '1px solid rgba(194,133,90,0.2)',
  borderRadius: 16, padding: 16,
};
const mealTimeRowStyle = {
  display: 'flex', alignItems: 'center',
  fontSize: 11, letterSpacing: '0.06em', textTransform: 'uppercase',
  color: '#5A5A5A', fontWeight: 500, marginBottom: 8,
};
const featuredNameStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 17, fontWeight: 500,
  letterSpacing: '-0.01em', lineHeight: 1.25, color: '#1A1A1A', marginBottom: 6,
};
const featuredMetaStyle = {
  fontSize: 12, color: '#5A5A5A', lineHeight: 1.4,
};

const footnoteStyle = {
  marginTop: 10,
  display: 'flex', flexDirection: 'column', gap: 2,
};
const footnoteLineStyle = {
  fontSize: 11, color: '#5A5A5A', lineHeight: 1.5,
};
const footnoteSideStyle = { fontWeight: 500, color: '#1A1A1A' };
const footnoteWhyStyle = { color: '#9A9A9A' };

function mealPillStyle(variant) {
  if (variant === 'primary') {
    return {
      padding: '8px 14px', borderRadius: 999, border: 'none',
      background: '#1A1A1A', color: 'white',
      fontSize: 12, fontWeight: 500, cursor: 'pointer',
    };
  }
  if (variant === 'saved') {
    return {
      padding: '8px 14px', borderRadius: 999,
      border: '0.5px solid rgba(194,133,90,0.4)',
      background: '#FFF8F0', color: '#C2855A',
      fontSize: 12, fontWeight: 600, cursor: 'pointer',
    };
  }
  return {
    padding: '8px 14px', borderRadius: 999,
    border: '0.5px solid #E8E3D8',
    background: 'white', color: '#1A1A1A',
    fontSize: 12, fontWeight: 500, cursor: 'pointer',
  };
}

const subCardStyle = {
  background: 'white', border: '1px solid #E8E3D8', borderRadius: 14,
  padding: 12, cursor: 'pointer', textAlign: 'left',
  display: 'flex', flexDirection: 'column', gap: 4,
  minWidth: 0,
};
const subTimeStyle = {
  fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase',
  color: '#9A9A9A', fontWeight: 500,
};
const subNameStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 13, fontWeight: 500,
  lineHeight: 1.25, color: '#1A1A1A',
  display: '-webkit-box',
  WebkitLineClamp: 2,
  WebkitBoxOrient: 'vertical',
  overflow: 'hidden',
  wordBreak: 'break-word',
};
const subMetaStyle = { fontSize: 11, color: '#5A5A5A' };
