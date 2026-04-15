import { useState, useEffect, useCallback } from 'react';
import { grocery as groceryApi, pantry as pantryApi } from '../../services/api';

export default function GrocerySection({ profileData }) {
  const [groceryList, setGroceryList] = useState(null);
  const [loading, setLoading] = useState(false);
  const [generating, setGenerating] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [showAddInput, setShowAddInput] = useState(false);
  const [newItemName, setNewItemName] = useState('');
  const [newItemQty, setNewItemQty] = useState('');
  const [duplicateMsg, setDuplicateMsg] = useState('');
  const [editingQty, setEditingQty] = useState(null);
  const [editQtyValue, setEditQtyValue] = useState('');
  const [showHistory, setShowHistory] = useState(false);
  const [history, setHistory] = useState([]);
  const [showDoneConfirm, setShowDoneConfirm] = useState(false);
  const [activeFilter, setActiveFilter] = useState('all');
  const [showAll, setShowAll] = useState(false);

  const COLLAPSED_LIMIT = 8;

  // Load current grocery list
  const loadGrocery = useCallback(async () => {
    setLoading(true);
    const res = await groceryApi.current();
    if (!res.error) setGroceryList(res);
    else setGroceryList(null);
    setLoading(false);
  }, []);

  useEffect(() => { loadGrocery(); }, [loadGrocery]);

  async function handleGenerate() {
    setGenerating(true);
    const res = await groceryApi.generate();
    if (!res.error) {
      const current = await groceryApi.current();
      if (!current.error) setGroceryList(current);
    }
    setGenerating(false);
  }

  async function handleToggleCheck(itemId) {
    if (!groceryList) return;
    const res = await groceryApi.toggleItem(groceryList.id, itemId);
    if (!res.error) {
      setGroceryList(prev => ({
        ...prev,
        items: prev.items.map(i => i.id === itemId ? { ...i, checked: res.checked } : i),
      }));
    }
  }

  async function handleAddItem() {
    if (!newItemName.trim() || !groceryList) return;
    const res = await groceryApi.addItem(groceryList.id, newItemName.trim(), newItemQty.trim(), 'other');
    if (res.error === 'already_exists') {
      setDuplicateMsg(res.message);
      setTimeout(() => setDuplicateMsg(''), 2000);
      return;
    }
    if (!res.error) {
      setGroceryList(prev => ({ ...prev, items: [...prev.items, res] }));
      setNewItemName('');
      setNewItemQty('');
      setShowAddInput(false);
      setDuplicateMsg('');
    }
  }

  async function handleDeleteItem(itemId) {
    if (!groceryList) return;
    const res = await groceryApi.deleteItem(groceryList.id, itemId);
    if (!res.error) {
      setGroceryList(prev => ({
        ...prev,
        items: prev.items.filter(i => i.id !== itemId),
      }));
    }
  }

  async function handleUpdateQuantity(itemId) {
    if (!groceryList || !editQtyValue.trim()) { setEditingQty(null); return; }
    const res = await groceryApi.updateQuantity(groceryList.id, itemId, editQtyValue.trim());
    if (!res.error) {
      setGroceryList(prev => ({
        ...prev,
        items: prev.items.map(i => i.id === itemId ? { ...i, quantity: res.quantity } : i),
      }));
    }
    setEditingQty(null);
  }

  function handleDoneShopping() {
    const unchecked = items.filter(i => !i.checked).length;
    if (unchecked > 0) {
      setShowDoneConfirm(true);
    } else {
      confirmDone();
    }
  }

  async function confirmDone() {
    const res = await groceryApi.done();
    if (!res.error) {
      setGroceryList(null);
      setShowDoneConfirm(false);
      setExpanded(false);
      setHistory([]);
    }
  }

  async function handleToggleHistory() {
    if (!showHistory && history.length === 0) {
      const res = await groceryApi.list();
      if (!res.error && Array.isArray(res)) {
        setHistory(res);
      }
    }
    setShowHistory(!showHistory);
  }

  function handleShare() {
    if (!groceryList) return;
    const unchecked = items.filter(i => !i.checked);
    const shareGrouped = {};
    unchecked.forEach(i => {
      const cat = categoryLabels[i.category] || i.category;
      if (!shareGrouped[cat]) shareGrouped[cat] = [];
      shareGrouped[cat].push(`${i.name}${i.quantity ? ' — ' + i.quantity : ''}`);
    });
    let text = '🛒 Grocery List\n\n';
    Object.entries(shareGrouped).forEach(([cat, items]) => {
      text += `${cat}\n`;
      items.forEach(i => { text += `  ☐ ${i}\n`; });
      text += '\n';
    });

    if (navigator.share) {
      navigator.share({ title: 'Grocery List', text }).catch(() => {});
    } else {
      navigator.clipboard.writeText(text).then(() => {
        setDuplicateMsg('Copied to clipboard!');
        setTimeout(() => setDuplicateMsg(''), 2000);
      });
    }
  }

  async function handleAddToPantry(itemName, itemId) {
    await pantryApi.toggle(itemName);
    await handleDeleteItem(itemId);
  }

  function isNearShoppingDay() {
    const groceryDay = profileData?.grocery_day;
    if (!groceryDay) return false;
    const dayNames = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
    const today = new Date().getDay();
    const shopDay = dayNames.indexOf(groceryDay);
    if (shopDay === -1) return false;
    const diff = Math.abs(today - shopDay);
    return diff <= 1 || diff >= 6;
  }

  if (loading) return null;

  // Generating state
  if (generating) {
    return (
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{
          background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
          padding: '20px 16px', textAlign: 'center',
        }}>
          <div className="spinner" style={{ margin: '0 auto 8px', width: 24, height: 24 }} />
          <div style={{ fontSize: 13, color: '#888' }}>Generating your grocery list from this week's meals...</div>
        </div>
      </div>
    );
  }

  // No list — sorted state with quick-add option
  if (!groceryList) {
    async function handleQuickAdd() {
      if (!newItemName.trim()) return;
      const res = await groceryApi.quickAdd(newItemName.trim(), newItemQty.trim());
      if (res.error === 'already_exists') {
        setDuplicateMsg(res.message);
        setTimeout(() => setDuplicateMsg(''), 2000);
        return;
      }
      if (!res.error) {
        setGroceryList(res);
        setNewItemName('');
        setNewItemQty('');
        setShowAddInput(false);
        setDuplicateMsg('');
      }
    }

    return (
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div style={{
          background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
          padding: '12px 16px',
        }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 16 }}>✓</span>
              <span style={{ fontSize: 13, color: '#888' }}>Grocery sorted</span>
            </div>
          </div>

          {!showAddInput ? (
            <div
              onClick={() => setShowAddInput(true)}
              style={{
                display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6,
                border: '1.5px dashed #EDE8E3', borderRadius: 10,
                padding: 9, marginTop: 10,
                color: '#aaa', fontSize: 12, cursor: 'pointer',
              }}
            >
              + Need something? Add it here
            </div>
          ) : (
            <div style={{ marginTop: 10 }}>
              <div style={{ display: 'flex', gap: 6, minWidth: 0 }}>
                <input
                  value={newItemName}
                  onChange={(e) => setNewItemName(e.target.value)}
                  placeholder="Item name"
                  onKeyDown={(e) => e.key === 'Enter' && handleQuickAdd()}
                  style={{
                    flex: 2, minWidth: 0, border: '0.5px solid #EDE8E3', borderRadius: 8,
                    padding: '8px 10px', fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  }}
                  autoFocus
                />
                <input
                  value={newItemQty}
                  onChange={(e) => setNewItemQty(e.target.value)}
                  placeholder="Qty"
                  onKeyDown={(e) => e.key === 'Enter' && handleQuickAdd()}
                  style={{
                    width: 60, flexShrink: 0, border: '0.5px solid #EDE8E3', borderRadius: 8,
                    padding: '8px 6px', fontSize: 13, outline: 'none', boxSizing: 'border-box',
                  }}
                />
                <button onClick={handleQuickAdd} style={{
                  background: '#C2855A', border: 'none', borderRadius: 8,
                  padding: '8px 12px', color: 'white', fontSize: 13, cursor: 'pointer',
                  flexShrink: 0,
                }}>
                  Add
                </button>
              </div>
              {duplicateMsg && (
                <div style={{ fontSize: 12, color: '#DC3545', marginTop: 6, textAlign: 'center' }}>
                  {duplicateMsg}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- Active grocery list ---
  const items = groceryList.items || [];
  const total = items.length;
  const bought = items.filter(i => i.checked).length;

  const categoryLabels = {
    produce: '🥬 Fruits & Vegetables',
    dairy: '🥛 Dairy',
    grains: '🌾 Grains & Cereals',
    protein: '🍗 Protein',
    spices: '🧂 Spices & Condiments',
    snacks: '🍪 Snacks',
    other: '📦 Other',
  };

  const categoryEmojis = {
    produce: '🥬',
    dairy: '🥛',
    grains: '🌾',
    protein: '🍗',
    spices: '🧂',
    snacks: '🍪',
    other: '📦',
  };

  // Group items by category
  const grouped = {};
  items.forEach(item => {
    const cat = item.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  });
  const categoryOrder = ['produce', 'protein', 'dairy', 'grains', 'spices', 'snacks', 'other'];
  const sortedCategories = categoryOrder.filter(c => grouped[c]);

  // Filter items based on active pill
  const filteredCategories = activeFilter === 'all'
    ? sortedCategories
    : sortedCategories.filter(c => c === activeFilter);

  const filteredItems = filteredCategories.flatMap(c => grouped[c]);
  const visibleItems = showAll ? filteredItems : filteredItems.slice(0, COLLAPSED_LIMIT);
  const remainingCount = filteredItems.length - COLLAPSED_LIMIT;

  function renderItem(item) {
    return (
      <div key={item.id} style={{
        display: 'flex', alignItems: 'center', gap: 10, padding: '9px 0',
        borderBottom: '0.5px solid #f5f1ed',
      }}>
        <div onClick={() => handleToggleCheck(item.id)} style={{
          width: 20, height: 20, borderRadius: '50%',
          border: item.checked ? 'none' : '1.5px solid #EDE8E3',
          background: item.checked ? '#C2855A' : 'white',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          color: 'white', fontSize: 10, flexShrink: 0, cursor: 'pointer',
        }}>
          {item.checked && '✓'}
        </div>
        <div style={{ flex: 1 }}>
          <span style={{
            fontSize: 13.5,
            textDecoration: item.checked ? 'line-through' : 'none',
            color: item.checked ? '#bbb' : '#1a1a1a',
          }}>
            {item.name}
          </span>
          {editingQty === item.id ? (
            <input
              value={editQtyValue}
              onChange={(e) => setEditQtyValue(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleUpdateQuantity(item.id)}
              onBlur={() => handleUpdateQuantity(item.id)}
              style={{
                marginLeft: 6, width: 60, fontSize: 11, border: '1px solid #C2855A',
                borderRadius: 6, padding: '2px 6px', outline: 'none',
              }}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          ) : (
            item.quantity && (
              <span
                onClick={(e) => { e.stopPropagation(); setEditingQty(item.id); setEditQtyValue(item.quantity); }}
                style={{
                  fontSize: 11, color: '#C2855A', marginLeft: 6,
                  cursor: 'pointer', borderBottom: '1px dashed #C2855A',
                }}
              >
                {item.quantity}
              </span>
            )
          )}
        </div>
        <button
          onClick={() => handleDeleteItem(item.id)}
          style={{ background: 'none', border: 'none', fontSize: 10, cursor: 'pointer', color: '#ccc', padding: '2px 4px' }}
          title="Remove"
        >
          ✕
        </button>
      </div>
    );
  }

  // --- COLLAPSED VIEW ---
  if (!expanded) {
    return (
      <div style={{ padding: '0 16px', marginBottom: 16 }}>
        <div
          onClick={() => { setExpanded(true); setActiveFilter('all'); setShowAll(false); }}
          style={{
            background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
            padding: '14px 16px', cursor: 'pointer',
            transition: 'box-shadow 0.2s',
          }}
        >
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <div style={{
                width: 36, height: 36, borderRadius: 10, background: '#FFF3EB',
                display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
              }}>
                🛒
              </div>
              <div>
                <div style={{ fontFamily: 'Georgia, serif', fontSize: 15, fontWeight: 600 }}>Grocery List</div>
                <div style={{ fontSize: 12, color: '#888', marginTop: 1 }}>
                  {bought === 0
                    ? `${total} items this week`
                    : `${bought} of ${total} bought`}
                </div>
              </div>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                background: '#FFF3EB', padding: '3px 10px', borderRadius: 12,
                fontSize: 11, fontWeight: 600, color: '#C2855A',
              }}>
                {bought}/{total}
              </div>
              <span style={{ color: '#C2855A', fontSize: 18, transition: 'transform 0.2s' }}>›</span>
            </div>
          </div>
          <div style={{ height: 4, borderRadius: 2, background: '#EDE8E3', marginTop: 12 }}>
            <div style={{
              height: 4, borderRadius: 2, background: '#C2855A',
              width: total > 0 ? `${(bought / total) * 100}%` : '0%',
              transition: 'width 0.3s',
            }} />
          </div>
        </div>
      </div>
    );
  }

  // --- EXPANDED VIEW ---
  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: 'white', borderRadius: 14, border: '0.5px solid #EDE8E3',
        padding: '16px', transition: 'all 0.2s',
      }}>
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
          <div
            onClick={() => { setExpanded(false); setShowAddInput(false); setShowDoneConfirm(false); setShowHistory(false); }}
            style={{ display: 'flex', alignItems: 'center', gap: 10, cursor: 'pointer' }}
          >
            <div style={{
              width: 36, height: 36, borderRadius: 10, background: '#FFF3EB',
              display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 18,
            }}>
              🛒
            </div>
            <div>
              <div style={{ fontFamily: 'Georgia, serif', fontSize: 15, fontWeight: 600 }}>Grocery List</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 1 }}>{bought} / {total} bought</div>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <button
              onClick={handleShare}
              style={{ background: 'none', border: 'none', fontSize: 13, cursor: 'pointer', opacity: 0.5, padding: '4px' }}
              title="Share list"
            >
              📤
            </button>
            <span
              onClick={() => { setExpanded(false); setShowAddInput(false); setShowDoneConfirm(false); setShowHistory(false); }}
              style={{
                color: '#C2855A', fontSize: 18, cursor: 'pointer',
                transform: 'rotate(90deg)', display: 'inline-block',
                transition: 'transform 0.2s',
              }}
            >
              ›
            </span>
          </div>
        </div>

        {/* Progress bar */}
        <div style={{ height: 4, borderRadius: 2, background: '#EDE8E3', marginBottom: 14 }}>
          <div style={{
            height: 4, borderRadius: 2, background: '#C2855A',
            width: total > 0 ? `${(bought / total) * 100}%` : '0%',
            transition: 'width 0.3s',
          }} />
        </div>

        {/* Category pill filters */}
        <div style={{ display: 'flex', gap: 6, marginBottom: 14, overflowX: 'auto', paddingBottom: 2 }}>
          <button
            onClick={() => { setActiveFilter('all'); setShowAll(false); }}
            style={{
              padding: '5px 12px', borderRadius: 20, fontSize: 11, fontWeight: 500,
              border: activeFilter === 'all' ? '1px solid #C2855A' : '1px solid #EDE8E3',
              background: activeFilter === 'all' ? '#C2855A' : 'white',
              color: activeFilter === 'all' ? 'white' : '#888',
              cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            }}
          >
            All <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 3 }}>{total}</span>
          </button>
          {sortedCategories.map(cat => (
            <button
              key={cat}
              onClick={() => { setActiveFilter(cat); setShowAll(false); }}
              style={{
                padding: '5px 12px', borderRadius: 20, fontSize: 11, fontWeight: 500,
                border: activeFilter === cat ? '1px solid #C2855A' : '1px solid #EDE8E3',
                background: activeFilter === cat ? '#C2855A' : 'white',
                color: activeFilter === cat ? 'white' : '#888',
                cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
              }}
            >
              {categoryEmojis[cat]} <span style={{ fontSize: 10, opacity: 0.7, marginLeft: 3 }}>{grouped[cat].length}</span>
            </button>
          ))}
        </div>

        {/* Items */}
        {activeFilter === 'all' ? (
          // Show with category headers
          (() => {
            let count = 0;
            return filteredCategories.map(cat => {
              const catItems = grouped[cat];
              const itemsToShow = [];
              for (const item of catItems) {
                if (!showAll && count >= COLLAPSED_LIMIT) break;
                itemsToShow.push(item);
                count++;
              }
              if (itemsToShow.length === 0) return null;
              return (
                <div key={cat}>
                  <div style={{
                    fontSize: 11, fontWeight: 600, color: '#aaa', padding: '12px 0 4px',
                    textTransform: 'uppercase', letterSpacing: 0.5,
                  }}>
                    {categoryLabels[cat] || cat}
                  </div>
                  {itemsToShow.map(item => renderItem(item))}
                </div>
              );
            });
          })()
        ) : (
          // Filtered — no category headers needed
          visibleItems.map(item => renderItem(item))
        )}

        {/* Show more / less */}
        {!showAll && remainingCount > 0 && (
          <button onClick={() => setShowAll(true)} style={{
            width: '100%', padding: '10px', border: 'none', background: 'none',
            color: '#C2855A', fontSize: 12, fontWeight: 600, cursor: 'pointer', marginTop: 4,
          }}>
            ↓ {remainingCount} more items
          </button>
        )}
        {showAll && filteredItems.length > COLLAPSED_LIMIT && (
          <button onClick={() => setShowAll(false)} style={{
            width: '100%', padding: '10px', border: 'none', background: 'none',
            color: '#C2855A', fontSize: 12, fontWeight: 600, cursor: 'pointer', marginTop: 4,
          }}>
            Show less
          </button>
        )}

        {/* Duplicate message */}
        {duplicateMsg && (
          <div style={{ fontSize: 12, color: '#DC3545', marginTop: 6, textAlign: 'center' }}>
            {duplicateMsg}
          </div>
        )}

        {/* Action buttons row */}
        <div style={{ display: 'flex', gap: 8, marginTop: 14 }}>
          {!showAddInput ? (
            <button onClick={() => setShowAddInput(true)} style={{
              flex: 1, padding: '9px', border: '1.5px dashed #EDE8E3', borderRadius: 10,
              background: 'none', color: '#888', fontSize: 12, cursor: 'pointer',
            }}>
              + Add item
            </button>
          ) : (
            <div style={{ flex: 1 }} />
          )}
          {!showDoneConfirm && (
            <button onClick={handleDoneShopping} style={{
              flex: 1, padding: '9px', border: 'none', borderRadius: 10,
              background: '#C2855A', color: 'white', fontSize: 12, fontWeight: 600, cursor: 'pointer',
            }}>
              Done shopping
            </button>
          )}
        </div>

        {/* Add item input */}
        {showAddInput && (
          <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
            <input
              value={newItemName}
              onChange={(e) => setNewItemName(e.target.value)}
              placeholder="Item name"
              onKeyDown={(e) => e.key === 'Enter' && handleAddItem()}
              style={{
                flex: 2, border: '0.5px solid #EDE8E3', borderRadius: 8,
                padding: '8px 10px', fontSize: 13, outline: 'none',
              }}
              autoFocus
            />
            <input
              value={newItemQty}
              onChange={(e) => setNewItemQty(e.target.value)}
              placeholder="Qty"
              onKeyDown={(e) => e.key === 'Enter' && handleAddItem()}
              style={{
                flex: 1, border: '0.5px solid #EDE8E3', borderRadius: 8,
                padding: '8px 10px', fontSize: 13, outline: 'none',
              }}
            />
            <button onClick={handleAddItem} style={{
              background: '#C2855A', border: 'none', borderRadius: 8,
              padding: '8px 14px', color: 'white', fontSize: 13, cursor: 'pointer',
            }}>
              Add
            </button>
          </div>
        )}

        {/* Done shopping confirm */}
        {showDoneConfirm && (
          <div style={{ marginTop: 10, padding: '12px', background: '#FFF8F0', borderRadius: 10 }}>
            <div style={{ fontSize: 13, color: '#9B4000', marginBottom: 8 }}>
              {items.filter(i => !i.checked).length} items are still unchecked. Mark as done anyway?
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={confirmDone} style={{
                flex: 1, padding: '8px', background: '#C2855A', color: 'white',
                border: 'none', borderRadius: 8, fontSize: 13, cursor: 'pointer',
              }}>
                Yes, I'm done
              </button>
              <button onClick={() => setShowDoneConfirm(false)} style={{
                flex: 1, padding: '8px', background: 'white', color: '#888',
                border: '0.5px solid #EDE8E3', borderRadius: 8, fontSize: 13, cursor: 'pointer',
              }}>
                Not yet
              </button>
            </div>
          </div>
        )}

        {/* History toggle */}
        <button onClick={handleToggleHistory} style={{
          width: '100%', padding: '8px', border: 'none', background: 'none',
          color: '#888', fontSize: 12, cursor: 'pointer', marginTop: 4,
        }}>
          {showHistory ? 'Hide history' : 'Past lists'}
        </button>

        {/* History list */}
        {showHistory && history.length > 0 && (
          <div style={{ marginTop: 4 }}>
            {history.filter(h => h.id !== groceryList.id).slice(0, 5).map(h => (
              <div key={h.id} style={{
                display: 'flex', justifyContent: 'space-between', alignItems: 'center',
                padding: '8px 0', borderBottom: '0.5px solid #EDE8E3',
              }}>
                <div>
                  <div style={{ fontSize: 13, fontWeight: 500 }}>
                    Week of {new Date(h.week_start_date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
                  </div>
                  <div style={{ fontSize: 11, color: '#888' }}>{h.item_count} items</div>
                </div>
              </div>
            ))}
            {history.filter(h => h.id !== groceryList.id).length === 0 && (
              <div style={{ fontSize: 12, color: '#888', textAlign: 'center', padding: 8 }}>No past lists yet</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
