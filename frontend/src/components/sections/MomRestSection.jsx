export default function MomRestSection({ data }) {
  const restWindows = data || [];
  if (restWindows.length === 0) return null;

  return (
    <>
      <div className="section-header">
        <div className="section-title">Your Rest Windows</div>
      </div>
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        {restWindows.map((rest, i) => (
          <div key={i} style={{
            background: '#F5F0FF', borderRadius: 14, padding: '14px 16px',
            display: 'flex', alignItems: 'center', gap: 12, marginBottom: 8,
          }}>
            <div style={{
              width: 40, height: 40, borderRadius: 12,
              background: '#E8DCFF', display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20,
            }}>
              😴
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: '#6B46C1' }}>
                Rest at {rest.time}
              </div>
              <div style={{ fontSize: 12, color: '#8B5CF6', marginTop: 2 }}>
                {rest.note} · {rest.duration}
              </div>
            </div>
            <div style={{ fontSize: 20 }}>💤</div>
          </div>
        ))}
      </div>
    </>
  );
}
