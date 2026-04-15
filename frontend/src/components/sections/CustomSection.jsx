import { useState, useEffect, useCallback } from 'react';
import { customSection as api } from '../../services/api';

// Color palette for custom section icons — distinct from housework
const SECTION_COLORS = {
  default:    { dot: '#C2855A', bg: '#FDF2EB' },
  water:      { dot: '#5B9BD5', bg: '#EBF4FB' },
  garden:     { dot: '#6BBF6B', bg: '#EBF8EB' },
  fitness:    { dot: '#E86B6B', bg: '#FDECEC' },
  meditation: { dot: '#9B7FD4', bg: '#F3EEFB' },
  reading:    { dot: '#D4A057', bg: '#FBF3EB' },
  pet:        { dot: '#E8A06B', bg: '#FDF2EB' },
  budget:     { dot: '#5BBFA0', bg: '#EBF8F4' },
  clean:      { dot: '#6BB5BF', bg: '#EBF6F8' },
  study:      { dot: '#7F9BD4', bg: '#EEF2FB' },
};

function getSectionColor(sectionKey, label) {
  const text = (sectionKey + ' ' + label).toLowerCase();
  for (const [keyword, colors] of Object.entries(SECTION_COLORS)) {
    if (keyword !== 'default' && text.includes(keyword)) return colors;
  }
  return SECTION_COLORS.default;
}

export default function CustomSection({ sectionKey, label }) {
  const [csList, setCsList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  // Capitalize each word in the label
  const displayLabel = label.replace(/\b\w/g, c => c.toUpperCase());
  const colors = getSectionColor(sectionKey, label);

  const loadCurrent = useCallback(async () => {
    setLoading(true);
    const res = await api.current(sectionKey);
    if (!res.error) {
      setCsList(res);
      setLoading(false);
    } else {
      setLoading(false);
      setGenerating(true);
      const genRes = await api.generate(sectionKey);
      if (!genRes.error) setCsList(genRes);
      setGenerating(false);
    }
  }, [sectionKey]);

  useEffect(() => { loadCurrent(); }, [loadCurrent]);

  async function handleToggle(taskId) {
    if (!csList) return;
    const res = await api.toggleTask(sectionKey, csList.id, taskId);
    if (!res.error) {
      setCsList(prev => ({
        ...prev,
        tasks: prev.tasks.map(t => t.id === taskId ? { ...t, completed: res.completed } : t),
      }));
    }
  }

  // --- Render ---
  if (loading) return null;

  if (generating) {
    return (
      <>
        <div className="section-header">
          <div className="section-title">{displayLabel}</div>
        </div>
        <div style={{
          margin: '0 16px 16px', padding: '20px 16px', textAlign: 'center',
          background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
        }}>
          <div className="spinner" style={{ margin: '0 auto 8px', width: 24, height: 24 }} />
          <div style={{ fontSize: 13, color: '#888' }}>Setting up {label.toLowerCase()}...</div>
        </div>
      </>
    );
  }

  if (!csList) return null;

  const tasks = csList.tasks || [];
  const total = tasks.length;
  const done = tasks.filter(t => t.completed).length;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  const allDone = total > 0 && done === total;

  return (
    <>
      <div className="section-header">
        <div className="section-title">{displayLabel}</div>
      </div>

      {allDone ? (
        <div style={{
          margin: '0 16px 16px', background: colors.bg, borderRadius: 14,
          padding: '28px 14px', textAlign: 'center',
        }}>
          <div style={{
            width: 48, height: 48, borderRadius: '50%', background: colors.dot,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            margin: '0 auto 10px', color: 'white', fontSize: 20, fontWeight: 700,
          }}>
            {'\u2713'}
          </div>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', marginBottom: 4 }}>
            {displayLabel} finished!
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>
            All {total} done for today
          </div>
        </div>
      ) : (
        <div style={{
          margin: '0 16px 16px', background: 'white', borderRadius: 14,
          border: '0.5px solid #EDE8E3', overflow: 'hidden',
        }}>
          {/* Task rows */}
          <div style={{ padding: '6px 14px' }}>
            {tasks.map((task, idx) => (
              <div
                key={task.id}
                onClick={() => handleToggle(task.id)}
                style={{
                  display: 'flex', alignItems: 'center', gap: 12,
                  padding: '12px 0',
                  opacity: task.completed ? 0.5 : 1,
                  transition: 'opacity 0.25s',
                  borderBottom: idx < tasks.length - 1 ? '0.5px dashed #f0ece7' : 'none',
                  cursor: 'pointer',
                }}
              >
                {/* Colored dot icon */}
                <div style={{
                  width: 32, height: 32, borderRadius: 10,
                  background: task.completed ? '#f0ece7' : colors.bg,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, transition: 'background 0.25s',
                }}>
                  {task.completed ? (
                    <span style={{ fontSize: 13, color: '#aaa' }}>{'\u2713'}</span>
                  ) : (
                    <div style={{
                      width: 10, height: 10, borderRadius: '50%',
                      background: colors.dot,
                    }} />
                  )}
                </div>

                {/* Name */}
                <div style={{
                  flex: 1, fontSize: 13.5,
                  fontWeight: task.completed ? 400 : 500,
                  color: task.completed ? '#bbb' : '#1a1a1a',
                  textDecoration: task.completed ? 'line-through' : 'none',
                  lineHeight: 1.4,
                }}>
                  {task.name}
                </div>
              </div>
            ))}

            {/* Empty state */}
            {total === 0 && (
              <div style={{ fontSize: 13, color: '#aaa', textAlign: 'center', padding: '16px 0' }}>
                Generate a plan to see today's tasks.
              </div>
            )}
          </div>

          {/* Progress bar at bottom */}
          {total > 0 && (
            <div style={{
              padding: '10px 14px 12px', background: '#FDFBF9',
              borderTop: '0.5px solid #f0ece7',
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <div style={{
                flex: 1, height: 4, borderRadius: 2, background: '#EDE8E3',
              }}>
                <div style={{
                  height: 4, borderRadius: 2, background: colors.dot,
                  width: `${percent}%`, transition: 'width 0.3s',
                }} />
              </div>
              <span style={{ fontSize: 11, color: '#888', whiteSpace: 'nowrap' }}>
                {done}/{total}
              </span>
            </div>
          )}
        </div>
      )}
    </>
  );
}
