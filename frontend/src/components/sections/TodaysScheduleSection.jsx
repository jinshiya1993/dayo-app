import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { events } from '../../services/api';

function getTodayEvents(allEvents) {
  const jsDay = new Date().getDay();
  const pyDay = jsDay === 0 ? 6 : jsDay - 1;
  return allEvents.filter((ev) => {
    switch (ev.recurrence) {
      case 'daily': return true;
      case 'weekdays': return pyDay < 5;
      case 'weekly': return ev.recurrence_days?.includes(pyDay);
      case 'custom': return ev.recurrence_days?.includes(pyDay);
      case 'none': default: return true;
    }
  }).sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
}

function formatTime(timeStr) {
  if (!timeStr) return '';
  const [h, m] = timeStr.split(':').map(Number);
  const ampm = h >= 12 ? 'PM' : 'AM';
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, '0')} ${ampm}`;
}

function getMinutesFromNow(timeStr) {
  if (!timeStr) return Infinity;
  const [h, m] = timeStr.split(':').map(Number);
  const now = new Date();
  return (h * 60 + m) - (now.getHours() * 60 + now.getMinutes());
}

function calcLeaveBy(startTime, travelMinutes) {
  if (!startTime || !travelMinutes) return null;
  const [h, m] = startTime.split(':').map(Number);
  let totalMin = h * 60 + m - travelMinutes;
  if (totalMin < 0) totalMin += 24 * 60;
  const lh = Math.floor(totalMin / 60);
  const lm = totalMin % 60;
  return `${lh}:${String(lm).padStart(2, '0')}`;
}

// Keyword → emoji mapping for smart icon detection
const keywordEmojis = [
  { keywords: ['swim', 'pool'], emoji: '🏊' },
  { keywords: ['doctor', 'dr.', 'clinic', 'hospital', 'checkup', 'check-up', 'medical', 'dentist', 'dental'], emoji: '🏥' },
  { keywords: ['karate', 'taekwondo', 'martial', 'judo', 'kung fu'], emoji: '🥋' },
  { keywords: ['dance', 'ballet', 'dancing'], emoji: '💃' },
  { keywords: ['music', 'piano', 'guitar', 'violin', 'singing', 'vocal'], emoji: '🎵' },
  { keywords: ['art', 'drawing', 'paint', 'sketch', 'craft'], emoji: '🎨' },
  { keywords: ['football', 'soccer'], emoji: '⚽' },
  { keywords: ['cricket', 'bat'], emoji: '🏏' },
  { keywords: ['basketball', 'basket'], emoji: '🏀' },
  { keywords: ['tennis', 'badminton', 'racket'], emoji: '🎾' },
  { keywords: ['gym', 'workout', 'fitness', 'exercise'], emoji: '🏋️' },
  { keywords: ['yoga', 'meditation'], emoji: '🧘' },
  { keywords: ['school', 'drop', 'pick', 'bus'], emoji: '🏫' },
  { keywords: ['tuition', 'tutor', 'coaching', 'class', 'lesson', 'lecture'], emoji: '📚' },
  { keywords: ['meet', 'meeting', 'call', 'zoom', 'teams'], emoji: '💼' },
  { keywords: ['grocery', 'shop', 'market', 'store'], emoji: '🛒' },
  { keywords: ['cook', 'bake', 'kitchen'], emoji: '🍳' },
  { keywords: ['birthday', 'party', 'celebration'], emoji: '🎂' },
  { keywords: ['travel', 'trip', 'flight', 'airport'], emoji: '✈️' },
  { keywords: ['exam', 'test', 'quiz'], emoji: '📝' },
  { keywords: ['play', 'playground', 'park'], emoji: '🛝' },
  { keywords: ['vaccine', 'vaccination', 'injection', 'shot'], emoji: '💉' },
  { keywords: ['therapy', 'therapist', 'counsell'], emoji: '🧠' },
  { keywords: ['walk', 'jog', 'run', 'morning walk'], emoji: '🚶' },
  { keywords: ['salon', 'haircut', 'spa', 'facial'], emoji: '💇' },
  { keywords: ['temple', 'church', 'mosque', 'prayer', 'pooja'], emoji: '🙏' },
];

// Fallback emojis by event type
const typeEmojis = {
  personal: '📌',
  appointment: '📋',
  school_drop: '🏫',
  school_pick: '🏫',
  child_activity: '⭐',
  class: '📚',
  study: '📖',
  exam: '📝',
  assignment_due: '📄',
  work_shift: '💼',
  meeting: '💼',
};

function getEventEmoji(ev) {
  const title = (ev.title || '').toLowerCase();
  for (const entry of keywordEmojis) {
    if (entry.keywords.some((kw) => title.includes(kw))) {
      return entry.emoji;
    }
  }
  return typeEmojis[ev.event_type] || '📅';
}

export default function TodaysScheduleSection({ onUrgentEvent }) {
  const [todayEvents, setTodayEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [now, setNow] = useState(new Date());
  const navigate = useNavigate();

  useEffect(() => { loadEvents(); }, []);
  useEffect(() => {
    const timer = setInterval(() => setNow(new Date()), 60000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!onUrgentEvent || todayEvents.length === 0) return;
    const urgent = todayEvents.find((ev) => {
      const leaveMin = ev.travel_time_minutes || 0;
      const minsUntil = getMinutesFromNow(ev.start_time);
      const leaveIn = minsUntil - leaveMin;
      return leaveIn > 0 && leaveIn <= (leaveMin || 30);
    });
    onUrgentEvent(urgent || null);
  }, [todayEvents, now, onUrgentEvent]);

  async function loadEvents() {
    const res = await events.list('active=true');
    if (!res.error) setTodayEvents(getTodayEvents(Array.isArray(res) ? res : []));
    setLoading(false);
  }

  if (loading) return null;
  // Show only events within 2 hours from now, hide once event time passes
  const upcoming = todayEvents.filter((ev) => {
    const mins = getMinutesFromNow(ev.start_time);
    return mins > 0 && mins <= 120;
  }).slice(0, 3);
  if (upcoming.length === 0) return null;

  return (
    <div style={{ padding: '0 16px', marginBottom: 12 }}>
      {upcoming.map((ev) => {
        const minsUntil = getMinutesFromNow(ev.start_time);
        const leaveBy = calcLeaveBy(ev.start_time, ev.travel_time_minutes);
        const leaveIn = ev.travel_time_minutes ? minsUntil - ev.travel_time_minutes : null;
        const isUrgent = leaveIn !== null && leaveIn > 0 && leaveIn <= (ev.travel_time_minutes || 30);
        const emoji = getEventEmoji(ev);

        return (
          <div key={ev.id} onClick={() => navigate('/schedule')} style={{
            background: isUrgent ? '#FEF2F2' : '#F9F1EB',
            border: isUrgent ? '1px solid #FECACA' : '1px solid transparent',
            borderRadius: 14, padding: '12px 14px',
            display: 'flex', alignItems: 'center', gap: 10,
            marginBottom: 6, cursor: 'pointer',
          }}>
            <div style={{
              width: 34, height: 34, borderRadius: 10,
              background: isUrgent ? '#FECACA' : '#EEDDD0',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 16, flexShrink: 0,
            }}>
              {isUrgent ? '🔴' : emoji}
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{
                fontSize: 13, fontWeight: 600,
                color: isUrgent ? '#DC2626' : '#6B4226',
                overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
              }}>
                {ev.title}
                {ev.child_name && <span style={{ fontWeight: 400, color: isUrgent ? '#E87171' : '#A07A5E' }}> · {ev.child_name}</span>}
              </div>
              <div style={{ fontSize: 11, color: isUrgent ? '#E87171' : '#A07A5E', marginTop: 1 }}>
                {formatTime(ev.start_time)}
                {leaveBy && !isUrgent && <span> · Leave {formatTime(leaveBy + ':00')}</span>}
              </div>
            </div>
            {isUrgent && (
              <div style={{
                fontSize: 11, fontWeight: 700, color: '#fff',
                background: '#DC2626', borderRadius: 8, padding: '3px 8px',
                whiteSpace: 'nowrap', flexShrink: 0,
              }}>
                {Math.max(1, Math.round(leaveIn))}m
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
