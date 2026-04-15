import { useNavigate } from 'react-router-dom';

export default function LogoBar({ displayName }) {
  const navigate = useNavigate();
  const initial = displayName ? displayName[0].toUpperCase() : '?';

  return (
    <div className="logo-bar">
      <div className="logo">da<span>yo</span></div>
      <div className="logo-bar-right">
        <button className="icon-btn" aria-label="Search">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <path d="M21 21l-4.35-4.35" />
          </svg>
        </button>
        <div className="avatar" onClick={() => navigate('/profile')}>{initial}</div>
      </div>
    </div>
  );
}
