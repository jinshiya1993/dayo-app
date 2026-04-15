import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { profile as profileApi } from '../services/api';

export default function OnboardingPage() {
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [userType, setUserType] = useState('parent');
  const [customUserType, setCustomUserType] = useState('');
  const [city, setCity] = useState('');
  const [wakeTime, setWakeTime] = useState('06:00');
  const [sleepTime, setSleepTime] = useState('22:00');

  useEffect(() => {
    profileApi.get().then((p) => {
      if (p?.error) return;
      const prefill = p.display_name || p.username || '';
      if (prefill) setDisplayName(prefill);
      if (p.location_city) setCity(p.location_city);
      if (p.wake_time) setWakeTime(p.wake_time.slice(0, 5));
      if (p.sleep_time) setSleepTime(p.sleep_time.slice(0, 5));
    });
  }, []);

  function handleNext() {
    if (!displayName.trim()) return;
    navigate('/onboarding/chat', {
      state: {
        name: displayName.trim(),
        userType: userType === 'other' ? (customUserType.trim() || 'other') : userType,
        city,
        wakeTime,
        sleepTime,
      },
    });
  }

  return (
    <div className="app-shell" style={{ padding: '0 16px' }}>
      <div style={{ textAlign: 'center', padding: '24px 0 8px' }}>
        <div className="logo" style={{ fontSize: 28 }}>da<span>yo</span></div>
        <div style={{ color: '#888', fontSize: 13, marginTop: 4 }}>Let's set up your profile</div>
      </div>

      <div>
        <h2 style={h2Style}>About you</h2>
        <p style={subStyle}>Tell us a bit about yourself</p>

        <label style={labelStyle}>Your name</label>
        <input
          className="auth-input"
          value={displayName}
          readOnly
          style={{ ...inputStyle, background: '#FAF7F5', color: '#555', cursor: 'default' }}
        />

        <label style={labelStyle}>I am a...</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
          {[
            { key: 'parent', label: 'Mom with Kids', emoji: '👩‍👧‍👦' },
            { key: 'new_mom', label: 'New Mom', emoji: '👶' },
            { key: 'working_mom', label: 'Working Mom', emoji: '👩‍💻' },
            { key: 'homemaker', label: 'Homemaker', emoji: '🏡' },
            { key: 'professional', label: 'Professional', emoji: '💼' },
            { key: 'other', label: 'Other', emoji: '✨' },
          ].map((opt) => (
            <button key={opt.key} onClick={() => { setUserType(opt.key); if (opt.key !== 'other') setCustomUserType(''); }}
              style={{ padding: '14px 12px', borderRadius: 12, border: '0.5px solid', borderColor: userType === opt.key ? '#C2855A' : '#EDE8E3', background: userType === opt.key ? '#FFF8F0' : 'white', cursor: 'pointer', textAlign: 'center' }}>
              <div style={{ fontSize: 24 }}>{opt.emoji}</div>
              <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4 }}>{opt.label}</div>
            </button>
          ))}
        </div>
        {userType === 'other' && (
          <>
            <label style={labelStyle}>Tell us what you do</label>
            <input className="auth-input" value={customUserType} onChange={(e) => setCustomUserType(e.target.value)} placeholder="e.g. Freelancer, Retiree, Caregiver" style={inputStyle} />
          </>
        )}

        <label style={labelStyle}>City</label>
        <input className="auth-input" value={city} onChange={(e) => setCity(e.target.value)} placeholder="e.g. Kochi" style={inputStyle} />

        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}><label style={labelStyle}>Wake up</label><input className="auth-input" type="time" value={wakeTime} onChange={(e) => setWakeTime(e.target.value)} style={inputStyle} /></div>
          <div style={{ flex: 1 }}><label style={labelStyle}>Sleep</label><input className="auth-input" type="time" value={sleepTime} onChange={(e) => setSleepTime(e.target.value)} style={inputStyle} /></div>
        </div>
      </div>

      <div style={{ paddingBottom: 32, marginTop: 20 }}>
        <button onClick={handleNext} className="auth-btn" style={{ width: '100%', background: '#C2855A' }} disabled={!displayName.trim()}>
          Next
        </button>
      </div>
    </div>
  );
}

const h2Style = { fontFamily: 'Georgia, serif', fontSize: 22, marginBottom: 4 };
const subStyle = { color: '#888', fontSize: 13, marginBottom: 20 };
const labelStyle = { display: 'block', fontSize: 12, fontWeight: 600, color: '#888', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 };
const inputStyle = { marginBottom: 10 };
