import { useState, useEffect } from 'react';
import { Routes, Route, Navigate, useLocation } from 'react-router-dom';
import './styles/design.css';
import BottomNav from './components/BottomNav';
import Dashboard from './pages/Dashboard';
import ChatPage from './pages/ChatPage';
import SchedulePage from './pages/SchedulePage';
import ProfilePage from './pages/ProfilePage';
import AuthPage from './pages/AuthPage';
import OnboardingPage from './pages/OnboardingPage';
import OnboardingChat from './pages/OnboardingChat';
import OnboardingPreview from './pages/OnboardingPreview';
import CustomiseDashboard from './pages/CustomiseDashboard';
import { profile } from './services/api';

function App() {
  const [authed, setAuthed] = useState(null);
  const [onboarded, setOnboarded] = useState(true);
  const location = useLocation();

  useEffect(() => {
    // Don't re-check auth while on onboarding screens —
    // prevents redirect race condition when onboarding_complete becomes true
    if (location.pathname.startsWith('/onboarding')) return;
    // Leaving onboarding before state has refreshed — show loader instead of
    // flashing the OnboardingPage fallback while checkAuth is in flight.
    if (!onboarded) setAuthed(null);
    checkAuth();
  }, [location.pathname]);

  async function checkAuth() {
    const result = await profile.get();
    if (result.error === 'unauthorized') {
      setAuthed(false);
    } else if (!result.error) {
      setAuthed(true);
      setOnboarded(result.onboarding_complete);
    } else {
      setAuthed(false);
    }
  }

  if (authed === null) {
    return (
      <div className="app-shell">
        <div className="loading" style={{ minHeight: '100dvh' }}>
          <div className="spinner" />
        </div>
      </div>
    );
  }

  if (!authed) {
    return (
      <div className="app-shell">
        <Routes>
          <Route path="/auth" element={<AuthPage />} />
          <Route path="*" element={<Navigate to="/auth" replace />} />
        </Routes>
      </div>
    );
  }

  // Authenticated but not onboarded
  if (!onboarded) {
    return (
      <div className="app-shell">
        <Routes>
          <Route path="/onboarding" element={<OnboardingPage />} />
          <Route path="/onboarding/chat" element={<OnboardingChat />} />
          <Route path="/onboarding/preview" element={<OnboardingPreview />} />
          <Route path="*" element={<Navigate to="/onboarding" replace />} />
        </Routes>
      </div>
    );
  }

  // Authenticated + onboarded
  const showNav = !location.pathname.startsWith('/onboarding') && !location.pathname.startsWith('/settings');

  return (
    <div className="app-shell">
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/chat" element={<ChatPage />} />
        <Route path="/schedule" element={<SchedulePage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/settings/dashboard" element={<CustomiseDashboard />} />
        <Route path="/onboarding/preview" element={<OnboardingPreview />} />
        <Route path="/auth" element={<Navigate to="/" replace />} />
        <Route path="/onboarding" element={<Navigate to="/" replace />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
      {showNav && <BottomNav />}
    </div>
  );
}

export default App;
