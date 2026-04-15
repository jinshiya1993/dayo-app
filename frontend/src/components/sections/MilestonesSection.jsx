export default function MilestonesSection({ data }) {
  const milestones = data || {};
  const items = milestones.items || [];
  if (items.length === 0) return null;

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: '#FFF8F0', borderRadius: 14, padding: '16px',
        border: '0.5px solid #EDE8E3',
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
          <span style={{ fontSize: 18 }}>🌟</span>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#C2855A' }}>
            Milestones at {milestones.age || 'this stage'}
          </div>
        </div>
        {items.map((item, i) => (
          <div key={i} style={{
            display: 'flex', alignItems: 'flex-start', gap: 8, padding: '6px 0',
          }}>
            <div style={{ width: 6, height: 6, borderRadius: '50%', background: '#C2855A', marginTop: 5, flexShrink: 0 }} />
            <span style={{ fontSize: 13, color: '#9B4000' }}>{item}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
