import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { profile as profileApi, sections as sectionsApi } from '../services/api';

// Which registry categories are relevant to each user type
const USER_TYPE_CATEGORIES = {
  parent: ['essentials', 'kids', 'tasks', 'wellness', 'routine', 'other'],
  new_mom: ['essentials', 'baby', 'wellness', 'tasks', 'other'],
  homemaker: ['essentials', 'tasks', 'wellness', 'work', 'other'],
  working_mom: ['essentials', 'kids', 'tasks', 'wellness', 'work', 'routine', 'other'],
};

export default function CustomiseDashboard() {
  const navigate = useNavigate();
  const [layout, setLayout] = useState([]);
  const [registry, setRegistry] = useState({});
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [customName, setCustomName] = useState('');
  const dragItem = useRef(null);
  const dragOverItem = useRef(null);

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    setLoading(true);
    const [prof, reg] = await Promise.all([profileApi.get(), sectionsApi.list()]);
    if (!reg.error) setRegistry(reg);
    if (!prof.error) {
      setProfileData(prof);
      if (prof.custom_layout && prof.custom_layout.length > 0) {
        setLayout(prof.custom_layout);
      } else {
        const allKeys = Object.keys(reg.error ? {} : reg);
        setLayout(allKeys.map((key) => ({
          key, visible: true, locked: (reg[key]?.lockable) || false,
        })));
      }
    }
    setLoading(false);
  }

  function toggleSection(key) {
    setLayout((prev) => prev.map((item) =>
      item.key === key && !item.locked ? { ...item, visible: !item.visible } : item
    ));
  }

  function addSection(key) {
    if (layout.find((item) => item.key === key)) return;
    setLayout((prev) => [...prev, { key, visible: true, locked: false, added_by_user: true }]);
  }

  function addCustomSection() {
    const name = customName.trim();
    if (!name) return;

    // Cap: max 3 custom sections
    const customCount = layout.filter(i => i.custom_label || i.added_by_user).length;
    if (customCount >= 3) {
      setCustomName('');
      return;
    }

    const key = name.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    if (layout.find((item) => item.key === key)) return;
    setLayout((prev) => [...prev, {
      key, visible: true, locked: false, added_by_user: true,
      custom_label: name,
    }]);
    setCustomName('');
  }

  // Drag reorder
  function handleDragStart(idx) { dragItem.current = idx; }
  function handleDragEnter(idx) { dragOverItem.current = idx; }
  function handleDragEnd() {
    if (dragItem.current === null || dragOverItem.current === null) return;
    const items = [...layout];
    const dragged = items.splice(dragItem.current, 1)[0];
    items.splice(dragOverItem.current, 0, dragged);
    dragItem.current = null;
    dragOverItem.current = null;
    setLayout(items);
  }

  function moveUp(idx) {
    if (idx <= 0) return;
    const items = [...layout];
    [items[idx - 1], items[idx]] = [items[idx], items[idx - 1]];
    setLayout(items);
  }

  function moveDown(idx) {
    if (idx >= layout.length - 1) return;
    const items = [...layout];
    [items[idx], items[idx + 1]] = [items[idx + 1], items[idx]];
    setLayout(items);
  }

  function removeSection(idx) {
    setLayout((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSave() {
    setSaving(true);
    await profileApi.saveLayout(layout);
    setSaving(false);
    navigate('/');
  }

  // Sections that are mutually exclusive — if one is active, hide the others
  const EXCLUSIVE_GROUPS = [
    ['meal_cards', 'mom_meals'],
  ];

  // Filter available sections by user type
  const userType = profileData?.user_type || 'homemaker';
  const allowedCategories = USER_TYPE_CATEGORIES[userType] || USER_TYPE_CATEGORIES.homemaker;
  const activeKeys = new Set(layout.map((item) => item.key));

  // Build a set of keys to hide because a sibling from the same exclusive group is active
  const excludedKeys = new Set();
  EXCLUSIVE_GROUPS.forEach((group) => {
    if (group.some((k) => activeKeys.has(k))) {
      group.forEach((k) => excludedKeys.add(k));
    }
  });

  const availableSections = Object.entries(registry)
    .filter(([key, meta]) => !activeKeys.has(key) && !excludedKeys.has(key) && allowedCategories.includes(meta.category))
    .map(([key, meta]) => ({ key, ...meta }));

  if (loading) return <div className="loading"><div className="spinner" />Loading...</div>;

  return (
    <div style={{ maxWidth: 430, margin: '0 auto', paddingBottom: 120 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '16px 16px 0' }}>
        <button onClick={() => navigate(-1)} style={{
          border: 'none', background: 'none', cursor: 'pointer', color: '#1a1a1a',
          padding: 4, display: 'flex', alignItems: 'center',
        }}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round"><path d="M15 18l-6-6 6-6"/></svg>
        </button>
        <div>
          <div style={{ fontFamily: 'Georgia, serif', fontSize: 20, fontWeight: 700 }}>Customise</div>
          <div style={{ fontSize: 12, color: '#999' }}>Reorder, toggle, or add sections</div>
        </div>
      </div>

      {/* Active sections */}
      <div style={{ padding: '20px 16px 0' }}>
        <div style={{ fontSize: 11, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
          Your sections
        </div>

        {layout.map((item, idx) => {
          const meta = registry[item.key] || {};
          const label = item.custom_label || meta.label || item.key;
          const subtitle = item.added_by_user ? 'Added by you' : item.added_by_ai ? 'Suggested for you' : meta.subtitle || '';
          const emoji = meta.emoji || '📌';

          return (
            <div
              key={item.key + idx}
              draggable
              onDragStart={() => handleDragStart(idx)}
              onDragEnter={() => handleDragEnter(idx)}
              onDragEnd={handleDragEnd}
              onDragOver={(e) => e.preventDefault()}
              style={{
                display: 'flex', alignItems: 'center', gap: 10,
                background: item.visible ? '#fff' : '#FAF7F5',
                borderRadius: 14, border: '1px solid #EDE8E3',
                padding: '10px 12px', marginBottom: 6,
                opacity: item.visible ? 1 : 0.45,
                cursor: 'grab',
                transition: 'opacity 0.2s',
              }}
            >
              {/* Reorder arrows */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 0, flexShrink: 0 }}>
                <button onClick={() => moveUp(idx)} disabled={idx === 0} style={arrowStyle}>
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke={idx === 0 ? '#ddd' : '#999'} strokeWidth="2" strokeLinecap="round"><path d="M2 8l4-4 4 4"/></svg>
                </button>
                <button onClick={() => moveDown(idx)} disabled={idx === layout.length - 1} style={arrowStyle}>
                  <svg width="10" height="10" viewBox="0 0 12 12" fill="none" stroke={idx === layout.length - 1 ? '#ddd' : '#999'} strokeWidth="2" strokeLinecap="round"><path d="M2 4l4 4 4-4"/></svg>
                </button>
              </div>

              {/* Icon */}
              <div style={{
                width: 34, height: 34, borderRadius: 10,
                background: item.visible ? '#FDF2EB' : '#F3F0ED',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 16, flexShrink: 0,
              }}>
                {emoji}
              </div>

              {/* Label */}
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontWeight: 600, fontSize: 14, color: '#1a1a1a', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</div>
                {subtitle && <div style={{ fontSize: 11, color: '#aaa', marginTop: 1 }}>{subtitle}</div>}
              </div>

              {/* Toggle or lock */}
              {item.locked ? (
                <div style={{ fontSize: 14, color: '#ccc', flexShrink: 0 }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#ccc" strokeWidth="2" strokeLinecap="round"><rect x="3" y="11" width="18" height="11" rx="2"/><path d="M7 11V7a5 5 0 0110 0v4"/></svg>
                </div>
              ) : (
                <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
                  <div onClick={() => toggleSection(item.key)} style={{
                    width: 40, height: 22, borderRadius: 11,
                    background: item.visible ? '#C2855A' : '#ddd',
                    display: 'flex', alignItems: 'center', padding: 2,
                    cursor: 'pointer', transition: 'background 0.2s',
                  }}>
                    <div style={{
                      width: 18, height: 18, borderRadius: '50%', background: '#fff',
                      transform: item.visible ? 'translateX(18px)' : 'translateX(0)',
                      transition: 'transform 0.2s',
                      boxShadow: '0 1px 3px rgba(0,0,0,0.1)',
                    }} />
                  </div>
                  {!item.locked && (
                    <button onClick={() => removeSection(idx)} style={{
                      border: 'none', background: 'none', color: '#ccc', cursor: 'pointer',
                      fontSize: 16, padding: '0 2px', lineHeight: 1,
                    }}>×</button>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Add from registry */}
      {availableSections.length > 0 && (
        <div style={{ padding: '16px 16px 0' }}>
          <div style={{ fontSize: 11, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
            Add a section
          </div>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
            {availableSections.map((section) => (
              <button key={section.key} onClick={() => addSection(section.key)} style={{
                display: 'flex', alignItems: 'center', gap: 6,
                background: '#fff', borderRadius: 20, border: '1px solid #EDE8E3',
                padding: '8px 14px', cursor: 'pointer', fontSize: 13, color: '#1a1a1a',
                fontFamily: 'system-ui, sans-serif',
              }}>
                <span style={{ fontSize: 14 }}>{section.emoji || '📌'}</span>
                {section.label}
                <span style={{ color: '#C2855A', fontWeight: 700, marginLeft: 2 }}>+</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Add custom section */}
      {(() => {
        const customCount = layout.filter(i => i.custom_label || i.added_by_user).length;
        const atLimit = customCount >= 3;
        return (
          <div style={{ padding: '20px 16px 0' }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 10 }}>
              Add your own section {atLimit ? '(limit reached)' : `(${customCount}/3)`}
            </div>
            {!atLimit ? (
              <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
                <input
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && addCustomSection()}
                  placeholder="e.g. Meditation, Garden care"
                  style={{
                    flex: 1, padding: '12px 16px', borderRadius: 12,
                    border: '1px solid #EDE8E3', background: '#fff',
                    fontSize: 14, fontFamily: 'system-ui, sans-serif',
                    outline: 'none',
                  }}
                />
                <button onClick={addCustomSection} disabled={!customName.trim()} style={{
                  padding: '12px 18px', borderRadius: 12, border: 'none',
                  background: customName.trim() ? '#1a1a1a' : '#ddd',
                  color: '#fff', fontSize: 13, fontWeight: 600,
                  cursor: customName.trim() ? 'pointer' : 'default',
                }}>
                  Add
                </button>
              </div>
            ) : (
              <div style={{ fontSize: 13, color: '#aaa', padding: '8px 0' }}>
                You can have up to 3 custom sections.
              </div>
            )}
          </div>
        );
      })()}

      {/* Save button */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 430, padding: '12px 16px 28px',
        background: '#fff', borderTop: '1px solid #EDE8E3',
      }}>
        <button onClick={handleSave} disabled={saving} style={{
          width: '100%', padding: 14, borderRadius: 14, border: 'none',
          background: '#C2855A', color: '#fff', fontSize: 15, fontWeight: 600,
          cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
        }}>
          {saving ? 'Saving...' : 'Save layout'}
        </button>
      </div>
    </div>
  );
}

const arrowStyle = {
  border: 'none', background: 'none', cursor: 'pointer',
  padding: '1px 2px', display: 'flex', alignItems: 'center',
};
