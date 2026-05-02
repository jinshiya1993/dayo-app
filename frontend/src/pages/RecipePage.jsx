import { useEffect, useState } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { plans, members as membersApi, profile as profileApi } from '../services/api';

const MEAL_LABELS = { breakfast: 'BREAKFAST', lunch: 'LUNCH', snack: 'SNACK', dinner: 'DINNER' };
const MEAL_TIMES = { breakfast: '07:00', lunch: '13:00', snack: '17:00', dinner: '19:00' };
const MEAL_HERO_BG = {
  breakfast: 'linear-gradient(135deg, #FFE9C7 0%, #FFD8A6 100%)',
  lunch: 'linear-gradient(135deg, #FFD8C2 0%, #F5C9A8 100%)',
  snack: 'linear-gradient(135deg, #F5E6FF 0%, #E8D4F5 100%)',
  dinner: 'linear-gradient(135deg, #F5DEC4 0%, #E8C9A0 100%)',
};

// Pick an emoji that matches the dish, based on keywords in the name.
// Falls back to a meal-type emoji, then a generic plate. The mapping is
// ordered — first match wins, so put more-specific keywords above general.
const DISH_EMOJI_RULES = [
  // Specific dishes / proteins
  // Indian/savory pancakes and griddle items first — they often contain
  // "dal" or "lentil" in the name and would otherwise match the lentil
  // rule below and render as a paella pan.
  { match: /pancake|waffle|crepe|cheela|chilla|chila|dosa|uttapam|adai|appam/i, emoji: '🥞' },
  { match: /paratha|roti|naan|chapati|chappathi|chappati|puri|poori|kulcha|flatbread|tortilla/i, emoji: '🫓' },
  { match: /idli|idly/i, emoji: '🍚' },
  { match: /upma|poha|khichdi/i, emoji: '🥣' },
  { match: /noodle|ramen|pho|spaghetti|pasta|lasagna|maggi/i, emoji: '🍜' },
  { match: /sushi|sashimi|maki|nigiri/i, emoji: '🍣' },
  { match: /pizza/i, emoji: '🍕' },
  { match: /burger/i, emoji: '🍔' },
  { match: /taco/i, emoji: '🌮' },
  { match: /burrito|wrap|roll(?!ed)|kati/i, emoji: '🌯' },
  { match: /sandwich|toast|bread|bagel|panini/i, emoji: '🥪' },
  { match: /salad|greens|kale|lettuce/i, emoji: '🥗' },
  { match: /soup|stew|broth|chowder|rasam|sambar/i, emoji: '🍲' },
  { match: /curry|biryani|pulao|pilaf|risotto|fried rice|jeera rice|rice bowl/i, emoji: '🍛' },
  { match: /\brice\b|congee|porridge|oatmeal|oats|kanji/i, emoji: '🍚' },
  { match: /dumpling|momo|gyoza|samosa|pakora/i, emoji: '🥟' },
  { match: /omelet|omelette|frittata|scrambl|fried egg|boiled egg|poached egg|eggs?\b/i, emoji: '🍳' },
  { match: /tofu|paneer|chickpea|lentil|dal\b|bean curd/i, emoji: '🥘' },
  { match: /chicken|tikka|tandoori|kebab|skewer/i, emoji: '🍗' },
  { match: /steak|beef|mutton|lamb|stir-?fry/i, emoji: '🥩' },
  { match: /fish|salmon|tuna|prawn|shrimp|seafood/i, emoji: '🐟' },
  { match: /smoothie|shake|juice|lassi/i, emoji: '🥤' },
  { match: /yogurt|yoghurt|curd/i, emoji: '🥣' },
  { match: /fruit|berries|apple|banana|mango|papaya/i, emoji: '🍓' },
  { match: /cake|brownie|cookie|dessert|halwa|kheer|payasam/i, emoji: '🍰' },
  { match: /tea|chai|coffee|latte/i, emoji: '☕' },
];

const MEAL_TYPE_EMOJI_FALLBACK = { breakfast: '🥐', lunch: '🍽️', snack: '🍪', dinner: '🍽️' };

function pickDishEmoji(name, mealType) {
  const dish = name || '';
  const rule = DISH_EMOJI_RULES.find((r) => r.match.test(dish));
  if (rule) return rule.emoji;
  return MEAL_TYPE_EMOJI_FALLBACK[mealType] || '🍽️';
}

const ROLE_AVATAR_BG = {
  partner: '#C97D5A', child: '#C9A84C', helper: '#6B5B95',
  parent: '#1A1A1A', grandparent: '#1A1A1A', sibling: '#C97D5A',
  roommate: '#1A1A1A', other: '#1A1A1A',
};

export default function RecipePage() {
  const navigate = useNavigate();
  const location = useLocation();

  // Prefer meal data passed via state (instant load). Fall back to fetching
  // today's plan if the user landed here directly via URL.
  const stateMeal = location.state?.meal;
  const stateMealType = location.state?.mealType;
  const planDate = location.state?.planDate;

  const [meal, setMeal] = useState(stateMeal || null);
  const [mealType, setMealType] = useState(stateMealType || '');
  const [memberList, setMemberList] = useState([]);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(!stateMeal);
  const [extractingIngredients, setExtractingIngredients] = useState(false);
  const [extractingSteps, setExtractingSteps] = useState(false);

  useEffect(() => {
    membersApi.list().then((res) => {
      if (!res.error && Array.isArray(res)) setMemberList(res);
    });
    profileApi.get().then((res) => {
      if (!res.error) setProfileData(res);
    });
    if (stateMeal) return;
    // Fallback: fetch today's plan and try to find a meal.
    const today = planDate || new Date().toISOString().slice(0, 10);
    plans.get(today).then((res) => {
      if (res.error) { setLoading(false); return; }
      const data = res.plan_data || {};
      const meals = data.mom_meals || data.meals || {};
      const firstKey = Object.keys(meals).find((k) => meals[k]?.name);
      if (firstKey) {
        setMeal(meals[firstKey]);
        setMealType(firstKey);
      }
      setLoading(false);
    });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-fetch ingredients when missing. Fires once per meal load — backend
  // is idempotent (returns cached ingredients if already saved).
  useEffect(() => {
    if (!meal || !planDate || !mealType) return;
    if (Array.isArray(meal.ingredients) && meal.ingredients.length > 0) return;
    if (extractingIngredients) return;
    setExtractingIngredients(true);
    plans.extractIngredients(planDate, mealType).then((res) => {
      if (!res.error && res.meal) setMeal(res.meal);
      setExtractingIngredients(false);
    });
  }, [meal?.name, planDate, mealType]); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-fetch cooking steps + kcal when missing. Same idempotent pattern as
  // ingredients. Waits for ingredients so the steps prompt can use them as
  // context. Backend fills in whichever fields are missing.
  useEffect(() => {
    if (!meal || !planDate || !mealType) return;
    const hasSteps = Array.isArray(meal.steps) && meal.steps.length > 0;
    const hasKcal = typeof meal.kcal === 'number' && meal.kcal > 0;
    if (hasSteps && hasKcal) return;
    if (extractingSteps || extractingIngredients) return;
    setExtractingSteps(true);
    plans.extractRecipe(planDate, mealType).then((res) => {
      if (!res.error && res.meal) setMeal(res.meal);
      setExtractingSteps(false);
    });
  }, [meal?.name, meal?.ingredients?.length, planDate, mealType]); // eslint-disable-line react-hooks/exhaustive-deps

  const avatarMap = (() => {
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
  })();

  if (loading) {
    return <div className="loading"><div className="spinner" />Loading recipe…</div>;
  }

  if (!meal) {
    return (
      <div style={shellStyle}>
        <TopBar onBack={() => navigate(-1)} />
        <div style={{ padding: '40px 20px', textAlign: 'center', color: '#5A5A5A' }}>
          No recipe to show. <button onClick={() => navigate('/')} style={linkStyle}>Back to dashboard</button>
        </div>
      </div>
    );
  }

  const ingredients = Array.isArray(meal.ingredients) ? meal.ingredients : [];
  const pairings = Array.isArray(meal.pairings) ? meal.pairings : [];
  const steps = Array.isArray(meal.steps) ? meal.steps : [];
  const time = MEAL_TIMES[mealType] || '';
  const label = MEAL_LABELS[mealType] || mealType.toUpperCase();
  const emoji = pickDishEmoji(meal.name, mealType);
  const heroBg = MEAL_HERO_BG[mealType] || 'linear-gradient(135deg, #FFF8F0 0%, #F5E6D3 100%)';

  const hasIngredients = ingredients.length > 0;
  const hasSteps = steps.length > 0;

  return (
    <div style={shellStyle}>
      <TopBar onBack={() => navigate(-1)} />

      <div style={contentWrapStyle}>
        <article style={unifiedCardStyle}>
          <div style={{ ...cardHeroStyle, background: heroBg }}>
            <div style={heroEmojiStyle}>{emoji}</div>
          </div>

          <div style={cardBodyStyle}>
            <div style={eyebrowStyle}>
              {label}{time ? ` · ${time}` : ''}
            </div>
            <h1 style={titleStyle}>{scrubHalal(meal.name)}</h1>

            <div style={metaRowStyle}>
              {meal.prep_mins ? (
                <div style={metaPillStyle}><ClockIcon /> {meal.prep_mins} min</div>
              ) : null}
              {meal.kcal ? (
                <div style={metaPillStyle}>🔥 {meal.kcal} kcal</div>
              ) : null}
              {hasIngredients && (
                <div style={metaPillStyle}>{ingredients.length} ingredients</div>
              )}
              {hasSteps && (
                <div style={metaPillStyle}>{steps.length} steps</div>
              )}
              {Array.isArray(meal.tags) && meal.tags.slice(0, 3).map((tag, idx) => (
                <div key={`tag-${idx}`} style={tagPillStyle}>{tag}</div>
              ))}
            </div>

            <div style={sectionHeaderStyle}>Ingredients</div>
            {hasIngredients ? (
              <ul style={ingredientsGridStyle}>
                {ingredients.map((ing, idx) => (
                  <li key={idx} style={ingredientCellStyle}>
                    <span style={ingredientCheckStyle} aria-hidden>✓</span>
                    <span style={ingredientItemNameStyle}>{scrubHalal(ing)}</span>
                  </li>
                ))}
              </ul>
            ) : extractingIngredients ? (
              <div style={ingredientsLoadingStyle}>
                <span style={{
                  display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
                  border: '2px solid #EDE8E3', borderTopColor: '#C2855A',
                  animation: 'spin 0.9s linear infinite',
                }} />
                Reading the recipe…
              </div>
            ) : (
              <p style={emptyStyle}>
                Couldn't pull an ingredient list for this meal.
              </p>
            )}

            <div style={cardDividerStyle} />

            <div style={sectionHeaderStyle}>Recipe</div>
            {(() => {
              if (hasSteps) {
                return (
                  <ul style={stepsListStyle}>
                    {steps.map(scrubHalal).map((step, idx) => (
                      <li key={idx} style={stepItemStyle}>
                        <span style={stepBulletStyle} />
                        <span style={stepTextStyle}>{step}</span>
                      </li>
                    ))}
                  </ul>
                );
              }
              if (extractingSteps) {
                return (
                  <div style={ingredientsLoadingStyle}>
                    <span style={{
                      display: 'inline-block', width: 14, height: 14, borderRadius: '50%',
                      border: '2px solid #EDE8E3', borderTopColor: '#C2855A',
                      animation: 'spin 0.9s linear infinite',
                    }} />
                    Writing the recipe…
                  </div>
                );
              }
              const recipeBullets = sentencesFrom(meal.description).map(scrubHalal);
              if (recipeBullets.length === 0) {
                return (
                  <p style={emptyStyle}>
                    No step-by-step recipe yet. Tap Swap on the meal card to regenerate with detailed instructions.
                  </p>
                );
              }
              return (
                <ul style={stepsListStyle}>
                  {recipeBullets.map((step, idx) => (
                    <li key={idx} style={stepItemStyle}>
                      <span style={stepBulletStyle} />
                      <span style={stepTextStyle}>{step}</span>
                    </li>
                  ))}
                </ul>
              );
            })()}

            {pairings.length > 0 && (
              <>
                <div style={cardDividerStyle} />
                <div style={sectionHeaderStyle}>Pair with</div>
                <p style={{ fontSize: 12.5, color: '#5A5A5A', marginBottom: 12, lineHeight: 1.5 }}>
                  Same main dish, different sides per person — one cooking session.
                </p>
                {pairings.map((p, idx) => (
                  <PairingRow key={idx} pairing={p} avatarMap={avatarMap} />
                ))}
              </>
            )}
          </div>
        </article>
      </div>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
    </div>
  );
}

function PairingRow({ pairing, avatarMap }) {
  const names = (pairing.for || '')
    .split(/[,&]/)
    .map((s) => s.trim())
    .filter(Boolean);

  return (
    <div style={pairingRowStyle}>
      <div style={{ display: 'flex', flexShrink: 0 }}>
        {names.slice(0, 3).map((n, i) => {
          const meta = avatarMap.get(n.toLowerCase()) || {
            initial: initialOf(n), bg: '#9A9A9A',
          };
          return (
            <div
              key={i}
              title={meta.name || n}
              style={{
                ...pairingAvatarStyle,
                background: meta.bg,
                marginLeft: i === 0 ? 0 : -8,
                zIndex: 3 - i,
              }}
            >
              {meta.initial}
            </div>
          );
        })}
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={pairingWithStyle}>{pairing.with}</div>
        {pairing.why && <div style={pairingWhyStyle}>{pairing.why}</div>}
      </div>
    </div>
  );
}

function TopBar({ onBack }) {
  return (
    <div style={topBarStyle}>
      <button onClick={onBack} style={backBtnStyle} aria-label="Back">
        <BackIcon />
      </button>
      <div style={{ fontSize: 12, color: '#5A5A5A' }}>Recipe</div>
      <div style={{ width: 40 }} />
    </div>
  );
}

function ClockIcon() {
  return (
    <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="12" cy="12" r="10" />
      <polyline points="12 6 12 12 16 14" />
    </svg>
  );
}
function BackIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6" />
    </svg>
  );
}
function initialOf(s) {
  return (s || '?').trim().charAt(0).toUpperCase() || '?';
}

// Pull a leading quantity (e.g. "200g", "2 cups", "1/2 tsp") off an
// ingredient string so the recipe page can render quantity and item in
// two columns. Returns { qty, item } — qty may be empty if no quantity.
// Strip the word "Halal" from user-facing text. The dietary restriction
// is already satisfied by ingredient choice — labelling things "Halal X"
// reads awkwardly for non-Muslim members of the household. Drops the
// word + any trailing/leading whitespace it leaves behind.
function scrubHalal(text) {
  if (!text) return '';
  return text
    .replace(/\bhalal\b[\s,-]*/gi, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

// Split a recipe paragraph into bullet-friendly sentences. Trims, drops
// empties, keeps periods off the end so the list looks clean.
function sentencesFrom(text) {
  if (!text) return [];
  return text
    .split(/(?<=[.!?])\s+/)
    .map((s) => s.trim().replace(/[.!?]+$/, ''))
    .filter((s) => s.length > 3);
}

// ── Styles ──────────────────────────────────────────────────────
const shellStyle = {
  display: 'flex', flexDirection: 'column', minHeight: '100dvh',
  maxWidth: 430, margin: '0 auto', background: '#FAF7F5',
  paddingBottom: 80,
};
const topBarStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '12px 16px',
};
const backBtnStyle = {
  width: 40, height: 40, borderRadius: '50%', background: 'white',
  border: '1px solid #EDE8E3', display: 'flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', color: '#1A1A1A',
};
const contentWrapStyle = { padding: '4px 16px 24px' };
const unifiedCardStyle = {
  background: 'white',
  border: '1px solid #E8E3D8',
  borderRadius: 20,
  overflow: 'hidden',
  boxShadow: '0 1px 2px rgba(0,0,0,0.03), 0 8px 24px rgba(0,0,0,0.04)',
};
const cardHeroStyle = {
  height: 180,
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  position: 'relative',
};
const heroEmojiStyle = {
  fontSize: 96,
  lineHeight: 1,
  filter: 'drop-shadow(0 4px 12px rgba(0,0,0,0.08))',
};
const cardBodyStyle = { padding: '20px 18px 22px' };
const eyebrowStyle = {
  fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
  color: '#C2855A', fontWeight: 500, marginBottom: 12, marginTop: 8,
};
const titleStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontWeight: 500, fontSize: 28,
  lineHeight: 1.15, letterSpacing: '-0.02em', marginBottom: 10, color: '#1A1A1A',
};
const metaRowStyle = {
  display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 22,
};
const metaPillStyle = {
  display: 'inline-flex', alignItems: 'center', gap: 6,
  padding: '6px 12px', borderRadius: 999, background: 'white',
  border: '1px solid #E8E3D8', fontSize: 12, color: '#1A1A1A',
};
const tagPillStyle = {
  display: 'inline-flex', alignItems: 'center',
  padding: '6px 12px', borderRadius: 999,
  background: 'rgba(194,133,90,0.10)',
  border: '1px solid rgba(194,133,90,0.25)',
  fontSize: 12, color: '#8A4A1F', fontWeight: 500,
};
const sectionHeaderStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 16, fontWeight: 500,
  letterSpacing: '-0.01em', marginBottom: 12, color: '#1A1A1A',
};
const cardDividerStyle = {
  height: 1, background: '#EDE8E3', margin: '18px 0 16px',
};
const ingredientsGridStyle = {
  margin: 0, padding: 0, listStyle: 'none',
  display: 'grid',
  gridTemplateColumns: '1fr 1fr',
  columnGap: 14,
  rowGap: 10,
};
const ingredientCellStyle = {
  display: 'flex',
  alignItems: 'flex-start',
  gap: 8,
  fontSize: 13.5,
  color: '#1A1A1A',
  lineHeight: 1.4,
  minWidth: 0,
};
const ingredientCheckStyle = {
  flexShrink: 0,
  width: 18,
  height: 18,
  borderRadius: '50%',
  background: '#FFF8F0',
  border: '1px solid rgba(194,133,90,0.3)',
  color: '#C2855A',
  fontSize: 11,
  fontWeight: 600,
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  marginTop: 1,
  lineHeight: 1,
};
const ingredientItemNameStyle = {
  color: '#1A1A1A',
  wordBreak: 'break-word',
};
const emptyStyle = {
  fontSize: 13, color: '#9A9A9A', fontStyle: 'italic',
  margin: 0, lineHeight: 1.5, marginBottom: 12,
};
const ingredientsLoadingStyle = {
  display: 'flex', alignItems: 'center', gap: 10,
  fontSize: 13, color: '#5A5A5A', padding: '4px 0',
};
const stepsListStyle = {
  margin: 0, padding: 0, listStyle: 'none',
  display: 'flex', flexDirection: 'column', gap: 14,
};
const stepItemStyle = {
  display: 'flex', alignItems: 'flex-start', gap: 12,
};
const stepBulletStyle = {
  flexShrink: 0,
  width: 6, height: 6, borderRadius: '50%',
  background: '#C2855A',
  marginTop: 9,
};
const stepTextStyle = {
  fontSize: 14, color: '#1A1A1A', lineHeight: 1.5,
};

const pairingRowStyle = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '10px 0', borderBottom: '1px dashed rgba(194,133,90,0.18)',
};
const pairingAvatarStyle = {
  width: 28, height: 28, borderRadius: '50%', color: 'white',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  fontFamily: 'Fraunces, Georgia, serif', fontWeight: 500, fontSize: 12,
  border: '2px solid white',
};
const pairingWithStyle = { fontSize: 13.5, fontWeight: 500, color: '#1A1A1A', lineHeight: 1.25 };
const pairingWhyStyle = { fontSize: 11.5, color: '#5A5A5A', marginTop: 2, lineHeight: 1.3 };
const linkStyle = {
  background: 'transparent', border: 'none', color: '#C2855A',
  fontSize: 13, textDecoration: 'underline', cursor: 'pointer', padding: 0,
};
