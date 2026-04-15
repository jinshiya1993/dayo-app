import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { plans, profile as profileApi } from '../services/api';

const LOADING_TEXTS = [
  'Setting up your plan...',
  'Learning your preferences...',
  'Planning your meals...',
  'Organizing your schedule...',
  'Almost ready...',
];

export default function OnboardingLoading() {
  const navigate = useNavigate();
  const location = useLocation();
  const { name, city, wakeTime, sleepTime, profileData: passedProfileData } = location.state || {};
  const [textIndex, setTextIndex] = useState(0);

  // Cycle loading text every 2 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      setTextIndex((prev) => (prev + 1) % LOADING_TEXTS.length);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

  // Save city/wake/sleep from step 1, then generate plan
  useEffect(() => {
    async function setup() {
      // Update profile with step 1 data that the chat agent didn't handle
      if (city || wakeTime || sleepTime) {
        const update = {};
        if (city) update.location_city = city;
        if (wakeTime) update.wake_time = wakeTime;
        if (sleepTime) update.sleep_time = sleepTime;
        await profileApi.update(update);
      }

      // Generate today's plan
      await plans.generate();

      // Navigate to preview (not dashboard)
      navigate('/onboarding/preview', {
        replace: true,
        state: { profileData: passedProfileData, name },
      });
    }

    setup();
  }, []);

  return (
    <div style={{
      minHeight: '100vh', background: '#1a1a1a',
      display: 'flex', flexDirection: 'column',
      alignItems: 'center', justifyContent: 'center',
      animation: 'fadeIn 0.6s ease-in',
    }}>
      {/* Logo */}
      <div style={{
        fontFamily: 'Georgia, serif', fontSize: 40, fontWeight: 700,
        color: '#C2855A', marginBottom: 32,
      }}>
        dayo
      </div>

      {/* Pulsing dots */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 24 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{
            width: 8, height: 8, borderRadius: '50%',
            background: '#C2855A',
            animation: `loadPulse 1.4s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>

      {/* Cycling text */}
      <div style={{
        color: '#888', fontSize: 14,
        transition: 'opacity 0.3s',
        textAlign: 'center',
      }}>
        {LOADING_TEXTS[textIndex]}
      </div>

      {name && (
        <div style={{ color: '#555', fontSize: 12, marginTop: 16 }}>
          Getting everything ready for you, {name}
        </div>
      )}

      <style>{`
        @keyframes loadPulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.4); }
        }
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
      `}</style>
    </div>
  );
}
