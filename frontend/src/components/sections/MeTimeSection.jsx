export default function MeTimeSection({ data }) {
  const selfcare = data || {};

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: '#F5EEFF', borderRadius: 14, padding: '16px',
        display: 'flex', alignItems: 'center', gap: 14,
      }}>
        <div style={{
          width: 44, height: 44, borderRadius: 12,
          background: '#E8DCFF', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 22,
        }}>
          🧘
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#6B46C1' }}>Me Time</div>
          <div style={{ fontSize: 12, color: '#8B5CF6', marginTop: 2 }}>
            {selfcare.activity || 'Take a break and relax'}
            {selfcare.time && ` · ${selfcare.time}`}
            {selfcare.duration && ` · ${selfcare.duration}`}
          </div>
        </div>
        <div style={{ fontSize: 11, color: '#8B5CF6', fontWeight: 600 }}>Protected</div>
      </div>
    </div>
  );
}
