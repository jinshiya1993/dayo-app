import { useCallback, useRef, useState } from 'react';

// The one recording engine behind every mic in Dayo — the chat bar and the
// floating home button both use this, so they behave identically.
//
// It does three things a bare MediaRecorder doesn't:
//   - reports a live volume level (0..1) so the UI can show a waveform that
//     reacts to the voice
//   - auto-stops a couple of seconds after the person stops talking, so they
//     never have to tap "stop" — it feels like talking, not recording
//   - can be cancelled (discard, don't send) as well as stopped (send)
//
// States: 'idle' | 'listening' | 'processing'. onResult({blob}) runs when a
// recording finishes; onResult({error}) for 'denied' or 'unsupported'.
export function useVoiceRecorder({ onResult, silenceMs = 2000, maxMs = 30000 }) {
  const [state, setState] = useState('idle');
  const [level, setLevel] = useState(0);

  const recRef = useRef(null);
  const streamRef = useRef(null);
  const ctxRef = useRef(null);
  const rafRef = useRef(null);
  const chunksRef = useRef([]);
  const cancelledRef = useRef(false);

  function teardown() {
    cancelAnimationFrame(rafRef.current);
    if (streamRef.current) streamRef.current.getTracks().forEach((t) => t.stop());
    if (ctxRef.current && ctxRef.current.state !== 'closed') ctxRef.current.close().catch(() => {});
    streamRef.current = null;
    ctxRef.current = null;
    setLevel(0);
  }

  const stop = useCallback(() => {
    const r = recRef.current;
    if (r && r.state !== 'inactive') r.stop();
  }, []);

  const cancel = useCallback(() => {
    cancelledRef.current = true;
    stop();
  }, [stop]);

  const start = useCallback(async () => {
    if (!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder) {
      onResult({ error: 'unsupported' });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      streamRef.current = stream;
      cancelledRef.current = false;
      chunksRef.current = [];

      // Web Audio taps the live signal for volume + silence detection. This
      // is separate from MediaRecorder, which captures the actual audio.
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      const ctx = new AudioCtx();
      ctxRef.current = ctx;
      const analyser = ctx.createAnalyser();
      analyser.fftSize = 512;
      ctx.createMediaStreamSource(stream).connect(analyser);
      const buf = new Uint8Array(analyser.frequencyBinCount);

      const started = Date.now();
      let lastLoud = Date.now();
      let hasSpoken = false;

      const tick = () => {
        analyser.getByteTimeDomainData(buf);
        let sum = 0;
        for (let i = 0; i < buf.length; i++) {
          const v = (buf[i] - 128) / 128;
          sum += v * v;
        }
        const rms = Math.sqrt(sum / buf.length);
        setLevel(Math.min(1, rms * 3.2));

        const now = Date.now();
        if (rms > 0.05) { hasSpoken = true; lastLoud = now; }
        // Only auto-stop once they've actually spoken, so a slow start never
        // cuts them off; a hard cap guards a recording left running.
        if ((hasSpoken && now - lastLoud > silenceMs) || now - started > maxMs) {
          stop();
          return;
        }
        rafRef.current = requestAnimationFrame(tick);
      };

      const rec = new MediaRecorder(stream);
      rec.ondataavailable = (e) => { if (e.data.size) chunksRef.current.push(e.data); };
      rec.onstop = async () => {
        teardown();
        if (cancelledRef.current) { setState('idle'); return; }
        const blob = new Blob(chunksRef.current, { type: rec.mimeType || 'audio/webm' });
        setState('processing');
        try { await onResult({ blob }); } finally { setState('idle'); }
      };
      recRef.current = rec;
      rec.start();
      setState('listening');
      rafRef.current = requestAnimationFrame(tick);
    } catch {
      teardown();
      onResult({ error: 'denied' });
    }
  }, [onResult, silenceMs, maxMs, stop]);

  const toggle = useCallback(() => {
    if (state === 'listening') stop(); else if (state === 'idle') start();
  }, [state, start, stop]);

  return { state, level, start, stop, cancel, toggle };
}
