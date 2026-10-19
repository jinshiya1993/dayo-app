// Dayo speaking replies aloud, using the browser's built-in voice — free,
// no backend. A mute preference is remembered so a voice that talks
// unprompted is never forced on anyone.

let muted = false;
try { muted = localStorage.getItem('dayoVoiceMuted') === '1'; } catch { /* private mode */ }

export function isMuted() { return muted; }

export function setMuted(next) {
  muted = next;
  try { localStorage.setItem('dayoVoiceMuted', next ? '1' : '0'); } catch { /* ignore */ }
  if (next) stopSpeaking();
}

export function speak(text) {
  if (muted || !text) return;
  const synth = window.speechSynthesis;
  if (!synth) return;
  synth.cancel();                       // never stack utterances
  const u = new SpeechSynthesisUtterance(String(text));
  u.lang = 'en-US';
  u.rate = 1.0;
  u.pitch = 1.0;
  synth.speak(u);
}

export function stopSpeaking() {
  try { window.speechSynthesis?.cancel(); } catch { /* ignore */ }
}
