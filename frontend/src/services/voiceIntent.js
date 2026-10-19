// Decide whether a short spoken reply means "yes, do it" or "no, cancel" —
// used ONLY while a confirmation is on screen, so the words are interpreted
// in that narrow context and can't be mistaken for a fresh request.

const YES = [
  'yes', 'yeah', 'yep', 'yup', 'sure', 'ok', 'okay', 'confirm', 'confirmed',
  'do it', 'yes do it', 'go ahead', 'add it', 'please do', 'please', 'correct',
  "that's right", 'thats right', 'right', 'good',
];

const NO = [
  'no', 'nope', 'nah', 'cancel', 'cancelled', "don't", 'dont', 'do not',
  'stop', 'never mind', 'nevermind', 'leave it', 'forget it',
];

function norm(text) {
  return (text || '').toLowerCase().trim().replace(/[.!?,]/g, '');
}

// Returns 'yes', 'no', or null (treat as a new message).
export function affirmation(text) {
  const t = norm(text);
  if (!t) return null;
  if (NO.some((w) => t === w || t.startsWith(w + ' '))) return 'no';
  if (YES.some((w) => t === w || t.startsWith(w + ' '))) return 'yes';
  return null;
}
