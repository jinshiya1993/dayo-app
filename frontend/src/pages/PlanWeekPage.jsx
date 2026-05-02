import { useNavigate } from 'react-router-dom';
import WeeklyMealInline from '../components/WeeklyMealInline';

export default function PlanWeekPage() {
  const navigate = useNavigate();

  return (
    <div style={shellStyle}>
      <div style={topBarStyle}>
        <button onClick={() => navigate(-1)} style={backBtnStyle} aria-label="Back">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
               strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M15 18l-6-6 6-6" />
          </svg>
        </button>
        <div style={topTitleStyle}>Plan week</div>
        <div style={{ width: 40 }} />
      </div>

      <WeeklyMealInline onClose={() => navigate('/')} />
    </div>
  );
}

const shellStyle = {
  display: 'flex', flexDirection: 'column', minHeight: '100dvh',
  maxWidth: 430, margin: '0 auto', background: '#FAF7F5',
  paddingBottom: 96,
};
const topBarStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '12px 16px',
};
const backBtnStyle = {
  width: 40, height: 40, borderRadius: '50%', background: 'white',
  border: '1px solid #EDE8E3', display: 'flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', color: '#1A1A1A',
};
const topTitleStyle = { fontSize: 12, color: '#5A5A5A' };
