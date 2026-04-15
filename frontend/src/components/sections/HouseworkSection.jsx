import { useState, useEffect, useCallback } from 'react';
import { housework as houseworkApi } from '../../services/api';

const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const TASK_KEYWORDS = [
  { keys: ['dish', 'dishwasher', 'plates', 'utensil'], emoji: '🍽️', bg: '#FFF8F0' },
  { keys: ['laundry', 'wash clothes', 'washing machine', 'dryer'], emoji: '🧺', bg: '#FFF5F5' },
  { keys: ['sweep', 'broom', 'floor'], emoji: '🧹', bg: '#F0FFF8' },
  { keys: ['mop', 'mopping'], emoji: '🪣', bg: '#F5F0FF' },
  { keys: ['wipe', 'counter', 'surface', 'table'], emoji: '🧽', bg: '#FFF8E1' },
  { keys: ['bathroom', 'toilet', 'sink', 'shower'], emoji: '🚿', bg: '#FFF5F5' },
  { keys: ['bed', 'sheet', 'pillow', 'blanket'], emoji: '🛏️', bg: '#F0F8FF' },
  { keys: ['trash', 'garbage', 'bin', 'waste', 'throw'], emoji: '🗑️', bg: '#F0FFF8' },
  { keys: ['iron', 'press', 'clothes', 'fold'], emoji: '👕', bg: '#F5F0FF' },
  { keys: ['cook', 'meal', 'lunch', 'dinner', 'breakfast', 'food'], emoji: '🍳', bg: '#FFF8F0' },
  { keys: ['grocery', 'shop', 'buy', 'market', 'store'], emoji: '🛒', bg: '#F0FFF8' },
  { keys: ['vacuum', 'hoover', 'carpet'], emoji: '🧹', bg: '#F0FFF8' },
  { keys: ['toy', 'play', 'tidy', 'kids', 'child'], emoji: '🧸', bg: '#FFF8F0' },
  { keys: ['garden', 'plant', 'water', 'lawn'], emoji: '🌱', bg: '#F0FFF8' },
  { keys: ['dust', 'polish', 'furniture'], emoji: '✨', bg: '#FFF8E1' },
  { keys: ['pet', 'dog', 'cat', 'feed'], emoji: '🐾', bg: '#FFF8F0' },
  { keys: ['window', 'glass', 'mirror'], emoji: '🪟', bg: '#F0F8FF' },
  { keys: ['organize', 'sort', 'declutter', 'arrange'], emoji: '📦', bg: '#F5F0FF' },
];

const DEFAULT_ICON = { emoji: '✅', bg: '#F0FFF8' };

function getTaskIcon(taskName) {
  const lower = taskName.toLowerCase();
  for (const entry of TASK_KEYWORDS) {
    if (entry.keys.some(k => lower.includes(k))) {
      return { emoji: entry.emoji, bg: entry.bg };
    }
  }
  return DEFAULT_ICON;
}

export default function HouseworkSection({ profileData }) {
  const [hwList, setHwList] = useState(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [showAddInput, setShowAddInput] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [newTaskName, setNewTaskName] = useState('');
  const [duplicateMsg, setDuplicateMsg] = useState('');

  // Template management
  const [showTemplates, setShowTemplates] = useState(false);
  const [templates, setTemplates] = useState([]);
  const [newTemplateName, setNewTemplateName] = useState('');
  const [newTemplateDays, setNewTemplateDays] = useState([]);
  const [showTemplateForm, setShowTemplateForm] = useState(false);

  const isHelper = profileData?.home_help_type === 'partial_help' || profileData?.home_help_type === 'full_maid';

  const loadCurrent = useCallback(async () => {
    setLoading(true);
    const res = await houseworkApi.current();
    if (!res.error) {
      setHwList(res);
      setLoading(false);
    } else {
      setLoading(false);
      setGenerating(true);
      const genRes = await houseworkApi.generate();
      if (!genRes.error) setHwList(genRes);
      setGenerating(false);
    }
  }, []);

  useEffect(() => { loadCurrent(); }, [loadCurrent]);

  async function handleToggleCheck(taskId) {
    if (!hwList) return;
    const res = await houseworkApi.toggleTask(hwList.id, taskId);
    if (!res.error) {
      setHwList(prev => ({
        ...prev,
        tasks: prev.tasks.map(t => t.id === taskId ? { ...t, completed: res.completed } : t),
      }));
    }
  }

  async function handleAddTask() {
    if (!newTaskName.trim() || !hwList) return;
    const res = await houseworkApi.addTask(hwList.id, newTaskName.trim());
    if (res.error === 'already_exists') {
      setDuplicateMsg(res.message);
      setTimeout(() => setDuplicateMsg(''), 2000);
      return;
    }
    if (!res.error) {
      setHwList(prev => ({ ...prev, tasks: [...prev.tasks, res] }));
      setNewTaskName('');
      setShowAddInput(false);
      setDuplicateMsg('');
    }
  }

  async function handleDeleteTask(taskId) {
    if (!hwList) return;
    const res = await houseworkApi.deleteTask(hwList.id, taskId);
    if (!res.error) {
      setHwList(prev => ({
        ...prev,
        tasks: prev.tasks.filter(t => t.id !== taskId),
      }));
    }
  }

  // --- Templates ---
  async function loadTemplates() {
    const res = await houseworkApi.templates();
    if (!res.error && Array.isArray(res)) setTemplates(res);
  }

  async function handleAddTemplate() {
    if (!newTemplateName.trim()) return;
    const res = await houseworkApi.addTemplate(newTemplateName.trim(), newTemplateDays);
    if (!res.error) {
      setTemplates(prev => [...prev, res]);
      setNewTemplateName('');
      setNewTemplateDays([]);
      setShowTemplateForm(false);
    }
  }

  async function handleDeleteTemplate(id) {
    const res = await houseworkApi.deleteTemplate(id);
    if (!res.error) {
      setTemplates(prev => prev.filter(t => t.id !== id));
    }
  }

  function toggleTemplateDay(day) {
    setNewTemplateDays(prev =>
      prev.includes(day) ? prev.filter(d => d !== day) : [...prev, day].sort()
    );
  }

  function handleOpenTemplates() {
    if (!showTemplates) loadTemplates();
    setShowTemplates(!showTemplates);
  }

  function handleShareWhatsApp() {
    if (!hwList) return;
    const unchecked = (hwList.tasks || []).filter(t => !t.completed);
    let text = '🧹 Tasks for today\n\n';
    unchecked.forEach((t, i) => { text += `${i + 1}. ${t.name}\n`; });
    window.open(`https://wa.me/?text=${encodeURIComponent(text)}`, '_blank');
  }

  // --- Render ---
  if (loading) return null;

  if (generating) {
    return (
      <>
        <div className="section-header">
          <div className="section-title">{isHelper ? 'Tasks for Helper' : 'Housework'}</div>
        </div>
        <div style={{
          margin: '0 16px 16px', padding: '20px 16px', textAlign: 'center',
          background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
        }}>
          <div className="spinner" style={{ margin: '0 auto 8px', width: 24, height: 24 }} />
          <div style={{ fontSize: 13, color: '#888' }}>Setting up today's tasks...</div>
        </div>
      </>
    );
  }

  if (!hwList) return null;

  const tasks = hwList.tasks || [];
  const total = tasks.length;
  const done = tasks.filter(t => t.completed).length;
  const percent = total > 0 ? Math.round((done / total) * 100) : 0;

  let progressRight = `${percent}%`;
  if (done > 0 && done === total) progressRight = 'All done!';
  else if (percent >= 80) progressRight = 'Almost there!';

  const allDone = total > 0 && done === total;

  return (
    <>
      {/* Section header — same as Today's Meals */}
      <div className="section-header">
        <div className="section-title">{isHelper ? 'Tasks for Helper' : 'Housework'}</div>
      </div>

      {/* All done state */}
      {allDone ? (
        <div style={{
          margin: '0 16px 16px', background: 'white', borderRadius: 14,
          border: '0.5px solid #EDE8E3', padding: '28px 14px',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 32, marginBottom: 8 }}>🎉</div>
          <div style={{ fontSize: 15, fontWeight: 600, color: '#1a1a1a', marginBottom: 4 }}>
            All tasks done for today!
          </div>
          <div style={{ fontSize: 12, color: '#888' }}>
            {total} task{total !== 1 ? 's' : ''} completed
          </div>
        </div>
      ) : (

      /* Single card containing everything */
      <div style={{
        margin: '0 16px 16px', background: 'white', borderRadius: 14,
        border: '0.5px solid #EDE8E3', padding: '14px',
      }}>
        {/* Progress bar */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
          <span style={{ fontSize: 11, color: '#888' }}>{done} of {total} done</span>
          <span style={{ fontSize: 11, fontWeight: 600, color: '#C2855A' }}>{progressRight}</span>
        </div>
        <div style={{ height: 4, borderRadius: 2, background: '#EDE8E3', marginBottom: 12 }}>
          <div style={{
            height: 4, borderRadius: 2, background: '#C2855A',
            width: `${percent}%`, transition: 'width 0.3s',
          }} />
        </div>

        {/* Task rows */}
        {(showAll ? tasks : tasks.slice(0, 5)).map((task, idx, visible) => {
          const icon = getTaskIcon(task.name);

          return (
            <div
              key={task.id}
              onClick={() => handleToggleCheck(task.id)}
              style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '10px 0',
                opacity: task.completed ? 0.5 : 1,
                transition: 'opacity 0.2s',
                borderBottom: idx < visible.length - 1 ? '0.5px solid #f5f1ed' : 'none',
                cursor: 'pointer',
              }}
            >
              {/* Checkbox */}
              <div style={{
                width: 20, height: 20, borderRadius: 6,
                border: task.completed ? 'none' : '1.5px solid #EDE8E3',
                background: task.completed ? '#C2855A' : 'white',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                color: 'white', fontSize: 11, flexShrink: 0,
              }}>
                {task.completed && '✓'}
              </div>

              {/* Icon */}
              <div style={{
                width: 34, height: 34, borderRadius: 10, background: icon.bg,
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, flexShrink: 0,
              }}>
                {icon.emoji}
              </div>

              {/* Name */}
              <div style={{ flex: 1 }}>
                <div style={{
                  fontSize: 13.5, fontWeight: task.completed ? 400 : 500,
                  color: task.completed ? '#bbb' : '#1a1a1a',
                  textDecoration: task.completed ? 'line-through' : 'none',
                }}>
                  {task.name}
                </div>
              </div>

              {/* Remove button */}
              <div
                onClick={(e) => { e.stopPropagation(); handleDeleteTask(task.id); }}
                style={{
                  width: 22, height: 22, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, color: '#ccc', flexShrink: 0, cursor: 'pointer',
                }}
              >
                ✕
              </div>
            </div>
          );
        })}

        {/* Show more/less toggle */}
        {tasks.length > 5 && (
          <div
            onClick={() => setShowAll(!showAll)}
            style={{
              textAlign: 'center', padding: '8px 0 2px', fontSize: 12,
              color: '#C2855A', cursor: 'pointer', fontWeight: 500,
            }}
          >
            {showAll ? 'Show less' : `Show all ${tasks.length} tasks`}
          </div>
        )}

        {/* Add task, WhatsApp, recurring — only when expanded or <= 5 tasks */}
        {(showAll || tasks.length <= 5) && (
          <>
            {/* Duplicate message */}
            {duplicateMsg && (
              <div style={{ fontSize: 12, color: '#DC3545', marginTop: 6, textAlign: 'center' }}>
                {duplicateMsg}
              </div>
            )}

            {/* Add task */}
            {!showAddInput ? (
              <div
                onClick={() => setShowAddInput(true)}
                style={{
                  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                  border: '1.5px dashed #EDE8E3', borderRadius: 10,
                  padding: 9, marginTop: 12,
                  color: '#aaa', fontSize: 12, cursor: 'pointer',
                }}
              >
                + Add a task
              </div>
            ) : (
              <div style={{ display: 'flex', gap: 6, marginTop: 12 }}>
                <input
                  value={newTaskName}
                  onChange={(e) => setNewTaskName(e.target.value)}
                  placeholder="Task name"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddTask()}
                  style={{
                    flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 8,
                    padding: '8px 10px', fontSize: 13, outline: 'none',
                  }}
                  autoFocus
                />
                <button onClick={handleAddTask} style={{
                  background: '#C2855A', border: 'none', borderRadius: 8,
                  padding: '8px 14px', color: 'white', fontSize: 13, cursor: 'pointer',
                }}>
                  Add
                </button>
              </div>
            )}

            {/* WhatsApp share */}
            <button onClick={handleShareWhatsApp} style={{
              display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
              background: '#25D366', color: 'white', border: 'none', borderRadius: 10,
              padding: 10, marginTop: 10, fontSize: 12, fontWeight: 600,
              width: '100%', cursor: 'pointer',
            }}>
              <span>📱</span> Share via WhatsApp
            </button>
          </>
        )}

        {/* Manage recurring tasks — only when expanded or <= 5 tasks */}
        {(showAll || tasks.length <= 5) && (
        <div
          onClick={handleOpenTemplates}
          style={{
            textAlign: 'center', padding: '8px 0 0', fontSize: 11, color: '#C2855A',
            cursor: 'pointer', fontWeight: 500,
          }}
        >
          {showTemplates ? 'Hide recurring tasks' : 'Manage recurring tasks'}
        </div>
        )}

        {/* Recurring tasks panel */}
        {showTemplates && (showAll || tasks.length <= 5) && (
          <div style={{
            marginTop: 10, padding: 12, background: '#FDFBF9',
            borderRadius: 10, border: '0.5px solid #EDE8E3',
          }}>
            <div style={{ fontSize: 13, fontWeight: 600, marginBottom: 8, color: '#1a1a1a' }}>
              Recurring Tasks
            </div>
            <div style={{ fontSize: 11, color: '#888', marginBottom: 10 }}>
              Auto-added on the days you set
            </div>

            {templates.map(t => (
              <div key={t.id} style={{
                display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                padding: '8px 0', borderBottom: '0.5px solid #EDE8E3',
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>{t.name}</div>
                  <div style={{ fontSize: 11, color: '#888', marginTop: 1 }}>
                    {t.days.length === 0 ? 'Every day' : t.days.map(d => DAY_LABELS[d]).join(', ')}
                  </div>
                </div>
                <button
                  onClick={() => handleDeleteTemplate(t.id)}
                  style={{ background: 'none', border: 'none', fontSize: 10, cursor: 'pointer', color: '#ccc' }}
                >
                  ✕
                </button>
              </div>
            ))}

            {templates.length === 0 && !showTemplateForm && (
              <div style={{ fontSize: 12, color: '#aaa', textAlign: 'center', padding: '8px 0' }}>
                No recurring tasks yet
              </div>
            )}

            {!showTemplateForm ? (
              <button onClick={() => setShowTemplateForm(true)} style={{
                width: '100%', padding: 8, border: '1.5px dashed #EDE8E3', borderRadius: 8,
                background: 'none', color: '#888', fontSize: 12, cursor: 'pointer', marginTop: 8,
              }}>
                + Add recurring task
              </button>
            ) : (
              <div style={{ marginTop: 10, paddingTop: 10, borderTop: '0.5px solid #EDE8E3' }}>
                <input
                  value={newTemplateName}
                  onChange={(e) => setNewTemplateName(e.target.value)}
                  placeholder="Task name (e.g. Clean bathroom)"
                  onKeyDown={(e) => e.key === 'Enter' && handleAddTemplate()}
                  style={{
                    width: '100%', border: '0.5px solid #EDE8E3', borderRadius: 8,
                    padding: '8px 10px', fontSize: 13, outline: 'none', marginBottom: 8,
                  }}
                  autoFocus
                />
                <div style={{ fontSize: 11, color: '#888', marginBottom: 6 }}>
                  Which days? (leave empty for every day)
                </div>
                <div style={{ display: 'flex', gap: 4, marginBottom: 10 }}>
                  {DAY_LABELS.map((label, idx) => (
                    <button
                      key={idx}
                      onClick={() => toggleTemplateDay(idx)}
                      style={{
                        width: 36, height: 30, borderRadius: 8, fontSize: 11, fontWeight: 500,
                        border: newTemplateDays.includes(idx) ? '1px solid #C2855A' : '1px solid #EDE8E3',
                        background: newTemplateDays.includes(idx) ? '#C2855A' : 'white',
                        color: newTemplateDays.includes(idx) ? 'white' : '#888',
                        cursor: 'pointer',
                      }}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <div style={{ display: 'flex', gap: 6 }}>
                  <button onClick={handleAddTemplate} style={{
                    flex: 1, padding: 8, background: '#C2855A', color: 'white',
                    border: 'none', borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: 'pointer',
                  }}>
                    Save
                  </button>
                  <button onClick={() => { setShowTemplateForm(false); setNewTemplateName(''); setNewTemplateDays([]); }} style={{
                    flex: 1, padding: 8, background: 'white', color: '#888',
                    border: '0.5px solid #EDE8E3', borderRadius: 8, fontSize: 12, cursor: 'pointer',
                  }}>
                    Cancel
                  </button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
      )}
    </>
  );
}
