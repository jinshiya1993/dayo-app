import { useRef, useState } from 'react';
import { chat } from '../services/api';
import { useVoiceRecorder } from '../hooks/useVoiceRecorder';
import { speak, isMuted, setMuted } from '../services/speech';
import { affirmation } from '../services/voiceIntent';

// Ask Dayo anything by voice from the home page. Uses the shared recorder, so
// it behaves exactly like the chat mic: tap to start, it auto-stops when you
// stop talking, shows a live waveform while listening, speaks the answer back
// (unless muted), and lets you confirm a change by tapping OR by saying "yes".
export default function FloatingMic() {
  const [result, setResult] = useState(null);   // { transcript, reply, pending, done }
  const [error, setError] = useState('');
  const [muted, setMutedState] = useState(isMuted());
  const convoRef = useRef(null);
  const pendingRef = useRef(null);               // confirm context for voice yes/no

  const { state, level, toggle } = useVoiceRecorder({ onResult: handleResult });
  const listening = state === 'listening';
  const processing = state === 'processing';

  async function ensureConvo() {
    if (convoRef.current) return convoRef.current;
    const c = await chat.create();
    if (c.error) return null;
    convoRef.current = c;
    return c;
  }

  async function handleResult({ blob, error: recErr }) {
    if (recErr) {
      setError(recErr === 'denied'
        ? 'I need microphone access to listen. Open Chat to type instead.'
        : 'Voice needs a newer browser — open Chat to type instead.');
      return;
    }
    // If a confirmation is waiting, a spoken "yes"/"no" acts on it.
    if (pendingRef.current) {
      const convo = await ensureConvo();
      const probe = await chat.sendVoice(convo.id, blob);
      const verdict = affirmation(probe.transcript || '');
      if (verdict === 'yes') { await confirmPending(); return; }
      if (verdict === 'no') { pendingRef.current = null; setResult(null); return; }
      // Not a yes/no — fall through and treat it as a brand-new question.
      applyReply(probe);
      return;
    }
    const convo = await ensureConvo();
    if (!convo) { setError('Please sign in again.'); return; }
    const res = await chat.sendVoice(convo.id, blob);
    applyReply(res);
  }

  function applyReply(res) {
    if (res.error) { setError(res.error === 'unauthorized' ? 'Please sign in again.' : res.error); return; }
    if (!res.transcript) { setError(res.message || "I didn't catch anything — tap and try again."); return; }
    const reply = res.reply || {};
    const pending = reply.action_status === 'pending' ? { id: reply.id } : null;
    pendingRef.current = pending;
    setError('');
    setResult({ transcript: res.transcript, reply: reply.content || '', pending, done: '' });
    // Speak the answer, or the proposed action so she can say yes hands-free.
    speak(reply.content);
  }

  async function confirmPending() {
    const p = pendingRef.current;
    if (!p) return;
    const res = await chat.confirm(p.id);
    pendingRef.current = null;
    if (res.error) { setError("Couldn't do that — try again."); return; }
    const msg = res.content || 'Done.';
    setResult((r) => ({ ...(r || {}), pending: null, done: msg }));
    speak(msg);
  }

  function dismiss() { pendingRef.current = null; setResult(null); setError(''); }

  function toggleMute() {
    const next = !muted;
    setMuted(next);
    setMutedState(next);
  }

  // No card while transcribing — the mic button's own spinner is feedback
  // enough, and a card popping over the page the moment you stop talking is
  // intrusive. The card is only for the answer, an error, or while listening.
  const showCard = result || error || listening;

  return (
    <>
      {showCard && (
        <div style={cardStyle}>
          {!listening && <button onClick={dismiss} style={closeStyle} aria-label="Close">×</button>}
          {listening && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ width: 9, height: 9, borderRadius: '50%', background: '#C2855A', flexShrink: 0,
                             transform: `scale(${1 + level * 1.2})`, transition: 'transform 0.08s' }} />
              <div>
                <div style={{ fontSize: 14, color: '#1a1a1a' }}>I'm listening…</div>
                <div style={{ fontSize: 12, color: '#8a8178', marginTop: 2 }}>Speak now — I'll stop on my own when you're done.</div>
              </div>
            </div>
          )}
          {error && !listening && <div style={{ fontSize: 13, color: '#9A5B4B', lineHeight: 1.5 }}>{error}</div>}
          {result && !processing && (
            <>
              <div style={labelStyle}>YOU ASKED</div>
              <div style={{ fontSize: 13.5, color: '#1a1a1a', marginBottom: 12, lineHeight: 1.5 }}>{result.transcript}</div>
              <div style={{ ...labelStyle, color: '#a0764f' }}>DAYO</div>
              <div style={{ fontSize: 13.5, color: '#1a1a1a', lineHeight: 1.6, whiteSpace: 'pre-wrap' }}>{result.reply}</div>
              {result.pending && !result.done && (
                <>
                  <div style={{ fontSize: 11.5, color: '#8a8178', marginTop: 10 }}>
                    Tap, or just say “yes”.
                  </div>
                  <div style={{ display: 'flex', gap: 8, marginTop: 8 }}>
                    <button onClick={confirmPending} style={yesStyle}>Yes, do it</button>
                    <button onClick={dismiss} style={noStyle}>No</button>
                  </div>
                </>
              )}
              {result.done && (
                <div style={{ fontSize: 13, color: '#1D7A4A', marginTop: 12 }}>✓ {result.done}</div>
              )}
            </>
          )}
        </div>
      )}

      <div style={{ position: 'fixed', right: 18, bottom: 118, zIndex: 50, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 8 }}>
        <button onClick={toggleMute} aria-label={muted ? 'Unmute Dayo' : 'Mute Dayo'} title={muted ? 'Dayo is muted' : 'Dayo speaks replies'} style={muteStyle}>
          {muted
            ? <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8a8178" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><line x1="23" y1="9" x2="17" y2="15"/><line x1="17" y1="9" x2="23" y2="15"/></svg>
            : <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#8a8178" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M11 5 6 9H2v6h4l5 4V5z"/><path d="M15.54 8.46a5 5 0 0 1 0 7.07"/><path d="M19.07 4.93a10 10 0 0 1 0 14.14"/></svg>}
        </button>

        <button
          type="button"
          onClick={() => (listening ? toggle() : (dismiss(), toggle()))}
          disabled={processing}
          aria-label={listening ? 'Stop recording' : 'Ask Dayo by voice'}
          title={listening ? 'Listening — stop' : 'Ask Dayo by voice'}
          style={{ ...micStyle, background: listening ? '#C2855A' : '#1A1A1A' }}
        >
          {processing ? (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2.5" strokeLinecap="round"><path d="M12 2a10 10 0 0 1 10 10" opacity="0.9"><animateTransform attributeName="transform" type="rotate" from="0 12 12" to="360 12 12" dur="0.8s" repeatCount="indefinite"/></path></svg>
          ) : listening ? (
            <svg width="22" height="22" viewBox="0 0 24 24" fill="#fff"><rect x="6" y="6" width="12" height="12" rx="2"/></svg>
          ) : (
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/></svg>
          )}
          {listening && (
            <span style={{ ...ringStyle, transform: `scale(${1 + level * 0.9})`, opacity: 0.25 + level * 0.5 }} />
          )}
        </button>
      </div>
    </>
  );
}

const micStyle = {
  width: 56, height: 56, borderRadius: '50%', border: 'none', cursor: 'pointer',
  display: 'flex', alignItems: 'center', justifyContent: 'center', position: 'relative',
  boxShadow: '0 4px 14px rgba(0,0,0,0.22)',
};
const muteStyle = {
  width: 34, height: 34, borderRadius: '50%', border: '0.5px solid #EDE8E3',
  background: '#fff', cursor: 'pointer', display: 'flex', alignItems: 'center',
  justifyContent: 'center', boxShadow: '0 2px 6px rgba(0,0,0,0.1)',
};
const ringStyle = {
  position: 'absolute', inset: -6, borderRadius: '50%',
  border: '2px solid #C2855A', pointerEvents: 'none', transition: 'transform 0.08s ease-out, opacity 0.08s',
};
const cardStyle = {
  position: 'fixed', left: 16, right: 16, bottom: 186, zIndex: 50,
  maxWidth: 400, margin: '0 auto', background: '#fff',
  border: '0.5px solid #EDE8E3', borderRadius: 16, padding: '16px 18px',
  boxShadow: '0 8px 28px rgba(0,0,0,0.16)',
};
const closeStyle = {
  position: 'absolute', top: 8, right: 12, background: 'none', border: 'none',
  fontSize: 20, color: '#b0a89e', cursor: 'pointer', lineHeight: 1,
};
const labelStyle = { fontSize: 11, color: '#8a8178', letterSpacing: 0.4, marginBottom: 4 };
const yesStyle = { flex: 1.4, background: '#C2855A', color: '#fff', border: 'none', borderRadius: 11, padding: '10px', fontSize: 13, cursor: 'pointer' };
const noStyle = { flex: 1, background: '#fff', color: '#6b6259', border: '0.5px solid #EDE8E3', borderRadius: 11, padding: '10px', fontSize: 13, cursor: 'pointer' };
