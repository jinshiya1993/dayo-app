export default function EndOfDaySection({ data }) {
  if (!data) return null;

  // Format time
  const [h, m] = (data || '18:00').split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const displayH = h > 12 ? h - 12 : h;
  const timeStr = `${displayH}:${String(m).padStart(2, '0')} ${ampm}`;

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: '#FFF3CD', borderRadius: 14, padding: '16px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{ fontSize: 24 }}>🌅</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 14, color: '#856404' }}>Stop work at {timeStr}</div>
          <div style={{ fontSize: 12, color: '#856404', marginTop: 2 }}>Your evening is protected</div>
        </div>
      </div>
    </div>
  );
}
