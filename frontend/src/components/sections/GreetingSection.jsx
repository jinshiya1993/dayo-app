export default function GreetingSection({ profileData, onPlanDay, planning }) {
  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

  return (
    <div style={{
      background: '#1a1a1a', borderRadius: 14, padding: '20px',
      margin: '0 16px 12px', display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    }}>
      <div>
        <div style={{ color: '#888', fontSize: 12 }}>Your plan is ready</div>
        <div style={{ color: 'white', fontFamily: 'Georgia, serif', fontSize: 20, fontWeight: 700, margin: '2px 0' }}>
          {profileData?.display_name || 'there'}
        </div>
        <div style={{ color: '#888', fontSize: 12 }}>{dateStr}</div>
      </div>
      <button onClick={onPlanDay} disabled={planning} style={{
        background: '#C2855A', color: 'white', border: 'none', borderRadius: 20,
        padding: '10px 18px', fontSize: 12, fontWeight: 600, cursor: 'pointer',
        opacity: planning ? 0.6 : 1,
      }}>
        {planning ? 'Planning...' : 'Plan my day'}
      </button>
    </div>
  );
}
