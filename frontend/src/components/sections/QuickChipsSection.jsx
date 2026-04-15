import { useNavigate } from 'react-router-dom';

export default function QuickChipsSection({ chips }) {
  const navigate = useNavigate();
  if (!chips || chips.length === 0) return null;

  return (
    <div style={{ padding: '0 16px', marginBottom: 24 }}>
      <div style={{ display: 'flex', gap: 8, overflowX: 'auto', paddingBottom: 4 }}>
        {chips.map((chip) => (
          <button key={chip} onClick={() => navigate('/chat', { state: { prefill: chip } })}
            style={{
              padding: '9px 16px', borderRadius: 20, border: '0.5px solid #EDE8E3',
              background: 'white', fontSize: 12, whiteSpace: 'nowrap', cursor: 'pointer',
              color: '#1a1a1a', fontWeight: 500,
            }}>
            {chip}
          </button>
        ))}
      </div>
    </div>
  );
}
