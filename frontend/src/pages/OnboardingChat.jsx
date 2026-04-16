import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { profile as profileApi } from '../services/api';

const API_BASE = process.env.NODE_ENV === 'production' ? '/api/v1' : 'http://localhost:8000/api/v1';

function getCookie(name) {
  const value = `; ${document.cookie}`;
  const parts = value.split(`; ${name}=`);
  if (parts.length === 2) return parts.pop().split(';').shift();
  return null;
}

async function apiPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCookie('csrftoken'),
    },
    body: JSON.stringify(body),
  });
  return res.json();
}

export default function OnboardingChat() {
  const location = useLocation();
  const navigate = useNavigate();
  const { name, userType, city, wakeTime, sleepTime } = location.state || {};

  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [typing, setTyping] = useState(true);
  const [userMsgCount, setUserMsgCount] = useState(0);
  const [sessionId] = useState(() => String(Date.now()));
  const [fadeOut, setFadeOut] = useState(false);
  const messagesEnd = useRef(null);
  const inputRef = useRef(null);

  // Redirect if no state passed
  useEffect(() => {
    if (!name) {
      navigate('/onboarding', { replace: true });
      return;
    }
    startConversation();
  }, []);

  useEffect(() => {
    messagesEnd.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, typing]);

  async function startConversation() {
    setTyping(true);
    const result = await apiPost('/onboarding/start/', {
      session_id: sessionId,
      name,
      user_type: userType,
    });
    setTyping(false);
    if (result.message) {
      setMessages([{ role: 'ai', text: result.message, chips: result.chips || [] }]);
    }
    inputRef.current?.focus();
  }

  async function sendMessage(directText) {
    const text = (directText || input).trim();
    if (!text || sending) return;

    const newCount = userMsgCount + 1;
    setUserMsgCount(newCount);
    // Clear chips from all previous messages when user sends
    setMessages((prev) => [
      ...prev.map((m) => ({ ...m, chips: undefined })),
      { role: 'user', text },
    ]);
    setInput('');
    setSending(true);
    setTyping(true);

    const result = await apiPost('/onboarding/chat/', {
      session_id: sessionId,
      message: text,
    });

    setTyping(false);
    setSending(false);

    if (result.message) {
      setMessages((prev) => [...prev, { role: 'ai', text: result.message }]);
    }

    if (result.is_complete) {
      // Fire the city/wake/sleep update in the background while the user
      // reads the final message — done by the time we navigate.
      const update = {};
      if (city) update.location_city = city;
      if (wakeTime) update.wake_time = wakeTime;
      if (sleepTime) update.sleep_time = sleepTime;
      if (Object.keys(update).length > 0) profileApi.update(update);

      // Show final message → wait → fade out → navigate
      setTimeout(() => {
        setFadeOut(true);
        setTimeout(() => {
          navigate('/onboarding/preview', {
            replace: true,
            state: {
              name,
              profileData: {
                ...result.profile_data,
                confidence: result.confidence,
                section_reasons: result.section_reasons,
              },
            },
          });
        }, 600); // wait for fade animation
      }, 2000); // show final message for 2 seconds
    }

    inputRef.current?.focus();
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  }

  // Progress dots — 4 dots, fill based on user message count
  function getActiveDots() {
    if (userMsgCount >= 5) return 4;
    if (userMsgCount >= 4) return 3;
    if (userMsgCount >= 2) return 2;
    return 1;
  }

  const activeDots = getActiveDots();

  return (
    <div style={{
      display: 'flex', flexDirection: 'column', height: '100dvh', maxWidth: 430, margin: '0 auto', background: '#FAF7F5',
      opacity: fadeOut ? 0 : 1, transition: 'opacity 0.6s ease-out',
    }}>

      {/* Top bar */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '14px 16px', borderBottom: '0.5px solid #EDE8E3' }}>
        <div style={{ fontFamily: 'Georgia, serif', fontSize: 22, fontWeight: 700 }}>
          da<span style={{ color: '#C2855A' }}>yo</span>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          {[1, 2, 3, 4].map((dot) => (
            <div key={dot} style={{
              width: 8, height: 8, borderRadius: '50%',
              background: dot <= activeDots ? '#C2855A' : '#EDE8E3',
              transition: 'background 0.3s',
            }} />
          ))}
        </div>
      </div>

      {/* Messages area */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '16px', display: 'flex', flexDirection: 'column', gap: 12 }}>
        {messages.map((msg, i) => (
          msg.role === 'user' ? (
            <div key={i} style={{
              alignSelf: 'flex-end', maxWidth: '80%',
              background: '#1a1a1a', color: 'white',
              padding: '12px 16px', fontSize: 14, lineHeight: 1.5,
              borderRadius: '20px 20px 4px 20px',
            }}>
              {msg.text}
            </div>
          ) : (
            <div key={i} style={{ alignSelf: 'flex-start', maxWidth: '85%' }}>
              <div style={{ display: 'flex', gap: 8 }}>
                <div style={{
                  width: 32, height: 32, borderRadius: '50%',
                  background: '#C2855A', color: 'white',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontFamily: 'Georgia, serif', fontWeight: 700, fontSize: 14,
                  flexShrink: 0,
                }}>
                  D
                </div>
                <div style={{
                  background: 'white', border: '0.5px solid #EDE8E3',
                  padding: '12px 16px', fontSize: 14, lineHeight: 1.5,
                  borderRadius: '4px 20px 20px 20px',
                }}>
                  {msg.text}
                </div>
              </div>
              {/* Tappable chips below AI message */}
              {msg.chips && msg.chips.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8, marginLeft: 40 }}>
                  {msg.chips.map((chip) => (
                    <button key={chip} onClick={() => { setInput(''); sendMessage(chip); }}
                      style={{
                        padding: '8px 14px', borderRadius: 20,
                        border: '0.5px solid #EDE8E3', background: 'white',
                        fontSize: 12, cursor: 'pointer', color: '#1a1a1a',
                        fontWeight: 500,
                      }}>
                      {chip}
                    </button>
                  ))}
                </div>
              )}
            </div>
          )
        ))}

        {/* Typing indicator */}
        {typing && (
          <div style={{ display: 'flex', gap: 8, alignSelf: 'flex-start' }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: '#C2855A', color: 'white',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontFamily: 'Georgia, serif', fontWeight: 700, fontSize: 14,
              flexShrink: 0,
            }}>
              D
            </div>
            <div style={{
              background: 'white', border: '0.5px solid #EDE8E3',
              padding: '12px 18px',
              borderRadius: '4px 20px 20px 20px',
              display: 'flex', gap: 4, alignItems: 'center',
            }}>
              <span style={dotAnim(0)} />
              <span style={dotAnim(1)} />
              <span style={dotAnim(2)} />
            </div>
          </div>
        )}

        <div ref={messagesEnd} />
      </div>

      {/* Input bar */}
      <div style={{ padding: '12px 16px calc(12px + env(safe-area-inset-bottom)) 16px', borderTop: '0.5px solid #EDE8E3', background: 'white', display: 'flex', gap: 8, alignItems: 'center' }}>
        <input
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type your answer..."
          disabled={sending || typing}
          style={{
            flex: 1, padding: '12px 18px',
            borderRadius: 24, border: 'none',
            background: '#FAF7F5', fontSize: 14,
            fontFamily: 'system-ui, sans-serif',
            outline: 'none',
          }}
        />
        <button
          onClick={() => sendMessage()}
          disabled={!input.trim() || sending || typing}
          style={{
            width: 40, height: 40, borderRadius: '50%',
            background: input.trim() && !sending ? '#C2855A' : '#EDE8E3',
            color: 'white', border: 'none',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            cursor: input.trim() && !sending ? 'pointer' : 'default',
            fontSize: 18, flexShrink: 0,
            transition: 'background 0.2s',
          }}
        >
          ↑
        </button>
      </div>

      {/* Keyframe styles for typing dots */}
      <style>{`
        @keyframes typingBounce {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
      `}</style>
    </div>
  );
}

function dotAnim(delay) {
  return {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: '#999',
    animation: `typingBounce 1.4s ease-in-out ${delay * 0.2}s infinite`,
  };
}
