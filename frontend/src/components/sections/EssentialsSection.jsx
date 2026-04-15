import { useState, useEffect } from 'react';
import { essentials as api, grocery } from '../../services/api';

const ITEM_EMOJIS = {
  'nappies': '🧷', 'nappy': '🧷', 'diapers': '🧷',
  'wipes': '🧻', 'wet wipes': '🧻',
  'formula': '🍼', 'formula/milk': '🍼', 'milk': '🍼',
  'clean bottles': '🍶', 'bottles': '🍶', 'steriliser': '🍶',
  'breast pads': '🤱', 'nursing pads': '🤱',
  'nipple cream': '💧',
  'water bottle': '💦', 'water': '💦',
  'burp cloths': '🧣', 'clean burp cloths': '🧣',
  'postnatal vitamin': '💊', 'vitamins': '💊',
  'cream': '🧴', 'lotion': '🧴',
  'blanket': '🧸', 'pacifier': '🧸', 'dummy': '🧸',
};

function getEmoji(itemName) {
  const lower = itemName.toLowerCase();
  for (const [key, emoji] of Object.entries(ITEM_EMOJIS)) {
    if (lower.includes(key)) return emoji;
  }
  return '📦';
}

export default function EssentialsSection() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showAdd, setShowAdd] = useState(false);
  const [newItem, setNewItem] = useState('');
  const [error, setError] = useState('');
  const [groceryMsg, setGroceryMsg] = useState('');

  async function handleAddToGrocery(checkId, itemName, e) {
    e.stopPropagation();
    const res = await grocery.quickAdd(itemName);
    const added = !res.error || res.error === 'already_exists';
    if (added) {
      // Mark on backend so it stays hidden
      api.markGrocery(checkId);
      // Update local state
      setItems(prev => prev.map(i =>
        i.id === checkId ? { ...i, added_to_grocery: true } : i
      ));
      const msg = res.error === 'already_exists'
        ? `${itemName} already in grocery list`
        : `${itemName} added to grocery list`;
      setGroceryMsg(msg);
      setTimeout(() => setGroceryMsg(''), 1500);
    }
  }

  useEffect(() => {
    async function load() {
      const res = await api.current();
      if (!res.error && Array.isArray(res)) setItems(res);
      setLoading(false);
    }
    load();
  }, []);

  async function handleToggle(checkId) {
    setItems(prev => prev.map(item =>
      item.id === checkId ? { ...item, is_checked: !item.is_checked } : item
    ));
    const res = await api.toggle(checkId);
    if (res.error) {
      setItems(prev => prev.map(item =>
        item.id === checkId ? { ...item, is_checked: !item.is_checked } : item
      ));
    }
  }

  async function handleAdd() {
    if (!newItem.trim()) return;
    const res = await api.add(newItem.trim());
    if (res.error === 'already_exists') {
      setError(res.message);
      setTimeout(() => setError(''), 2000);
      return;
    }
    if (!res.error) {
      setItems(prev => [...prev, { ...res, is_low: false }]);
      setNewItem('');
      setShowAdd(false);
      setError('');
    }
  }

  async function handleRemove(checkId) {
    setItems(prev => prev.filter(i => i.id !== checkId));
    const res = await api.remove(checkId);
    if (res.error) {
      // Reload on failure
      const reload = await api.current();
      if (!reload.error && Array.isArray(reload)) setItems(reload);
    }
  }

  if (loading || items.length === 0) return null;

  const allChecked = items.every(i => i.is_checked);

  return (
    <>
      <div className="section-header">
        <div className="section-title">Essentials Check</div>
      </div>

      <div style={{
        display: 'flex', gap: 8, padding: '0 16px', marginBottom: 8,
        overflowX: 'auto', scrollbarWidth: 'none',
      }}>
        {items.map((item) => {
          const emoji = getEmoji(item.item);
          const isLow = item.is_low;

          return (
            <div key={item.id} style={{
              minWidth: 82, textAlign: 'center', position: 'relative',
              padding: '12px 8px 10px',
              background: item.is_checked ? '#F0FFF8' : isLow ? '#FFF5F5' : 'white',
              borderRadius: 14,
              border: isLow && !item.is_checked ? '1.5px solid #FECACA' : '0.5px solid #EDE8E3',
              flexShrink: 0, cursor: 'pointer',
              transition: 'background 0.2s, border 0.2s',
            }}>
              {/* Remove button */}
              <div
                onClick={(e) => { e.stopPropagation(); handleRemove(item.id); }}
                style={{
                  position: 'absolute', top: 4, right: 4,
                  width: 16, height: 16, borderRadius: '50%',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 9, color: '#ccc', cursor: 'pointer',
                }}
              >
                ✕
              </div>

              {/* Tap area for toggle */}
              <div onClick={() => handleToggle(item.id)}>
                {/* Emoji + check overlay */}
                <div style={{
                  width: 38, height: 38, borderRadius: '50%',
                  margin: '0 auto 6px', position: 'relative',
                  background: item.is_checked ? '#D1FAE5' : isLow ? '#FEE2E2' : '#FAF7F5',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 18, transition: 'background 0.2s',
                }}>
                  {item.is_checked ? (
                    <span style={{ fontSize: 16, color: '#2D7A5B' }}>✓</span>
                  ) : (
                    emoji
                  )}
                  {/* Low stock red dot */}
                  {isLow && !item.is_checked && (
                    <div style={{
                      position: 'absolute', top: 0, right: 0,
                      width: 8, height: 8, borderRadius: '50%',
                      background: '#EF4444', border: '1.5px solid white',
                    }} />
                  )}
                </div>

                {/* Label */}
                <div style={{
                  fontSize: 10.5, fontWeight: 500, lineHeight: 1.3,
                  color: item.is_checked ? '#2D7A5B' : isLow ? '#DC2626' : '#1a1a1a',
                }}>
                  {item.item}
                </div>
                {isLow && !item.is_checked && (
                  <div style={{ fontSize: 9, color: '#EF4444', marginTop: 2 }}>Low</div>
                )}
              </div>

              {/* Add to grocery button */}
              {!item.is_checked && !item.added_to_grocery && (
                <div
                  onClick={(e) => handleAddToGrocery(item.id, item.item, e)}
                  style={{
                    position: 'absolute', bottom: 4, right: 4,
                    width: 20, height: 20, borderRadius: '50%',
                    background: '#FAF7F5',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: 11, cursor: 'pointer',
                  }}
                  title="Add to grocery list"
                >
                  🛒
                </div>
              )}
            </div>
          );
        })}

        {/* Add button card */}
        {!showAdd && (
          <div
            onClick={() => setShowAdd(true)}
            style={{
              minWidth: 60, textAlign: 'center', padding: '12px 8px 10px',
              borderRadius: 14, border: '1.5px dashed #EDE8E3',
              flexShrink: 0, cursor: 'pointer',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              color: '#aaa', fontSize: 11,
            }}
          >
            <div style={{ fontSize: 20, marginBottom: 4 }}>+</div>
            Add
          </div>
        )}
      </div>

      {/* Grocery added message */}
      {groceryMsg && (
        <div style={{
          padding: '6px 16px', marginBottom: 4,
          fontSize: 12, color: '#2D7A5B', textAlign: 'center',
        }}>
          {groceryMsg}
        </div>
      )}

      {/* Add input */}
      {showAdd && (
        <div style={{ padding: '0 16px', marginBottom: 8 }}>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              value={newItem}
              onChange={(e) => setNewItem(e.target.value)}
              placeholder="e.g. Pacifier, Cream"
              onKeyDown={(e) => e.key === 'Enter' && handleAdd()}
              style={{
                flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 8,
                padding: '8px 10px', fontSize: 13, outline: 'none',
              }}
              autoFocus
            />
            <button onClick={handleAdd} style={{
              background: '#C2855A', border: 'none', borderRadius: 8,
              padding: '8px 14px', color: 'white', fontSize: 13, cursor: 'pointer',
            }}>
              Add
            </button>
            <button onClick={() => { setShowAdd(false); setNewItem(''); setError(''); }} style={{
              background: 'none', border: '0.5px solid #EDE8E3', borderRadius: 8,
              padding: '8px 10px', color: '#888', fontSize: 13, cursor: 'pointer',
            }}>
              ✕
            </button>
          </div>
          {error && (
            <div style={{ fontSize: 12, color: '#DC3545', marginTop: 4 }}>{error}</div>
          )}
        </div>
      )}

      {/* All checked message */}
      {allChecked && (
        <div style={{ padding: '0 16px', marginBottom: 12 }}>
          <div style={{ fontSize: 12, color: '#2D7A5B', textAlign: 'center' }}>
            All stocked up for today
          </div>
        </div>
      )}
    </>
  );
}
