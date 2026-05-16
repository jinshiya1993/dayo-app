export default function GreetingSection({ profileData }) {
  const now = new Date();
  const dateStr = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });
  const name = profileData?.display_name;

  return (
    <div style={{
      background: '#1a1a1a', borderRadius: 14, padding: '20px',
      margin: '0 16px 12px',
    }}>
      <div style={{ color: '#888', fontSize: 12 }}>Your plan is ready</div>
      <div style={{ color: 'white', fontFamily: 'Georgia, serif', fontSize: 20, fontWeight: 700, margin: '2px 0' }}>
        {name ? name[0].toUpperCase() + name.slice(1) : 'there'}
      </div>
      <div style={{ color: '#888', fontSize: 12 }}>{dateStr}</div>
    </div>
  );
}
