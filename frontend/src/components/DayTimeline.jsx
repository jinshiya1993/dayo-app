const dotClass = {
  wake_up: 'personal',
  meal: 'meal',
  activity: 'activity',
  child_care: 'activity',
  travel: 'travel',
  work: 'work',
  study: 'personal',
  exercise: 'activity',
  free_time: 'personal',
  errand: 'travel',
  sleep: 'sleep',
};

export default function DayTimeline({ blocks }) {
  if (!blocks || blocks.length === 0) return null;

  return (
    <>
      <div className="section-header">
        <div className="section-title">Day Timeline</div>
      </div>
      <div className="timeline-card">
        {blocks.map((block) => (
          <div className="timeline-row" key={block.id}>
            <div className="timeline-time">{block.start_time?.slice(0, 5)}</div>
            <div className={`timeline-dot ${dotClass[block.block_type] || 'personal'}`} />
            <div className="timeline-text">
              <div className="timeline-title">{block.title}</div>
              {block.description && (
                <div className="timeline-desc">{block.description}</div>
              )}
              {block.completed && (
                <span className="timeline-chip completed">Done</span>
              )}
              {block.is_fixed && !block.completed && (
                <span className="timeline-chip upcoming">Fixed</span>
              )}
            </div>
          </div>
        ))}
      </div>
    </>
  );
}
