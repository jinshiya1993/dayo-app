import { useState } from 'react';

const urgencyStyles = {
  today: { bg: '#FFF0F0', color: '#DC3545', label: 'Due today' },
  'this-week': { bg: '#F0F7FF', color: '#3B82F6', label: 'This week' },
  someday: { bg: '#F0FFF8', color: '#2D7A5B', label: 'Someday' },
};

export default function PrioritiesSection({ data }) {
  const priorities = data || [];
  const [done, setDone] = useState([]);
  if (priorities.length === 0) return null;

  function toggle(num) {
    setDone((prev) => prev.includes(num) ? prev.filter((n) => n !== num) : [...prev, num]);
  }

  return (
    <>
      <div className="section-header">
        <div className="section-title">Today's Priorities</div>
      </div>
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{ background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3', padding: '4px 14px' }}>
          {priorities.map((p, idx) => {
            const isDone = done.includes(p.number) || p.done;
            const urg = urgencyStyles[p.urgency] || urgencyStyles.someday;
            return (
              <div key={idx} style={{
                display: 'flex', alignItems: 'flex-start', gap: 10, padding: '12px 0',
                borderBottom: idx < priorities.length - 1 ? '0.5px solid #EDE8E3' : 'none',
              }}>
                <div onClick={() => toggle(p.number)} style={{
                  width: 24, height: 24, borderRadius: 8, marginTop: 1,
                  background: isDone ? '#C2855A' : '#FAF7F5',
                  border: isDone ? 'none' : '1.5px solid #EDE8E3',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  color: 'white', fontSize: 12, fontWeight: 700, cursor: 'pointer', flexShrink: 0,
                }}>
                  {isDone ? '✓' : p.number}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{
                    fontWeight: 600, fontSize: 14,
                    textDecoration: isDone ? 'line-through' : 'none',
                    color: isDone ? '#AAA' : '#1a1a1a',
                  }}>
                    {p.title}
                  </div>
                  {p.notes && <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{p.notes}</div>}
                </div>
                <span style={{
                  fontSize: 10, fontWeight: 600, padding: '2px 8px', borderRadius: 8,
                  background: isDone ? '#F0FFF8' : urg.bg,
                  color: isDone ? '#2D7A5B' : urg.color,
                }}>
                  {isDone ? 'Done' : urg.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </>
  );
}
