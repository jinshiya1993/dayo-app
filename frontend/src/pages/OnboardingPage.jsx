import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { profile as profileApi } from '../services/api';

const CITIES = [
  // India — tier 1 & 2 + Kerala focus
  'Mumbai', 'Delhi', 'Bangalore', 'Hyderabad', 'Chennai', 'Kolkata', 'Pune',
  'Ahmedabad', 'Jaipur', 'Lucknow', 'Kanpur', 'Nagpur', 'Indore', 'Bhopal',
  'Patna', 'Vadodara', 'Ghaziabad', 'Ludhiana', 'Coimbatore', 'Agra',
  'Varanasi', 'Nashik', 'Faridabad', 'Meerut', 'Rajkot', 'Srinagar',
  'Aurangabad', 'Amritsar', 'Allahabad', 'Ranchi', 'Gwalior', 'Jabalpur',
  'Vijayawada', 'Jodhpur', 'Madurai', 'Raipur', 'Kota', 'Chandigarh',
  'Guwahati', 'Mysore', 'Tiruchirappalli', 'Gurgaon', 'Noida',
  'Thiruvananthapuram', 'Kochi', 'Kozhikode', 'Thrissur', 'Kollam',
  'Kannur', 'Alappuzha', 'Palakkad',
  // US
  'New York', 'Los Angeles', 'Chicago', 'Houston', 'San Francisco', 'Seattle',
  'Boston', 'Washington DC', 'Miami', 'Atlanta', 'Dallas', 'Austin',
  // UK
  'London', 'Manchester', 'Birmingham', 'Edinburgh',
  // Middle East
  'Dubai', 'Abu Dhabi', 'Doha', 'Riyadh', 'Jeddah', 'Muscat', 'Kuwait City',
  // South Asia (neighbours)
  'Karachi', 'Lahore', 'Islamabad', 'Dhaka', 'Chittagong', 'Kathmandu',
  'Colombo', 'Kandy', 'Malé',
  // Southeast Asia
  'Bangkok', 'Phuket', 'Chiang Mai', 'Pattaya',
  'Kuala Lumpur', 'Penang', 'Johor Bahru',
  'Jakarta', 'Bali', 'Surabaya', 'Yogyakarta',
  'Manila', 'Cebu',
  'Ho Chi Minh City', 'Hanoi',
  'Singapore',
  // East Asia
  'Tokyo', 'Osaka', 'Kyoto',
  'Hong Kong', 'Beijing', 'Shanghai', 'Shenzhen',
  'Seoul', 'Taipei',
  // Oceania + North America extras
  'Sydney', 'Melbourne', 'Brisbane', 'Perth', 'Auckland', 'Wellington',
  'Toronto', 'Vancouver', 'Montreal',
];

function CityTypeahead({ value, onChange }) {
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);

  useEffect(() => {
    function onClickOutside(e) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target)) setOpen(false);
    }
    document.addEventListener('mousedown', onClickOutside);
    return () => document.removeEventListener('mousedown', onClickOutside);
  }, []);

  const q = value.trim().toLowerCase();
  const matches = q
    ? CITIES.filter((c) => c.toLowerCase().includes(q)).slice(0, 8)
    : CITIES.slice(0, 8);
  const showList = open && matches.length > 0;

  return (
    <div ref={wrapperRef} style={{ position: 'relative', marginBottom: 14 }}>
      <input
        className="auth-input"
        value={value}
        onChange={(e) => { onChange(e.target.value); setOpen(true); }}
        onFocus={() => setOpen(true)}
        placeholder="Start typing your city..."
        autoComplete="off"
      />
      {showList && (
        <div
          style={{
            position: 'absolute',
            top: 'calc(100% + 4px)',
            left: 0,
            right: 0,
            background: 'white',
            border: '0.5px solid #EDE8E3',
            borderRadius: 12,
            boxShadow: '0 4px 16px rgba(0,0,0,0.06)',
            maxHeight: 240,
            overflowY: 'auto',
            zIndex: 10,
          }}
        >
          {matches.map((c) => (
            <button
              key={c}
              type="button"
              onClick={() => { onChange(c); setOpen(false); }}
              style={{
                display: 'block',
                width: '100%',
                textAlign: 'left',
                padding: '10px 14px',
                border: 'none',
                background: c.toLowerCase() === q ? '#FFF8F0' : 'white',
                fontSize: 15,
                color: '#1a1a1a',
                cursor: 'pointer',
              }}
              onMouseEnter={(e) => (e.currentTarget.style.background = '#FFF8F0')}
              onMouseLeave={(e) => (e.currentTarget.style.background = c.toLowerCase() === q ? '#FFF8F0' : 'white')}
            >
              {c}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export default function OnboardingPage() {
  const navigate = useNavigate();

  const [displayName, setDisplayName] = useState('');
  const [worksOutsideHome, setWorksOutsideHome] = useState(null);
  const [city, setCity] = useState('');
  const [wakeTime, setWakeTime] = useState('07:00');
  const [sleepTime, setSleepTime] = useState('22:00');

  useEffect(() => {
    profileApi.get().then((p) => {
      if (p?.error) return;
      const prefill = p.display_name || p.username || '';
      if (prefill) setDisplayName(prefill);
      if (p.location_city) setCity(p.location_city);
      if (p.wake_time) setWakeTime(p.wake_time.slice(0, 5));
      if (p.sleep_time) setSleepTime(p.sleep_time.slice(0, 5));
      if (typeof p.works_outside_home === 'boolean') {
        setWorksOutsideHome(p.works_outside_home);
      }
    });
  }, []);

  function handleNext() {
    if (!displayName.trim() || worksOutsideHome === null) return;
    navigate('/onboarding/form', {
      state: {
        name: displayName.trim(),
        worksOutsideHome,
        city,
        wakeTime,
        sleepTime,
      },
    });
  }

  const canProceed = displayName.trim() && worksOutsideHome !== null;

  return (
    <div className="app-shell" style={{ padding: '0 16px' }}>
      <div style={{ textAlign: 'center', padding: '24px 0 8px' }}>
        <div className="logo" style={{ fontSize: 28 }}>da<span>yo</span></div>
        <div style={{ color: '#888', fontSize: 13, marginTop: 4 }}>Let's set up your profile</div>
      </div>

      <div>
        <h2 style={h2Style}>About you</h2>
        <p style={subStyle}>A few basics and we're off</p>

        <label style={labelStyle}>Your name</label>
        <input
          className="auth-input"
          value={displayName}
          readOnly
          style={{ ...inputStyle, background: '#FAF7F5', color: '#555', cursor: 'default' }}
        />

        <label style={labelStyle}>Do you work outside the home?</label>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 12 }}>
          {[
            { value: true, label: 'Yes', emoji: '💼', hint: 'Office, shifts or commute' },
            { value: false, label: 'No', emoji: '🏡', hint: 'At home or remote all day' },
          ].map((opt) => {
            const on = worksOutsideHome === opt.value;
            return (
              <button
                key={String(opt.value)}
                onClick={() => setWorksOutsideHome(opt.value)}
                style={{
                  padding: '14px 12px',
                  borderRadius: 12,
                  border: '0.5px solid',
                  borderColor: on ? '#C2855A' : '#EDE8E3',
                  background: on ? '#FFF8F0' : 'white',
                  cursor: 'pointer',
                  textAlign: 'center',
                }}
              >
                <div style={{ fontSize: 26 }}>{opt.emoji}</div>
                <div style={{ fontSize: 14, fontWeight: 600, marginTop: 4 }}>{opt.label}</div>
                <div style={{ fontSize: 11, color: '#888', marginTop: 2 }}>{opt.hint}</div>
              </button>
            );
          })}
        </div>

        <label style={labelStyle}>City</label>
        <CityTypeahead value={city} onChange={setCity} />

        <div style={{ display: 'flex', gap: 8 }}>
          <div style={{ flex: 1 }}><label style={labelStyle}>Wake up</label><input className="auth-input" type="time" value={wakeTime} onChange={(e) => setWakeTime(e.target.value)} style={inputStyle} /></div>
          <div style={{ flex: 1 }}><label style={labelStyle}>Sleep</label><input className="auth-input" type="time" value={sleepTime} onChange={(e) => setSleepTime(e.target.value)} style={inputStyle} /></div>
        </div>
      </div>

      <div style={{ paddingBottom: 32, marginTop: 20 }}>
        <button onClick={handleNext} className="auth-btn" style={{ width: '100%', background: '#C2855A' }} disabled={!canProceed}>
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
