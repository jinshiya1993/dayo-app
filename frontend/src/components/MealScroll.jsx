const mealEmojis = {
  breakfast: '🥞',
  lunch: '🍛',
  dinner: '🍲',
};

const mainMealOrder = ['breakfast', 'lunch', 'dinner'];

export default function MealScroll({ meals }) {
  if (!meals || meals.length === 0) return null;

  const mainMeals = meals
    .filter((m) => mainMealOrder.includes(m.meal_type))
    .sort((a, b) => mainMealOrder.indexOf(a.meal_type) - mainMealOrder.indexOf(b.meal_type));

  const snacks = meals.filter((m) => m.meal_type === 'snack');

  return (
    <>
      <div className="section-header">
        <div className="section-title">Today's Meals</div>
      </div>

      {/* Main meal cards — breakfast, lunch, dinner */}
      <div className="meal-scroll">
        {mainMeals.map((meal) => (
          <div className="meal-card" key={meal.id}>
            <div className={`meal-emoji-area ${meal.meal_type}`}>
              {mealEmojis[meal.meal_type] || '🍽'}
            </div>
            <div className="meal-info">
              <div className="meal-time-badge">{meal.meal_type}</div>
              <div className="meal-name">{meal.name}</div>
              {meal.prep_time_minutes > 0 && (
                <div className="meal-duration">{meal.prep_time_minutes} min prep</div>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Snack strip — small pill below meals */}
      {snacks.length > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 12 }}>
          <div style={{
            display: 'flex', alignItems: 'center', gap: 6,
            background: '#F5F0FF', borderRadius: 10, padding: '8px 14px',
          }}>
            <span style={{ fontSize: 14 }}>🍪</span>
            <span style={{ fontSize: 12, color: '#6B46C1', fontWeight: 600 }}>Snacks:</span>
            <span style={{ fontSize: 12, color: '#6B46C1' }}>
              {snacks.map((s) => s.name).join('  •  ')}
            </span>
          </div>
        </div>
      )}
    </>
  );
}
