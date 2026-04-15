export default function ExerciseSection({ data }) {
  const exercise = data || {};

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: '#F0FFF8', borderRadius: 14, padding: '14px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 10,
          background: '#D1FAE5', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 20,
        }}>
          🏋️
        </div>
        <div style={{ flex: 1 }}>
          {exercise.activity ? (
            <>
              <div style={{ fontWeight: 600, fontSize: 14, color: '#2D7A5B' }}>{exercise.activity}</div>
              <div style={{ fontSize: 12, color: '#2D7A5B', marginTop: 2 }}>
                {exercise.time && `${exercise.time}`}
                {exercise.duration && ` · ${exercise.duration}`}
              </div>
            </>
          ) : (
            <>
              <div style={{ fontWeight: 600, fontSize: 14, color: '#2D7A5B' }}>Fitness today</div>
              <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>Generate a plan to see your workout</div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
