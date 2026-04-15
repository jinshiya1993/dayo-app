export default function GreetingStrip({ displayName, onPlanDay, loading }) {
  const now = new Date();
  const hour = now.getHours();
  let greeting = 'Good morning';
  if (hour >= 12 && hour < 17) greeting = 'Good afternoon';
  else if (hour >= 17) greeting = 'Good evening';

  const dateStr = now.toLocaleDateString('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
  });

  return (
    <div className="greeting-strip">
      <div className="greeting-left">
        <div className="greeting-label">{greeting}</div>
        <div className="greeting-name">{displayName || 'there'}</div>
        <div className="greeting-date">{dateStr}</div>
      </div>
      <button className="btn-brand" onClick={onPlanDay} disabled={loading}>
        {loading ? 'Planning...' : 'Plan my day'}
      </button>
    </div>
  );
}
