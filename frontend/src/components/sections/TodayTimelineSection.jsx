import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { timeline } from '../../services/api';

// Per-kind colors and inline SVG icons. Matches the warm palette used
// elsewhere on the dashboard. Each entry: { bg, fg, icon }.
const KIND_STYLES = {
  meal:     { bg: '#E2EBE5', fg: '#2D5F4C', icon: ChefHatIcon },
  school:   { bg: '#F5E8D5', fg: '#B07A2A', icon: GradCapIcon },
  work:     { bg: '#EDE8F5', fg: '#6B5B95', icon: BriefcaseIcon },
  study:    { bg: '#EDE8F5', fg: '#6B5B95', icon: BookIcon },
  selfcare: { bg: '#FCE4E4', fg: '#C2545A', icon: HeartIcon },
  grocery:  { bg: '#DCE9F3', fg: '#4A7BA8', icon: CartIcon },
  class:    { bg: '#F5E8D5', fg: '#B07A2A', icon: GradCapIcon },
  event:    { bg: '#F0EBE6', fg: '#5A5A5A', icon: DotIcon },
};

function styleFor(kind) {
  return KIND_STYLES[kind] || KIND_STYLES.event;
}

export default function TodayTimelineSection() {
  const navigate = useNavigate();
  const [items, setItems] = useState([]);
  const [checked, setChecked] = useState(new Set());
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => { load(); }, []);

  async function load() {
    setError('');
    const res = await timeline.today();
    if (res?.error) {
      setError('Could not load timeline.');
    } else {
      setItems(Array.isArray(res?.items) ? res.items : []);
      setChecked(new Set(res?.checked_keys || []));
    }
    setLoading(false);
  }

  async function toggle(itemKey) {
    // Optimistic — flip immediately, roll back on failure.
    const wasChecked = checked.has(itemKey);
    const next = new Set(checked);
    if (wasChecked) next.delete(itemKey);
    else next.add(itemKey);
    setChecked(next);

    const res = await timeline.toggleCheck(itemKey, !wasChecked);
    if (res?.error) {
      // Roll back
      const rollback = new Set(checked);
      if (wasChecked) rollback.add(itemKey);
      else rollback.delete(itemKey);
      setChecked(rollback);
    }
  }

  if (loading) return null;

  return (
    <div style={wrapStyle}>
      <div style={headerStyle}>
        <div style={titleStyle}>Today</div>
        <button onClick={() => navigate('/schedule')} style={linkStyle}>
          See full plan →
        </button>
      </div>

      {error && (
        <div style={emptyStyle}>{error} <button onClick={load} style={retryStyle}>Retry</button></div>
      )}

      {!error && items.length === 0 && (
        <div style={emptyStyle}>Nothing scheduled for today yet.</div>
      )}

      {items.length > 0 && (
      <div style={listStyle}>
        {items.map((it, idx) => {
          const isDone = checked.has(it.item_key);
          const s = styleFor(it.kind);
          const Icon = s.icon;
          const isLast = idx === items.length - 1;
          return (
            <div key={it.item_key} style={isLast ? rowLastStyle : rowStyle}>
              <div style={timeStyle}>{it.time || ''}</div>
              <div style={{ ...iconWrapStyle, background: s.bg, color: s.fg }}>
                <Icon />
              </div>
              <div style={infoStyle}>
                <div style={isDone ? titleDoneStyle : titleRowStyle}>{it.title}</div>
                {it.subtitle && (
                  <div style={subStyle}>{it.subtitle}</div>
                )}
              </div>
              <button
                onClick={() => toggle(it.item_key)}
                aria-label={isDone ? 'Mark not done' : 'Mark done'}
                style={isDone ? checkBtnDoneStyle : checkBtnStyle}
              >
                <CheckIcon />
              </button>
            </div>
          );
        })}
      </div>
      )}
    </div>
  );
}

// ── Icons ──────────────────────────────────────────────────────────
function CheckIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
         stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="20 6 9 17 4 12" />
    </svg>
  );
}
function ChefHatIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M6 13.87A4 4 0 0 1 7.41 6a5.11 5.11 0 0 1 1.05-1.54 5 5 0 0 1 7.08 0A5.11 5.11 0 0 1 16.59 6 4 4 0 0 1 18 13.87V21H6Z" />
      <line x1="6" y1="17" x2="18" y2="17" />
    </svg>
  );
}
function GradCapIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M22 10L12 5 2 10l10 5 10-5z" />
      <path d="M6 12v5a6 3 0 0 0 12 0v-5" />
    </svg>
  );
}
function BriefcaseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <rect x="2" y="7" width="20" height="14" rx="2" />
      <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
    </svg>
  );
}
function BookIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
      <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
    </svg>
  );
}
function HeartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="none">
      <path d="M12 21s-7-4.5-9.5-9A5.5 5.5 0 0 1 12 6a5.5 5.5 0 0 1 9.5 6c-2.5 4.5-9.5 9-9.5 9z" />
    </svg>
  );
}
function CartIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
         strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="21" r="1.5" />
      <circle cx="18" cy="21" r="1.5" />
      <path d="M3 3h2l3 13h11l3-9H6" />
    </svg>
  );
}
function DotIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor">
      <circle cx="12" cy="12" r="4" />
    </svg>
  );
}

// ── Styles ─────────────────────────────────────────────────────────
const wrapStyle = { padding: '0 16px', marginBottom: 14 };
const headerStyle = {
  display: 'flex', alignItems: 'baseline', justifyContent: 'space-between',
  marginBottom: 10,
};
const titleStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 22, fontWeight: 500,
  letterSpacing: '-0.01em', color: '#1A1A1A',
};
const linkStyle = {
  fontSize: 12, color: '#C2855A', fontWeight: 500, background: 'transparent',
  border: 'none', cursor: 'pointer', padding: 0,
};

const listStyle = {
  background: 'white',
  border: '1px solid #E8E3D8',
  borderRadius: 16,
  overflow: 'hidden',
};
const rowStyle = {
  display: 'flex', alignItems: 'center', gap: 12,
  padding: '12px 14px',
  borderBottom: '1px solid #F2EEE7',
};
const rowLastStyle = { ...rowStyle, borderBottom: 'none' };
const emptyStyle = {
  background: 'white', border: '1px solid #E8E3D8', borderRadius: 16,
  padding: '16px', fontSize: 13, color: '#9A9A9A', textAlign: 'center',
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
};
const retryStyle = {
  background: 'transparent', border: 'none', color: '#C2855A',
  fontSize: 13, fontWeight: 500, cursor: 'pointer', padding: 0,
  textDecoration: 'underline',
};
const timeStyle = {
  width: 48, flexShrink: 0,
  fontSize: 11, fontWeight: 500, color: '#5A5A5A',
  letterSpacing: '0.02em',
};
const iconWrapStyle = {
  width: 36, height: 36, borderRadius: 10,
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  flexShrink: 0,
};
const infoStyle = { flex: 1, minWidth: 0 };
const titleRowStyle = {
  fontSize: 13.5, color: '#1A1A1A', lineHeight: 1.3,
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
};
const titleDoneStyle = {
  ...titleRowStyle,
  color: '#9A9A9A', textDecoration: 'line-through',
};
const subStyle = {
  fontSize: 11.5, color: '#9A9A9A', marginTop: 2,
  whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis',
};
const checkBtnStyle = {
  width: 28, height: 28, borderRadius: '50%',
  background: 'white', border: '1.5px solid #E8E3D8',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  color: 'transparent', cursor: 'pointer', flexShrink: 0,
  transition: 'all 0.15s',
};
const checkBtnDoneStyle = {
  ...checkBtnStyle,
  background: '#2D5F4C', borderColor: '#2D5F4C', color: 'white',
};
