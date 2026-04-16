import { useState, useEffect, useCallback } from 'react';
import { kidsActivities } from '../../services/api';

const ACTIVITY_ICONS = {
  number_tracing: '🔢', letter_tracing: '🔤', counting: '🧮',
  drawing: '✏️', maze: '🌀', matching: '🔗',
  dot_to_dot: '⭐', word_search: '🔍', math_problems: '➕',
  pattern: '🔶', spot_difference: '👀', crossword_clues: '📝',
  odd_one_out: '🤔', fill_in_blank: '✍️', riddle: '💡',
  scramble: '🔀', true_false: '✅', sequencing: '📋',
  rhyming: '🎵', category_sort: '📦',
};

const ACTIVITY_COLORS = [
  { bg: '#FFF8E1', text: '#C9A84C' },
  { bg: '#F5F0FF', text: '#6B46C1' },
  { bg: '#F0FFF8', text: '#2D7A5B' },
];

const STORY_GRADIENTS = [
  'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
  'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)',
  'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)',
  'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)',
  'linear-gradient(135deg, #fa709a 0%, #fee140 100%)',
  'linear-gradient(135deg, #a18cd1 0%, #fbc2eb 100%)',
  'linear-gradient(135deg, #fccb90 0%, #d57eeb 100%)',
];

export default function KidsActivitiesSection() {
  const [plan, setPlan] = useState(null);
  const [hasChildren, setHasChildren] = useState(true);
  const [loading, setLoading] = useState(true);
  const [selectedChild, setSelectedChild] = useState(0);
  const [openSection, setOpenSection] = useState(null);
  const [markingRead, setMarkingRead] = useState(null);
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState('');

  const fetchCurrent = useCallback(async () => {
    const res = await kidsActivities.current();
    if (!res.error) {
      setPlan(res.plan);
      setHasChildren(res.has_children);
    }
    setLoading(false);
  }, []);

  const handleRetry = async () => {
    setRetrying(true);
    setRetryError('');
    const res = await kidsActivities.generate();
    if (res.error) {
      setRetryError(typeof res.error === 'string' ? res.error : 'Could not generate. Try again soon.');
      setRetrying(false);
      return;
    }
    setPlan(res);
    setRetrying(false);
  };

  useEffect(() => { fetchCurrent(); }, [fetchCurrent]);

  const handleMarkRead = async (dayId) => {
    setMarkingRead(dayId);
    const res = await kidsActivities.markRead(dayId);
    if (!res.error) {
      setPlan(res);
      setOpenSection(null);

      // Check if all days are now done — if so, refetch to trigger auto-regeneration
      const allChildrenDone = (res.children_progress || []).every(
        (c) => c.completed_days >= c.total_days
      );
      if (allChildrenDone) {
        setLoading(true);
        await fetchCurrent();
      }
    }
    setMarkingRead(null);
  };

  if (loading) {
    return (
      <div style={{ padding: '24px 16px', textAlign: 'center' }}>
        <div style={{ color: '#888', fontSize: 13 }}>Loading activities...</div>
      </div>
    );
  }

  if (!hasChildren) {
    return (
      <>
        <div className="section-header">
          <div className="section-title">Kids Activities</div>
        </div>
        <div style={{
          margin: '0 16px 12px', padding: 24, borderRadius: 14,
          border: '1.5px dashed #EDE8E3', textAlign: 'center',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>👶</div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>No children added yet</div>
          <div style={{ fontSize: 12, color: '#888' }}>Add your children in profile settings to get started</div>
        </div>
      </>
    );
  }

  if (!plan || !plan.children_progress?.length) {
    return (
      <>
        <div className="section-header">
          <div className="section-title">Kids Activities</div>
        </div>
        <div style={{
          margin: '0 16px 12px', padding: 20, borderRadius: 14,
          background: 'white', border: '0.5px solid #EDE8E3', textAlign: 'center',
        }}>
          <div style={{ fontSize: 28, marginBottom: 8 }}>🎨</div>
          <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 4 }}>
            Activities aren't ready yet
          </div>
          <div style={{ fontSize: 12, color: '#888', marginBottom: 12, lineHeight: 1.4 }}>
            We couldn't put this week's activities together. Give it another try.
          </div>
          <button
            onClick={handleRetry}
            disabled={retrying}
            style={{
              padding: '9px 20px', border: 'none', borderRadius: 22,
              background: '#C2855A', color: 'white', fontWeight: 600, fontSize: 13,
              cursor: retrying ? 'wait' : 'pointer', opacity: retrying ? 0.7 : 1,
            }}
          >
            {retrying ? 'Generating…' : 'Try again'}
          </button>
          {retryError && (
            <div style={{ fontSize: 11, color: '#DC3545', marginTop: 8 }}>{retryError}</div>
          )}
        </div>
      </>
    );
  }

  const { theme, days, children_progress } = plan;
  const childIds = children_progress.map((c) => c.child_id);
  const childNames = children_progress.map((c) => c.child_name);
  const currentChildId = childIds[selectedChild] || childIds[0];
  const progress = children_progress[selectedChild] || children_progress[0];

  const childDays = days
    .filter((d) => d.child === currentChildId)
    .sort((a, b) => a.day_of_week - b.day_of_week);

  const activeDay = childDays.find((d) => d.unlocked && !d.is_read && !d.is_downloaded);

  const toggle = (section) => setOpenSection(openSection === section ? null : section);

  const activities = activeDay?.worksheet_content?.activities || [];
  const storyGradient = activeDay
    ? STORY_GRADIENTS[(activeDay.day_of_week + activeDay.child) % STORY_GRADIENTS.length]
    : STORY_GRADIENTS[0];

  return (
    <>
      <div className="section-header">
        <div className="section-title">Kids Activities</div>
      </div>

      {/* ── Storybook card ── */}
      <div style={{
        margin: '0 16px 12px', borderRadius: 16,
        border: '0.5px solid #EDE8E3', background: 'white',
        overflow: 'hidden',
      }}>

        {/* Theme + child tabs row */}
        <div style={{ padding: '14px 16px 12px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: childIds.length > 1 ? 10 : 0 }}>
            <span style={{ fontSize: 18 }}>🎨</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 14, color: '#1a1a1a' }}>{theme}</div>
              <div style={{ fontSize: 10, color: '#888' }}>
                This week's theme
                {childIds.length === 1 && ` · ${childNames[0]}`}
              </div>
            </div>
          </div>

          {childIds.length > 1 && (
            <div style={{ display: 'flex', gap: 6 }}>
              {childNames.map((name, i) => (
                <button
                  key={childIds[i]}
                  onClick={() => { setSelectedChild(i); setOpenSection(null); }}
                  style={{
                    padding: '5px 14px', borderRadius: 16, fontSize: 11, fontWeight: 600,
                    border: selectedChild === i ? 'none' : '1px solid #EDE8E3',
                    background: selectedChild === i ? '#1B2A4A' : 'transparent',
                    color: selectedChild === i ? '#C9A84C' : '#888',
                    cursor: 'pointer', whiteSpace: 'nowrap',
                  }}
                >
                  {name}
                </button>
              ))}
            </div>
          )}
        </div>


        {activeDay && (
          <>
            {/* ── Story illustration block ── */}
            <div
              onClick={() => toggle('story')}
              style={{
                margin: '0 12px', borderRadius: 14, overflow: 'hidden',
                background: storyGradient, cursor: 'pointer',
                padding: '20px 16px', position: 'relative',
              }}
            >
              {/* Background emoji */}
              <div style={{
                fontSize: 56, position: 'absolute', right: 12, bottom: 8,
                opacity: 0.15, lineHeight: 1,
              }}>
                {activeDay.story_emoji || '📖'}
              </div>

              <div style={{ fontSize: 32, marginBottom: 6 }}>
                {activeDay.story_emoji || '📖'}
              </div>
              <div style={{
                color: 'white', fontWeight: 800, fontSize: 15, lineHeight: 1.3,
                textShadow: '0 1px 3px rgba(0,0,0,0.15)',
                marginBottom: 4, maxWidth: '85%',
              }}>
                {activeDay.story_title}
              </div>
              {activeDay.story_illustration && (
                <div style={{
                  color: 'rgba(255,255,255,0.7)', fontSize: 11, lineHeight: 1.4,
                  display: '-webkit-box', WebkitLineClamp: 2,
                  WebkitBoxOrient: 'vertical', overflow: 'hidden',
                  maxWidth: '80%',
                }}>
                  {activeDay.story_illustration}
                </div>
              )}
              <div style={{
                marginTop: 10, display: 'inline-block',
                background: 'rgba(255,255,255,0.2)', borderRadius: 12,
                padding: '4px 10px', fontSize: 10, color: 'white', fontWeight: 600,
              }}>
                {openSection === 'story' ? 'Close ▲' : 'Tap to read →'}
              </div>
            </div>

            {/* Story text (expanded) */}
            {openSection === 'story' && (
              <div style={{ padding: '14px 16px', margin: '0 12px', borderBottom: '0.5px solid #F0F0F0' }}>
                <div style={{ fontSize: 14, color: '#333', lineHeight: 1.8 }}>
                  {activeDay.story_text}
                </div>
              </div>
            )}

            {/* ── Activities section ── */}
            <div style={{ padding: '12px 16px 6px' }}>
              <div style={{ display: 'flex', alignItems: 'center', marginBottom: 8 }}>
                <div style={{ flex: 1, fontSize: 11, fontWeight: 700, color: '#888', textTransform: 'uppercase', letterSpacing: 0.5 }}>
                  Today's activities
                </div>
                <a
                  href={kidsActivities.downloadUrl(activeDay.id)}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    fontSize: 20, textDecoration: 'none', lineHeight: 1,
                    cursor: 'pointer',
                  }}
                  title="Download PDF"
                >
                  📥
                </a>
              </div>

              {/* Activity chips row */}
              <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
                {activities.map((act, i) => {
                  const icon = ACTIVITY_ICONS[act.type] || '🎯';
                  const isOpen = openSection === `activity_${i}`;
                  return (
                    <button
                      key={i}
                      onClick={() => toggle(`activity_${i}`)}
                      style={{
                        flex: 1, display: 'flex', flexDirection: 'column',
                        alignItems: 'center', gap: 4,
                        padding: '10px 6px', borderRadius: 12,
                        border: isOpen ? '1.5px solid #C2855A' : '1px solid #EDE8E3',
                        background: isOpen ? '#FFF8F0' : 'white',
                        cursor: 'pointer',
                      }}
                    >
                      <span style={{ fontSize: 22 }}>{icon}</span>
                      <span style={{
                        fontSize: 10, fontWeight: 600, lineHeight: 1.2,
                        color: isOpen ? '#C2855A' : '#666',
                        overflow: 'hidden', textOverflow: 'ellipsis',
                        display: '-webkit-box', WebkitLineClamp: 2,
                        WebkitBoxOrient: 'vertical', textAlign: 'center',
                      }}>
                        {act.title}
                      </span>
                    </button>
                  );
                })}
              </div>

              {/* Expanded activity detail */}
              {activities.map((act, i) => {
                if (openSection !== `activity_${i}`) return null;
                return (
                  <div key={i} style={{
                    padding: '10px 12px', background: '#F8F6F4', borderRadius: 10,
                    marginBottom: 8,
                  }}>
                    <ActivityPreview activity={act} />
                  </div>
                );
              })}
            </div>

            {/* ── Done button ── */}
            <div style={{ padding: '6px 16px 14px' }}>
              <button
                onClick={() => handleMarkRead(activeDay.id)}
                disabled={markingRead === activeDay.id}
                style={{
                  width: '100%', padding: '10px 0', borderRadius: 22,
                  border: 'none', fontWeight: 700, fontSize: 12,
                  cursor: markingRead === activeDay.id ? 'wait' : 'pointer',
                  background: '#C2855A', color: 'white',
                  opacity: markingRead === activeDay.id ? 0.7 : 1,
                }}
              >
                {markingRead === activeDay.id ? 'Loading...' : '✓ Done'}
              </button>
            </div>
          </>
        )}
      </div>
    </>
  );
}


function ActivityPreview({ activity }) {
  const { type, data } = activity;
  if (!data) return null;
  const s = { fontSize: 13, color: '#444', lineHeight: 1.6, marginTop: 8 };

  switch (type) {
    case 'drawing':
      return <div style={s}>{data.prompt}</div>;
    case 'maze':
      return <div style={s}>Help <b>{data.start_label}</b> reach <b>{data.end_label}</b>!</div>;
    case 'matching':
      return (
        <div style={{ marginTop: 8 }}>
          {(data.left || []).map((l, i) => (
            <div key={i} style={{ fontSize: 13, color: '#444', padding: '3px 0', display: 'flex', gap: 8 }}>
              <span style={{ flex: 1 }}>{l}</span>
              <span style={{ color: '#ccc' }}>→</span>
              <span style={{ flex: 1, textAlign: 'right' }}>{(data.right || [])[i] || '?'}</span>
            </div>
          ))}
        </div>
      );
    case 'dot_to_dot':
      return <div style={s}>Connect {data.total_dots} dots to reveal: <b>{data.reveal}</b></div>;
    case 'number_tracing':
      return <div style={s}>Trace: <b style={{ fontSize: 18, letterSpacing: 8 }}>{(data.numbers || data.items || []).join(' ')}</b></div>;
    case 'letter_tracing':
      return <div style={s}>Trace: <b style={{ fontSize: 18, letterSpacing: 8 }}>{(data.letters || data.items || []).join(' ')}</b></div>;
    case 'counting':
      return <div style={s}>{data.prompt}</div>;
    case 'word_search':
      return <div style={s}>Find: <b>{(data.words || []).join(', ')}</b></div>;
    case 'math_problems':
      return (
        <div style={{ marginTop: 8 }}>
          {(data.problems || []).map((p, i) => (
            <div key={i} style={{ fontSize: 14, color: '#333', padding: '3px 0', fontFamily: 'monospace' }}>{p}</div>
          ))}
        </div>
      );
    case 'pattern':
      return <div style={{ ...s, fontSize: 18, textAlign: 'center', letterSpacing: 4 }}>{data.sequence}</div>;
    case 'crossword_clues':
      return (
        <div style={{ marginTop: 8 }}>
          {(data.clues || []).map((c, i) => (
            <div key={i} style={{ fontSize: 13, color: '#444', padding: '3px 0' }}>
              {i + 1}. {c.clue} <span style={{ color: '#ccc' }}>({c.answer?.length || '?'} letters)</span>
            </div>
          ))}
        </div>
      );
    case 'spot_difference':
      return <div style={s}><em>{data.scene}</em> — find {(data.differences || []).length} differences!</div>;
    case 'odd_one_out':
      return <div style={s}>Which doesn't belong? <b>{(data.items || []).join(', ')}</b></div>;
    case 'fill_in_blank':
      return <div style={s}>{(data.sentences || []).map((sent, i) => <div key={i}>{i + 1}. {sent}</div>)}</div>;
    case 'riddle':
      return <div style={s}><em>{data.riddle}</em>{data.hint && <div style={{ color: '#888', fontSize: 11, marginTop: 4 }}>Hint: {data.hint}</div>}</div>;
    case 'scramble':
      return <div style={s}>{(data.words || []).map((w, i) => <div key={i}><b style={{ letterSpacing: 4 }}>{w.scrambled}</b>{w.hint && <span style={{ color: '#888' }}> — {w.hint}</span>}</div>)}</div>;
    case 'true_false':
      return <div style={s}>{(data.questions || []).map((q, i) => <div key={i}>{i + 1}. {q.statement}</div>)}</div>;
    case 'sequencing':
      return <div style={s}><b>{data.title}</b> — {(data.steps || []).length} steps to order</div>;
    case 'rhyming':
      return <div style={s}>Rhyme with: <b>{(data.pairs || []).map(p => p.word).join(', ')}</b></div>;
    case 'category_sort':
      return <div style={s}>Sort into: <b>{Object.keys(data.categories || {}).join(', ')}</b></div>;
    default:
      return <div style={s}>{JSON.stringify(data)}</div>;
  }
}
