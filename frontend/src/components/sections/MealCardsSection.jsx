import { useState, useEffect } from 'react';
import { plans, meals as mealsApi } from '../../services/api';
import WeeklyMealInline from '../WeeklyMealInline';

export default function MealCardsSection({ data, planData, planDate, onPlanUpdate }) {
  const meals = data || {};
  const snacks = meals.snacks || [];
  const banner = (planData && planData.meal_health_banner) || '';
  const todayKey = `meal_banner_shown_${new Date().toISOString().slice(0, 10)}`;
  const alreadyShownToday = sessionStorage.getItem(todayKey) === 'true';
  const [showBanner, setShowBanner] = useState(false);
  const [fading, setFading] = useState(false);
  const [expanded, setExpanded] = useState(null);
  const [loading, setLoading] = useState(null);
  const [showIngredientInput, setShowIngredientInput] = useState(false);
  const [ingredient, setIngredient] = useState('');
  const [favourites, setFavourites] = useState(new Set());
  const [weeklyOpen, setWeeklyOpen] = useState(false);

  const emojis = { breakfast: '🥞', lunch: '🍛', dinner: '🍲' };
  const bgs = { breakfast: '#FFF8F0', lunch: '#F0FFF8', dinner: '#FFF5F0' };

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
      if (!res.error && Array.isArray(res)) {
        setFavourites(new Set(res.map(f => f.meal_name)));
      }
    });
  }, []);

  async function handleSwap(mealType) {
    setLoading(mealType);
    const res = await plans.swapMeal(planDate, mealType);
    if (!res.error && res.plan_data) {
      onPlanUpdate(res.plan_data);
    }
    setLoading(null);
  }

  async function handleSubstitute(mealType) {
    if (!ingredient.trim()) return;
    setLoading(mealType);
    const res = await plans.substituteMeal(planDate, mealType, ingredient.trim());
    if (!res.error && res.plan_data) {
      onPlanUpdate(res.plan_data);
    }
    setLoading(null);
    setShowIngredientInput(false);
    setIngredient('');
  }

  async function handleFavourite(mealType) {
    const meal = meals[mealType];
    if (!meal) return;
    const res = await mealsApi.toggleFavourite(meal.name, mealType, meal.description || '');
    if (!res.error) {
      const added = res.favourited;
      setFavourites(prev => {
        const next = new Set(prev);
        if (added) next.add(meal.name);
        else next.delete(meal.name);
        return next;
      });
    }
  }

  return (
    <>
      <div className="section-header">
        <div className="section-title">Today's Meals</div>
      </div>
      {showBanner && banner && (
        <div style={{
          margin: '0 16px 10px', padding: '8px 14px',
          background: 'linear-gradient(135deg, #FFF8F0, #FFF0F5)',
          borderRadius: 12, border: '0.5px solid #EDE8E3',
          opacity: fading ? 0 : 1,
          transition: 'opacity 1s ease-out',
        }}>
          <span style={{ fontSize: 12, color: '#9B4000', lineHeight: 1.5, fontStyle: 'italic' }}>
            {banner}
          </span>
        </div>
      )}

      <div className="meal-scroll">
        {['breakfast', 'lunch', 'dinner'].map((type) => {
          const meal = meals[type];
          if (!meal) return null;
          const isExpanded = expanded === type;
          const isLoading = loading === type;
          const isFav = favourites.has(meal.name);

          return (
            <div key={type} onClick={() => {
              setExpanded(isExpanded ? null : type);
              setShowIngredientInput(false);
              setIngredient('');
            }} style={{
              minWidth: 150, maxWidth: 150,
              background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
              overflow: 'hidden', flexShrink: 0, cursor: 'pointer',
            }}>
              {/* Emoji area with heart in top-right */}
              <div style={{
                height: 80, display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 36, background: bgs[type], position: 'relative',
              }}>
                {isLoading ? <div className="spinner" style={{ width: 24, height: 24 }} /> : emojis[type]}
                <button
                  onClick={(e) => { e.stopPropagation(); handleFavourite(type); }}
                  style={{
                    position: 'absolute', top: 6, right: 6,
                    background: 'none', border: 'none',
                    width: 26, height: 26, fontSize: 16, cursor: 'pointer',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    filter: isFav ? 'none' : 'grayscale(1) opacity(0.4)',
                    transition: 'filter 0.2s ease',
                  }}
                >
                  📌
                </button>
              </div>

              <div style={{ padding: '10px 12px' }}>
                <div style={{ display: 'inline-block', background: '#FFF8F0', color: '#C2855A', fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 10, marginBottom: 4 }}>
                  {type}
                </div>
                <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3, marginBottom: 2 }}>{meal.name}</div>
                {meal.prep_mins > 0 && <div style={{ fontSize: 11, color: '#888' }}>{meal.prep_mins} min prep</div>}

                {/* Expanded actions — only Swap and No item */}
                {isExpanded && !isLoading && (
                  <div style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 4 }}>
                    <div style={{ display: 'flex', gap: 4 }}>
                      <button
                        onClick={(e) => { e.stopPropagation(); handleSwap(type); }}
                        style={{
                          flex: 1, background: '#FFF8F0', border: '0.5px solid #EDE8E3', borderRadius: 8,
                          padding: '5px 0', fontSize: 10, color: '#9B4000', cursor: 'pointer',
                          fontWeight: 500, textAlign: 'center',
                        }}
                      >
                        🔄 Swap
                      </button>
                      {!showIngredientInput ? (
                        <button
                          onClick={(e) => { e.stopPropagation(); setShowIngredientInput(true); }}
                          style={{
                            flex: 1, background: '#FFF8F0', border: '0.5px solid #EDE8E3', borderRadius: 8,
                            padding: '5px 0', fontSize: 10, color: '#9B4000', cursor: 'pointer',
                            fontWeight: 500, textAlign: 'center',
                          }}
                        >
                          🥄 No item
                        </button>
                      ) : null}
                    </div>

                    {showIngredientInput && (
                      <div onClick={(e) => e.stopPropagation()} style={{ display: 'flex', gap: 4 }}>
                        <input
                          value={ingredient}
                          onChange={(e) => setIngredient(e.target.value)}
                          placeholder="e.g. coconut milk"
                          onKeyDown={(e) => e.key === 'Enter' && handleSubstitute(type)}
                          style={{
                            flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 8,
                            padding: '5px 6px', fontSize: 10, outline: 'none', minWidth: 0,
                          }}
                          autoFocus
                        />
                        <button
                          onClick={() => handleSubstitute(type)}
                          style={{
                            background: '#C2855A', border: 'none', borderRadius: 8,
                            padding: '5px 8px', fontSize: 10, color: 'white', cursor: 'pointer',
                          }}
                        >
                          Go
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {snacks.length > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 14 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: 6, background: '#F5F0FF', borderRadius: 20, padding: '6px 14px' }}>
            <span style={{ fontSize: 13 }}>🍪</span>
            <span style={{ fontSize: 12, color: '#6B46C1', fontWeight: 600 }}>Snacks:</span>
            <span style={{ fontSize: 12, color: '#6B46C1' }}>{snacks.join('  •  ')}</span>
          </div>
        </div>
      )}

      {/* Weekly plan — expandable inline */}
      <div style={{ padding: '0 16px', marginBottom: weeklyOpen ? 6 : 14 }}>
        <div
          onClick={() => setWeeklyOpen(!weeklyOpen)}
          style={{
            display: 'flex', alignItems: 'center', justifyContent: 'space-between',
            background: '#FFF8F0', borderRadius: 12,
            padding: '10px 14px', cursor: 'pointer',
            border: '0.5px solid #EDE8E3',
          }}
        >
          <div>
            <div style={{ fontSize: 13, fontWeight: 600, color: '#C2855A' }}>
              {weeklyOpen ? 'Hide upcoming meals' : 'Upcoming meals'}
            </div>
            <div style={{ fontSize: 11, color: '#888', marginTop: 1 }}>
              {weeklyOpen ? 'Collapse weekly view' : 'Tap to review and edit your week'}
            </div>
          </div>
          <span style={{ fontSize: 16, color: '#C2855A' }}>
            {weeklyOpen ? '↑' : '→'}
          </span>
        </div>
      </div>

      {weeklyOpen && <WeeklyMealInline />}
    </>
  );
}
