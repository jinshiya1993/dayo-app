const categoryEmojis = {
  produce: '🥬',
  dairy: '🥛',
  grains: '🌾',
  protein: '🥩',
  spices: '🧂',
  snacks: '🍿',
  other: '🛒',
};

export default function GroceryGrid({ groceryList, onToggleItem }) {
  if (!groceryList || !groceryList.items || groceryList.items.length === 0) return null;

  // Group items by category
  const grouped = {};
  groceryList.items.forEach((item) => {
    const cat = item.category || 'other';
    if (!grouped[cat]) grouped[cat] = [];
    grouped[cat].push(item);
  });

  const categories = Object.keys(grouped);

  return (
    <>
      <div className="section-header">
        <div className="section-title">Grocery List</div>
      </div>
      <div className="grocery-grid">
        {categories.map((cat) => (
          <div className="grocery-card" key={cat}>
            <div className="grocery-emoji">{categoryEmojis[cat] || '🛒'}</div>
            <div className="grocery-category">{cat}</div>
            <ul className="grocery-items">
              {grouped[cat].map((item) => (
                <li className="grocery-item" key={item.id}>
                  <div
                    className={`grocery-check ${item.checked ? 'checked' : ''}`}
                    onClick={() => onToggleItem(groceryList.id, item.id)}
                  >
                    {item.checked ? '✓' : ''}
                  </div>
                  <span className={`grocery-item-text ${item.checked ? 'checked' : ''}`}>
                    {item.name}
                    {item.quantity && <span style={{ color: '#888', fontSize: 11 }}> ({item.quantity})</span>}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </>
  );
}
