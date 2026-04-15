export default function RecoveryExerciseSection({ data }) {
  const exercise = data || {};
  if (!exercise.activity) return null;

  return (
    <div style={{ padding: '0 16px', marginBottom: 16 }}>
      <div style={{
        background: '#F0FFF8', borderRadius: 14, padding: '14px 16px',
        display: 'flex', alignItems: 'center', gap: 12,
      }}>
        <div style={{
          width: 40, height: 40, borderRadius: 12,
          background: '#D1FAE5', display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 20,
        }}>
          🚶‍♀️
        </div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, fontSize: 14, color: '#2D7A5B' }}>{exercise.activity}</div>
          <div style={{ fontSize: 12, color: '#2D7A5B', marginTop: 2 }}>
            {exercise.time && `${exercise.time}`}
            {exercise.duration && ` · ${exercise.duration}`}
          </div>
          {exercise.note && <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{exercise.note}</div>}
        </div>
      </div>
    </div>
  );
}
