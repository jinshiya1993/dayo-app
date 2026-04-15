import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { profile as profileApi, sections as sectionsApi, plans } from '../services/api';

export default function OnboardingPreview() {
  const navigate = useNavigate();
  const location = useLocation();
  const topRef = useRef(null);

  // Data passed from loading screen
  const { profileData: initialData, name } = location.state || {};

  const [profileData, setProfileData] = useState(initialData || {});
  const [confidence, setConfidence] = useState(initialData?.confidence || {});
  const [sectionReasons, setSectionReasons] = useState(initialData?.section_reasons || {});
  const [registry, setRegistry] = useState({});
  const [layout, setLayout] = useState([]);
  const [saving, setSaving] = useState(false);
  const [loading, setLoading] = useState(true);
  const [addOpen, setAddOpen] = useState(false);
  const [addText, setAddText] = useState('');

  const displayName = name || profileData?.display_name || 'there';

  useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    const [prof, reg] = await Promise.all([
      profileApi.get(),
      sectionsApi.list(),
    ]);

    if (!prof.error) {
      setProfileData((prev) => ({ ...prev, ...prof }));
      if (prof.custom_layout?.length > 0) {
        setLayout(prof.custom_layout);
      }
    }
    if (!reg.error) setRegistry(reg);
    setLoading(false);
  }

  function removeSection(key) {
    setLayout((prev) => prev.filter((item) => item.key !== key));
  }

  function addSection(key, label) {
    if (layout.find((item) => item.key === key)) return;
    setLayout((prev) => [
      ...prev,
      { key, visible: true, locked: false, added_by_user: true, ...(label ? { label } : {}) },
    ]);
  }

  function handleAddCustom() {
    const text = addText.trim();
    if (!text) return;
    // Try match against registry first
    const match = Object.entries(registry).find(
      ([, meta]) => meta.label?.toLowerCase() === text.toLowerCase()
    );
    if (match) {
      addSection(match[0]);
    } else {
      // Cap: max 3 custom sections
      const customCount = layout.filter(i => i.label || i.added_by_user).length;
      if (customCount >= 3) return;

      const key = `custom_${text.toLowerCase().replace(/\s+/g, '_')}_${Date.now()}`;
      addSection(key, text);
    }
    setAddText('');
    setAddOpen(false);
  }

  async function handleConfirm() {
    setSaving(true);
    await profileApi.saveLayout(layout);
    await plans.generate();
    navigate('/', { replace: true });
  }

  function scrollToTop() {
    topRef.current?.scrollIntoView({ behavior: 'smooth' });
  }

  // Available sections not in layout
  const activeKeys = new Set(layout.map((item) => item.key));
  const available = Object.entries(registry)
    .filter(([key]) => !activeKeys.has(key))
    .map(([key, meta]) => ({ key, ...meta }));

  // Fields that have low or missing confidence
  const uncertainFields = Object.entries(confidence)
    .filter(([, v]) => v === 'low' || v === 'missing')
    .map(([k]) => k);

  if (loading) {
    return <div className="loading"><div className="spinner" />Loading preview...</div>;
  }

  return (
    <div className="app-shell" style={{ paddingBottom: 100, animation: 'previewFadeIn 0.5s ease-in' }}>
      <div ref={topRef} />

      {/* ── 1. Hero Section ───────────────────────────────── */}
      <div style={{
        background: '#1a1a1a', padding: '32px 20px 28px',
        borderRadius: '0 0 20px 20px',
      }}>
        <div style={{
          fontFamily: 'Georgia, serif', fontSize: 24, fontWeight: 700,
          color: 'white', lineHeight: 1.3, marginBottom: 8,
        }}>
          Here is what Dayo built for you, {displayName}
        </div>
        <div style={{ fontSize: 13, color: '#888', lineHeight: 1.5 }}>
          Review your dashboard before you start. Remove anything you don't need. Add anything you want.
        </div>
      </div>

      {/* ── 2. Dashboard Sections ─────────────────────────── */}
      <div style={{ padding: '20px 16px 0' }}>
        <div style={{
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          marginBottom: 10,
        }}>
          <div>
            <div style={{ fontFamily: 'Georgia, serif', fontSize: 18, fontWeight: 700 }}>Your dashboard sections</div>
            <div style={{ fontSize: 12, color: '#888' }}>Tap × to remove</div>
          </div>
        </div>

        {layout.map((item) => {
          const meta = registry[item.key] || {};
          const reason = sectionReasons[item.key];
          const isAiAdded = item.added_by_ai;
          const label = item.label || meta.label || item.key;

          return (
            <div key={item.key} style={{
              background: 'white', borderRadius: 14,
              border: isAiAdded ? '1px solid #E8A87C' : '0.5px solid #EDE8E3',
              padding: '14px', marginBottom: 8,
              display: 'flex', alignItems: 'center', gap: 10,
            }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10,
                background: isAiAdded ? '#FFF8F0' : '#FAF7F5',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 18,
              }}>
                {meta.emoji || '📌'}
              </div>
              <div style={{ flex: 1 }}>
                <div style={{ fontWeight: 600, fontSize: 14 }}>{label}</div>
                <div style={{ fontSize: 11, color: reason ? '#C2855A' : '#888', lineHeight: 1.4 }}>
                  {reason || (isAiAdded ? 'Added by Dayo' : item.added_by_user ? 'Added by you' : meta.subtitle || '')}
                </div>
              </div>
              <button
                onClick={() => removeSection(item.key)}
                aria-label="Remove section"
                style={{
                  width: 28, height: 28, borderRadius: '50%',
                  border: '0.5px solid #EDE8E3', background: '#FAF7F5',
                  color: '#888', fontSize: 16, lineHeight: 1,
                  cursor: 'pointer', padding: 0,
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                }}
              >
                ×
              </button>
            </div>
          );
        })}

        {/* Add more sections — existing registry list */}
        {available.length > 0 && (
          <>
            <div style={{ fontSize: 11, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: 0.5, marginTop: 16, marginBottom: 8 }}>
              Add more sections
            </div>
            {available.slice(0, 4).map((section) => (
              <div key={section.key} onClick={() => addSection(section.key)} style={{
                background: 'white', borderRadius: 14, border: '0.5px dashed #EDE8E3',
                padding: '12px 14px', marginBottom: 8, cursor: 'pointer',
                display: 'flex', alignItems: 'center', gap: 10,
              }}>
                <div style={{ width: 36, height: 36, borderRadius: 10, background: '#FAF7F5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18 }}>
                  {section.emoji || '📌'}
                </div>
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 600, fontSize: 14 }}>{section.label}</div>
                  <div style={{ fontSize: 11, color: '#888' }}>{section.subtitle}</div>
                </div>
                <span style={{ fontSize: 20, color: '#C2855A', fontWeight: 700 }}>+</span>
              </div>
            ))}
          </>
        )}

        {/* Add a section — dashed CTA for custom */}
        {!addOpen ? (
          <div onClick={() => setAddOpen(true)} style={{
            background: '#FFF8F0', borderRadius: 14, border: '1px dashed #E8A87C',
            padding: '14px', marginTop: 4, cursor: 'pointer',
            display: 'flex', alignItems: 'center', gap: 10,
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: 10, background: '#FAEBDD',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 20, color: '#C2855A', fontWeight: 700,
            }}>
              +
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 600, fontSize: 14, color: '#C2855A' }}>Add a section</div>
              <div style={{ fontSize: 11, color: '#B58763', lineHeight: 1.4 }}>
                Ramadan mode · Focus time · Batch cooking · more
              </div>
            </div>
          </div>
        ) : (
          <div style={{
            background: 'white', borderRadius: 14, border: '1px solid #E8A87C',
            padding: '12px', marginTop: 4,
          }}>
            <input
              autoFocus
              type="text"
              value={addText}
              onChange={(e) => setAddText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleAddCustom();
                if (e.key === 'Escape') { setAddOpen(false); setAddText(''); }
              }}
              placeholder="Name a section..."
              style={{
                width: '100%', padding: '10px 12px', fontSize: 14,
                border: '0.5px solid #EDE8E3', borderRadius: 10,
                outline: 'none', background: '#FAF7F5',
                boxSizing: 'border-box',
              }}
            />
            {addText.trim() && available.filter((s) =>
              s.label?.toLowerCase().includes(addText.trim().toLowerCase())
            ).slice(0, 4).length > 0 && (
              <div style={{ marginTop: 8 }}>
                {available
                  .filter((s) => s.label?.toLowerCase().includes(addText.trim().toLowerCase()))
                  .slice(0, 4)
                  .map((section) => (
                    <div key={section.key} onClick={() => { addSection(section.key); setAddText(''); setAddOpen(false); }} style={{
                      padding: '8px 10px', borderRadius: 8, cursor: 'pointer',
                      display: 'flex', alignItems: 'center', gap: 8, fontSize: 13,
                    }}>
                      <span style={{ fontSize: 16 }}>{section.emoji || '📌'}</span>
                      <span>{section.label}</span>
                    </div>
                  ))}
              </div>
            )}
            <div style={{ display: 'flex', gap: 8, marginTop: 10 }}>
              <button
                onClick={() => { setAddOpen(false); setAddText(''); }}
                style={{
                  flex: 1, padding: '10px', borderRadius: 10,
                  border: '0.5px solid #EDE8E3', background: 'white',
                  fontSize: 13, fontWeight: 500, cursor: 'pointer',
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleAddCustom}
                disabled={!addText.trim()}
                style={{
                  flex: 1, padding: '10px', borderRadius: 10, border: 'none',
                  background: '#C2855A', color: 'white',
                  fontSize: 13, fontWeight: 600, cursor: 'pointer',
                  opacity: addText.trim() ? 1 : 0.5,
                }}
              >
                Add
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── 4. Uncertainty Notice ─────────────────────────── */}
      {uncertainFields.length > 0 && (
        <div style={{ padding: '16px' }}>
          <div style={{
            background: '#FFF3CD', borderRadius: 14, padding: '14px 16px',
            border: '0.5px solid #F5E6B8',
          }}>
            <div style={{ fontWeight: 600, fontSize: 13, color: '#856404', marginBottom: 6 }}>
              Some things I'm not sure about
            </div>
            {uncertainFields.map((field) => (
              <div key={field} style={{ fontSize: 12, color: '#856404', padding: '3px 0' }}>
                • <strong>{field.replace('_', ' ')}</strong>: {confidence[field] === 'missing' ? "You didn't mention this — I'll use a default" : "I estimated this — you can edit it in your profile"}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── 5. Action Buttons ─────────────────────────────── */}
      <div style={{
        position: 'fixed', bottom: 0, left: '50%', transform: 'translateX(-50%)',
        width: '100%', maxWidth: 390, padding: '12px 16px 24px',
        background: 'white', borderTop: '0.5px solid #EDE8E3',
      }}>
        <div style={{
          fontSize: 11, color: '#888', textAlign: 'center', marginBottom: 8,
        }}>
          Want more? Add or remove sections above before continuing.
        </div>
        <button onClick={handleConfirm} disabled={saving} style={{
          width: '100%', padding: '14px', borderRadius: 14, border: 'none',
          background: '#1a1a1a', color: 'white', fontSize: 15, fontWeight: 600,
          cursor: 'pointer', marginBottom: 8, opacity: saving ? 0.6 : 1,
        }}>
          {saving ? 'Saving...' : "Looks good — show my dashboard"}
        </button>
        <button onClick={scrollToTop} style={{
          width: '100%', padding: '12px', borderRadius: 14,
          border: '0.5px solid #EDE8E3', background: 'white',
          fontSize: 14, fontWeight: 500, cursor: 'pointer', color: '#1a1a1a',
        }}>
          Change something first
        </button>
      </div>

      {/* ── Inline loading overlay while building the dashboard ─── */}
      {saving && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(26,26,26,0.45)',
          backdropFilter: 'blur(2px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 100, animation: 'overlayFadeIn 0.2s ease-out',
        }}>
          <div style={{
            background: 'white', borderRadius: 16, padding: '28px 36px',
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
            boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
          }}>
            <div style={{ display: 'flex', gap: 6 }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: 8, height: 8, borderRadius: '50%', background: '#C2855A',
                  animation: `dotPulse 1.2s ease-in-out ${i * 0.15}s infinite`,
                }} />
              ))}
            </div>
            <div style={{ fontSize: 14, color: '#1a1a1a', fontWeight: 500 }}>
              Creating your plan...
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes previewFadeIn {
          from { opacity: 0; transform: translateY(20px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes overlayFadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes dotPulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.4); }
        }
      `}</style>
    </div>
  );
}
