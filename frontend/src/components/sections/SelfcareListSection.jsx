export default function SelfcareListSection({ data }) {
  if (!data) return null;

  // Handle both object and array formats
  const items = Array.isArray(data) ? data : [data];
  if (items.length === 0 || !items[0].activity) return null;

  return (
    <>
      <div className="section-header">
        <div className="section-title">Self-care Windows</div>
      </div>
      <div style={{ display: 'flex', gap: 10, padding: '0 16px', marginBottom: 16, overflowX: 'auto' }}>
        {items.map((item, i) => (
          <div key={i} style={{
            minWidth: 140, background: i % 2 === 0 ? '#FFF8F0' : '#F5F0FF',
            borderRadius: 14, padding: '14px', border: '0.5px solid #EDE8E3', flexShrink: 0,
          }}>
            <div style={{ fontSize: 22, marginBottom: 6 }}>{['🛁', '☕', '📖', '🎧'][i % 4]}</div>
            <div style={{ fontWeight: 600, fontSize: 13, color: i % 2 === 0 ? '#C2855A' : '#6B46C1' }}>
              {item.activity}
            </div>
            <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
              {item.time} · {item.duration}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
