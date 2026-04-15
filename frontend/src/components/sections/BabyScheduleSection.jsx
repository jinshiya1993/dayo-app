export default function BabyScheduleSection({ data, baby }) {
  const schedule = data || [];
  if (schedule.length === 0) return null;

  const babyName = baby?.name || 'Baby';

  const typeConfig = {
    feed:  { emoji: '🍼', color: '#C2855A', bg: '#FFF8F0', label: 'Feed' },
    sleep: { emoji: '😴', color: '#6B46C1', bg: '#F5F0FF', label: 'Nap' },
    nappy: { emoji: '👶', color: '#2D7A5B', bg: '#F0FFF8', label: 'Nappy' },
    play:  { emoji: '🧸', color: '#3B82F6', bg: '#F0F7FF', label: 'Play' },
  };

  // Find the next upcoming item
  const now = new Date();
  const nowMins = now.getHours() * 60 + now.getMinutes();

  return (
    <>
      <div className="section-header">
        <div className="section-title">{babyName}'s Day</div>
      </div>
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{ background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3', padding: '4px 0' }}>
          {schedule.map((item, i) => {
            const cfg = typeConfig[item.type] || typeConfig.play;
            const [h, m] = (item.time || '00:00').split(':').map(Number);
            const itemMins = h * 60 + m;
            const isNext = itemMins > nowMins;
            const isPast = itemMins <= nowMins;

            return (
              <div key={i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 14px',
                borderBottom: i < schedule.length - 1 ? '0.5px solid #EDE8E3' : 'none',
                opacity: isPast ? 0.5 : 1,
              }}>
                <div style={{ fontSize: 12, color: '#888', minWidth: 40 }}>{item.time}</div>
                <div style={{
                  width: 32, height: 32, borderRadius: 10,
                  background: cfg.bg, display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 16,
                }}>
                  {cfg.emoji}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 13, color: cfg.color }}>{cfg.label}</div>
                  <div style={{ fontSize: 11, color: '#888' }}>{item.details}</div>
                </div>
                {item.end_time && (
                  <span style={{ fontSize: 10, color: '#888' }}>until {item.end_time}</span>
                )}
                {isNext && i === schedule.findIndex((s) => { const [sh, sm] = (s.time || '00:00').split(':').map(Number); return sh * 60 + sm > nowMins; }) && (
                  <span style={{ fontSize: 9, background: cfg.bg, color: cfg.color, padding: '2px 8px', borderRadius: 8, fontWeight: 600 }}>Next</span>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
