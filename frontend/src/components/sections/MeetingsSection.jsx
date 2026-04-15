export default function MeetingsSection({ data }) {
  const meetings = data || [];
  if (meetings.length === 0) return null;

  return (
    <>
      <div className="section-header">
        <div className="section-title">Meetings</div>
        <span style={{ fontSize: 12, color: '#888' }}>{meetings.length} today</span>
      </div>
      <div className="meal-scroll">
        {meetings.map((m, i) => (
          <div key={i} style={{
            minWidth: 160, maxWidth: 160, background: 'white', borderRadius: 14,
            border: '0.5px solid #EDE8E3', padding: '14px', flexShrink: 0,
          }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: '#C2855A', marginBottom: 4 }}>{m.time}</div>
            <div style={{ fontWeight: 600, fontSize: 13, lineHeight: 1.3, marginBottom: 4 }}>{m.title}</div>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 6 }}>{m.duration}</div>
            {m.platform && (
              <div style={{ display: 'inline-block', fontSize: 10, background: '#F0F7FF', color: '#3B82F6', padding: '2px 8px', borderRadius: 8, fontWeight: 600, marginBottom: 4 }}>
                {m.platform}
              </div>
            )}
            {m.note && (
              <div style={{ fontSize: 11, color: '#F59E0B', marginTop: 4 }}>⚡ {m.note}</div>
            )}
          </div>
        ))}
      </div>
    </>
  );
}
