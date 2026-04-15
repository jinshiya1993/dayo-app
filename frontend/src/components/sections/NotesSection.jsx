export default function NotesSection({ data }) {
  if (!data) return null;

  return (
    <div style={{ padding: '0 16px', marginBottom: 14 }}>
      <div style={{
        background: '#FFF8F0', borderRadius: 14, padding: '12px 14px',
        fontSize: 13, color: '#9B4000', display: 'flex', gap: 8, alignItems: 'flex-start',
      }}>
        <span>💡</span>
        <span>{data}</span>
      </div>
    </div>
  );
}
