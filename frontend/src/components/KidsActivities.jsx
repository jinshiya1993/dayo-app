const activityEmojis = {
  child_care: '🧸',
  activity: '🎨',
  exercise: '⚽',
  study: '📚',
  free_time: '🎮',
};

function getCardStyle(block) {
  if (block.child) {
    // Alternate between terracotta and purple for different children
    return block.child % 2 === 0 ? 'purple' : 'terracotta';
  }
  if (block.block_type === 'exercise') return 'green';
  if (block.block_type === 'free_time') return 'brown';
  return 'terracotta';
}

function getLabel(block) {
  if (block.block_type === 'child_care') return 'Kids Time';
  if (block.block_type === 'activity') return 'Activity';
  if (block.block_type === 'exercise') return 'Exercise';
  if (block.block_type === 'free_time') return 'Me Time';
  return 'Activity';
}

export default function KidsActivities({ blocks }) {
  const activityBlocks = (blocks || []).filter((b) =>
    ['child_care', 'activity', 'exercise', 'free_time'].includes(b.block_type)
  );

  if (activityBlocks.length === 0) return null;

  return (
    <>
      <div className="section-header">
        <div className="section-title">Activities</div>
      </div>
      <div className="masonry-grid">
        {activityBlocks.map((block) => {
          const style = getCardStyle(block);
          return (
            <div className={`activity-card ${style}`} key={block.id}>
              <div className="activity-emoji-area">
                {activityEmojis[block.block_type] || '✨'}
              </div>
              <div className="activity-info">
                <div className="activity-label">{getLabel(block)}</div>
                <div className="activity-title">{block.title}</div>
                {block.description && (
                  <div className="activity-subtitle">{block.description}</div>
                )}
                <div className="activity-time-tag">
                  {block.start_time?.slice(0, 5)} - {block.end_time?.slice(0, 5)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </>
  );
}
