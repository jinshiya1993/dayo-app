export default function DeepWorkSection({ data }) {
  const dw = data || {};
  if (!dw.title) return null;

  // Calculate progress if within the time range
  const now = new Date();
  const h = now.getHours();
  const m = now.getMinutes();
  const nowMins = h * 60 + m;
  const [sh, sm] = (dw.start || '09:00').split(':').map(Number);
  const [eh, em] = (dw.end || '12:00').split(':').map(Number);
  const startMins = sh * 60 + sm;
  const endMins = eh * 60 + em;
  const totalMins = endMins - startMins;
  const elapsed = Math.max(0, Math.min(totalMins, nowMins - startMins));
  const progress = totalMins > 0 ? (elapsed / totalMins) * 100 : 0;
  const isActive = nowMins >= startMins && nowMins < endMins;

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{ background: '#1a1a1a', borderRadius: 14, padding: '18px' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
          <div style={{ fontSize: 10, color: '#C2855A', fontWeight: 600, textTransform: 'uppercase', letterSpacing: 0.5 }}>
            Deep Work
          </div>
          <div style={{ fontSize: 11, color: '#888' }}>{dw.start} – {dw.end}</div>
        </div>
        <div style={{ color: 'white', fontFamily: 'Georgia, serif', fontSize: 18, fontWeight: 700, marginBottom: 4 }}>
          {dw.title}
        </div>
        {dw.description && <div style={{ color: '#888', fontSize: 12, marginBottom: 10 }}>{dw.description}</div>}
        {isActive && (
          <div style={{ fontSize: 11, color: '#C2855A', marginBottom: 6 }}>
            Protected until {dw.end} — no meetings
          </div>
        )}
        <div style={{ height: 4, borderRadius: 2, background: '#333' }}>
          <div style={{ height: 4, borderRadius: 2, background: '#C2855A', width: `${progress}%`, transition: 'width 0.5s' }} />
        </div>
      </div>
    </div>
  );
}
