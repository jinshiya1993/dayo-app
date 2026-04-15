import { useState } from 'react';

export default function ErrandsSection({ data }) {
  const errands = data || [];
  const [checked, setChecked] = useState([]);
  if (errands.length === 0) return null;

  function toggle(idx) {
    setChecked((prev) => prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]);
  }

  return (
    <>
      <div className="section-header">
        <div className="section-title">Errands</div>
      </div>
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{ background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3', padding: '4px 14px' }}>
          {errands.map((errand, idx) => {
            const name = typeof errand === 'string' ? errand : errand.title || '';
            return (
              <div key={idx} onClick={() => toggle(idx)} style={{
                display: 'flex', alignItems: 'center', gap: 10, padding: '10px 0',
                borderBottom: idx < errands.length - 1 ? '0.5px solid #EDE8E3' : 'none',
                cursor: 'pointer',
              }}>
                <div style={{
                  width: 20, height: 20, borderRadius: 6,
                  border: checked.includes(idx) ? 'none' : '1.5px solid #EDE8E3',
                  background: checked.includes(idx) ? '#C2855A' : 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', fontSize: 11, flexShrink: 0,
                }}>
                  {checked.includes(idx) && '✓'}
                </div>
                <span style={{
                  fontSize: 14,
                  textDecoration: checked.includes(idx) ? 'line-through' : 'none',
                  color: checked.includes(idx) ? '#AAA' : '#1a1a1a',
                }}>
                  {name}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
