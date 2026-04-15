import { useState, useEffect } from 'react';

export default function MealCompactSection({ data, planData }) {
  const meals = data || {};
  const banner = (planData && planData.meal_health_banner) || '';
  const [showBanner, setShowBanner] = useState(!!banner);
  const [fading, setFading] = useState(false);
  const items = [
    { type: 'breakfast', dot: '#F59E0B', label: 'Breakfast' },
    { type: 'lunch', dot: '#2D7A5B', label: 'Lunch' },
    { type: 'dinner', dot: '#DC3545', label: 'Dinner' },
  ];

  useEffect(() => {
    if (!banner) return;
    setShowBanner(true);
    setFading(false);
    const fadeTimer = setTimeout(() => setFading(true), 4000);
    const hideTimer = setTimeout(() => setShowBanner(false), 5000);
    return () => { clearTimeout(fadeTimer); clearTimeout(hideTimer); };
  }, [banner]);

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      {showBanner && banner && (
        <div style={{
          marginBottom: 8, padding: '8px 14px',
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
      <div style={{ background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3', padding: '4px 14px' }}>
        {items.map((item) => {
          const meal = meals[item.type];
          if (!meal) return null;
          return (
            <div key={item.type} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0',
              borderBottom: item.type !== 'dinner' ? '0.5px solid #EDE8E3' : 'none',
            }}>
              <div style={{ width: 8, height: 8, borderRadius: '50%', background: item.dot, flexShrink: 0 }} />
              <span style={{ fontSize: 12, color: '#888', minWidth: 60 }}>{item.label}</span>
              <span style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>{meal.name}</span>
              {meal.prep_mins > 0 && (
                <span style={{ fontSize: 11, color: '#888' }}>{meal.prep_mins}m</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
