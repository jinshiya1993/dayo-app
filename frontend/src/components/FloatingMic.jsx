import { useState, useRef } from 'react';
import { chat } from '../services/api';

// A floating mic that lets the user ask Dayo anything by voice from wherever
// it's placed — "what can I make today?", "add milk to my list". It records,
// sends to the same voice endpoint the chat page uses, and shows Dayo's reply
// in a small card right here, so she gets a quick answer without leaving the
// page. Falls back to a clear message if the mic is blocked or unsupported.
export default function FloatingMic() {
  const [recording, setRecording] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);   // { transcript, reply }
  const [error, setError] = useState('');
  const recorderRef = useRef(null);
  const convoRef = useRef(null);

  async function ensureConvo() {
    if (convoRef.current) return convoRef.current;
    const c = await chat.create();
    if (c.error) return null;
    convoRef.current = c;
    return c;
  }

  async function toggle() {
    if (recording) {
      const r = recorderRef.current;
      if (r && r.state !== 'inactive') r.stop();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError('Voice needs a newer browser — open Chat to type instead.');
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const rec = new MediaRecorder(stream);
      const chunks = [];
      rec.ondataavailable = (e) => { if (e.data.size) chunks.push(e.data); };
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setRecording(false);
        await send(new Blob(chunks, { type: rec.mimeType || 'audio/webm' }));
      };
      recorderRef.current = rec;
      setError('');
      setResult(null);
      rec.start();
      setRecording(true);
    } catch {
      setError('I need microphone access to listen. Open Chat to type instead.');
    }
  }

  async function send(blob) {
    setBusy(true);
    const convo = await ensureConvo();
    if (!convo) { setError('Please sign in again.'); setBusy(false); return; }
    const res = await chat.sendVoice(convo.id, blob);
    setBusy(false);
    if (res.error) { setError(res.error === 'unauthorized' ? 'Please sign in again.' : res.error); return; }
    if (!res.transcript) { setError(res.message || "I didn't catch anything — tap and try again."); return; }
    setResult({ transcript: res.transcript, reply: res.reply?.content || '' });
  }

  const label = recording ? 'Stop recording' : 'Ask Dayo by voice';

  return (
    <>
      {(result || error || busy) && (
        <div style={cardStyle}>
          <button onClick={() => { setResult(null); setError(''); }} style={closeStyle} aria-label="Close">×</button>
          {busy && <div style={{ fontSize: 13, color: '#8a8178' }}>Listening to what you said…</div>}
          {error && <div style={{ fontSize: 13, color: '#9A5B4B', lineHeight: 1.5 }}>{error}</div>}
          {result && (
            <>
              <div style={{ fontSize: 11, color: '#8a8178', letterSpacing: 0.4, marginBottom: 4 }}>YOU ASKED</div>
              <div style={{ fontSize: 13.5, color: '#1a1a1a', marginBottom: 12, lineHeight: 1.5 }}>{result.transcript}</div>
              <div style={{ fontSize: 11, color: '#a0764f', letterSpacing: 0.4, marginBottom: 4 }}>DAYO</div>
              <div style={{ fontSize: 13.5, color: '#1a1a1a', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.reply}</div>
            </>
          )}
        </div>
      )}

      <button
        type="button"
        onClick={toggle}
        disabled={busy && !recording}
        aria-label={label}
        title={label}
        style={{ ...micStyle, background: recording ? '#C2855A' : '#1A1A1A' }}
      >
        {recording ? (
          <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff"><rect x="6" y="6" width="12" height="12" rx="2" /></svg>
        ) : (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" /><path d="M19 10v2a7 7 0 0 1-14 0v-2" /><line x1="12" y1="19" x2="12" y2="23" /></svg>
        )}
        {recording && <span style={pulseStyle} />}
      </button>
    </>
  );
}

const micStyle = {
  // Sit well above the bottom nav bar so it reads as its own "ask Dayo"
  // button rather than crowding the Chat/Profile tabs.
  position: 'fixed', right: 18, bottom: 118, zIndex: 50,
  width: 56, height: 56, borderRadius: '50%', border: 'none', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center',
  boxShadow: '0 4px 14px rgba(0,0,0,0.22)',
};

const pulseStyle = {
  position: 'absolute', inset: 0, borderRadius: '50%',
  border: '2px solid #C2855A', animation: 'dayoMicPulse 1.4s ease-out infinite',
};

const cardStyle = {
  position: 'fixed', left: 16, right: 16, bottom: 186, zIndex: 50,
  maxWidth: 400, margin: '0 auto',
  background: '#fff', border: '0.5px solid #EDE8E3', borderRadius: 16,
  padding: '16px 18px', boxShadow: '0 8px 28px rgba(0,0,0,0.16)',
};

const closeStyle = {
  position: 'absolute', top: 8, right: 12, background: 'none', border: 'none',
  fontSize: 20, color: '#b0a89e', cursor: 'pointer', lineHeight: 1,
};
