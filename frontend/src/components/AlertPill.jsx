const typeStyles = {
  meeting: { bg: '#F5F0FF', color: '#6B46C1' },
  leave_time: { bg: '#FFF3CD', color: '#856404' },
  exercise: { bg: '#F0FFF8', color: '#2D7A5B' },
  study: { bg: '#F0F7FF', color: '#1E40AF' },
  prep_meal: { bg: '#FFF8F0', color: '#9B4000' },
  pickup: { bg: '#FFF3CD', color: '#856404' },
  class: { bg: '#FFF0F0', color: '#DC3545' },
  general: { bg: '#FFF3CD', color: '#856404' },
};

const typeEmojis = {
  meeting: '💼', leave_time: '🚗', exercise: '🏋️', study: '📚',
  prep_meal: '🍳', pickup: '🏫', class: '📖', general: '🔔',
};

export default function AlertPill({ reminders }) {
  if (!reminders || reminders.length === 0) return null;

  const now = new Date();

  // Filter: only show reminders within 30 min from now
  // (remind_at is in the past up to now, or in the future up to 30 min)
  const active = reminders.filter((r) => {
    if (!r.remind_at) return false;
    const remindTime = new Date(r.remind_at);
    const diffMin = (remindTime - now) / 60000;
    // Show if reminder is between -5 min (just passed) and +30 min (upcoming)
    return diffMin >= -5 && diffMin <= 30;
  });

  if (active.length === 0) return null;

  const next = active[0];
  const style = typeStyles[next.reminder_type] || typeStyles.general;
  const emoji = typeEmojis[next.reminder_type] || '🔔';

  let timeStr = '';
  if (next.remind_at) {
    const d = new Date(next.remind_at);
    const diffMin = Math.round((d - now) / 60000);
    if (diffMin <= 0) {
      timeStr = 'Now';
    } else if (diffMin < 60) {
      timeStr = `in ${diffMin} min`;
    } else {
      timeStr = d.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', hour12: true });
    }
  }

  return (
    <div style={{ background: style.bg, borderRadius: 12, padding: '12px 16px', margin: '0 16px 12px', display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ fontSize: 18 }}>{emoji}</span>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 600, fontSize: 13, color: style.color }}>{next.title}</div>
        {timeStr && <div style={{ fontSize: 11, color: style.color, opacity: 0.7 }}>{timeStr}</div>}
      </div>
      {active.length > 1 && (
        <span style={{ fontSize: 11, color: style.color, opacity: 0.7 }}>+{active.length - 1} more</span>
      )}
    </div>
  );
}
