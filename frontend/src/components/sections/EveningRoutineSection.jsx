import { useState } from 'react';

export default function EveningRoutineSection({ data }) {
  const routine = data || {};
  const tasks = routine.tasks || [];
  const [checked, setChecked] = useState([]);
  if (tasks.length === 0) return null;

  function toggle(idx) {
    setChecked((prev) => prev.includes(idx) ? prev.filter((i) => i !== idx) : [...prev, idx]);
  }

  return (
    <>
      <div className="section-header">
        <div className="section-title">Evening Routine</div>
        <span style={{ fontSize: 12, color: '#888' }}>from {routine.start || '18:00'}</span>
      </div>
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{ background: '#1a1a1a', borderRadius: 14, padding: '14px' }}>
          {tasks.map((task, idx) => (
            <div key={idx} onClick={() => toggle(idx)} style={{
              display: 'flex', alignItems: 'center', gap: 10, padding: '8px 0',
              borderBottom: idx < tasks.length - 1 ? '0.5px solid #333' : 'none',
              cursor: 'pointer',
            }}>
              <div style={{
                width: 20, height: 20, borderRadius: '50%',
                border: checked.includes(idx) ? 'none' : '1.5px solid #555',
                background: checked.includes(idx) ? '#C2855A' : 'transparent',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', fontSize: 11, flexShrink: 0,
              }}>
                {checked.includes(idx) && '✓'}
              </div>
              <span style={{
                fontSize: 13, color: checked.includes(idx) ? '#666' : 'white',
                textDecoration: checked.includes(idx) ? 'line-through' : 'none',
              }}>
                {task}
              </span>
            </div>
          ))}
        </div>
      </div>
    </>
  );
}
