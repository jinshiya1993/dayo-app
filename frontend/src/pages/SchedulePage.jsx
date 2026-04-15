import { useState, useEffect } from 'react';
import { events, children as childrenApi, profile as profileApi } from '../services/api';

const FILTER_TABS = [
  { key: 'all', label: 'All' },
  { key: 'school', label: 'School', types: ['school_drop', 'school_pick'] },
  { key: 'classes', label: 'Classes', types: ['child_activity', 'class', 'study', 'exam'] },
  { key: 'appointments', label: 'Appointments', types: ['appointment'] },
  { key: 'personal', label: 'Personal', types: ['personal', 'work_shift', 'meeting'] },
];

const typeBadge = {
  school_drop: { label: 'School', color: '#DC3545', bg: '#FEE2E2' },
  school_pick: { label: 'School', color: '#DC3545', bg: '#FEE2E2' },
  child_activity: { label: 'Class', color: '#C2855A', bg: '#FDF2EB' },
  class: { label: 'Class', color: '#C2855A', bg: '#FDF2EB' },
  appointment: { label: 'Appt', color: '#6B46C1', bg: '#F3EEFF' },
  personal: { label: 'Personal', color: '#6B46C1', bg: '#F3EEFF' },
  meeting: { label: 'Meeting', color: '#1a1a1a', bg: '#F3F0ED' },
  work_shift: { label: 'Work', color: '#1a1a1a', bg: '#F3F0ED' },
  study: { label: 'Study', color: '#3B82F6', bg: '#EFF6FF' },
  exam: { label: 'Exam', color: '#DC3545', bg: '#FEE2E2' },
  assignment_due: { label: 'Due', color: '#F59E0B', bg: '#FEF9E7' },
};

const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const ALERT_OPTIONS = [
  { value: 0, label: 'None' },
  { value: 5, label: '5 mins' },
  { value: 10, label: '10 mins' },
  { value: 15, label: '15 mins' },
  { value: 30, label: '30 mins' },
  { value: 45, label: '45 mins' },
  { value: 60, label: '1 hour' },
];

function formatTime12(timeStr) {
  if (!timeStr) return '';
  const [h, m] = timeStr.split(':').map(Number);
  const ampm = h >= 12 ? 'pm' : 'am';
  const h12 = h % 12 || 12;
  return `${h12}:${String(m).padStart(2, '0')}${ampm}`;
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

function getMinutesFromNow(timeStr) {
  if (!timeStr) return Infinity;
  const [h, m] = timeStr.split(':').map(Number);
  const now = new Date();
  return (h * 60 + m) - (now.getHours() * 60 + now.getMinutes());
}

function getRecurrenceLabel(ev) {
  if (ev.recurrence === 'none') return 'one-off';
  if (ev.recurrence === 'daily') return 'daily';
  if (ev.recurrence === 'weekdays') return 'Mon, Tue, Wed, Thu, Fri';
  if ((ev.recurrence === 'weekly' || ev.recurrence === 'custom') && ev.recurrence_days?.length > 0) {
    return ev.recurrence_days.map((d) => dayNames[d] || '').join(', ');
  }
  return ev.recurrence;
}

function getEventsForDay(allEvents, dayOffset) {
  const target = new Date();
  target.setDate(target.getDate() + dayOffset);
  const jsDay = target.getDay();
  const pyDay = jsDay === 0 ? 6 : jsDay - 1;
  const targetStr = `${target.getFullYear()}-${String(target.getMonth() + 1).padStart(2, '0')}-${String(target.getDate()).padStart(2, '0')}`;
  return allEvents.filter((ev) => {
    switch (ev.recurrence) {
      case 'daily': return true;
      case 'weekdays': return pyDay < 5;
      case 'weekly': return ev.recurrence_days?.includes(pyDay);
      case 'custom': return ev.recurrence_days?.includes(pyDay);
      case 'none': default:
        // One-off events: match by event_date if set, otherwise show always
        if (ev.event_date) return ev.event_date === targetStr;
        return true;
    }
  }).sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
}

function getTodayStr() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

const EMPTY_FORM = {
  title: '', event_type: 'school_drop', start_time: '09:00',
  recurrence: 'none', recurrence_days: [],
  travel_time_minutes: 15, description: '',
  child: '', date: getTodayStr(),
};

export default function SchedulePage() {
  const [allEvents, setAllEvents] = useState([]);
  const [childList, setChildList] = useState([]);
  const [profileData, setProfileData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');
  const [showForm, setShowForm] = useState(false);
  const [saving, setSaving] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState({ ...EMPTY_FORM });

  useEffect(() => { loadData(); }, []);

  async function loadData() {
    setLoading(true);
    const [ev, ch, prof] = await Promise.all([
      events.list('active=true'),
      childrenApi.list(),
      profileApi.get(),
    ]);
    if (!ev.error) setAllEvents(Array.isArray(ev) ? ev : []);
    if (!ch.error) setChildList(Array.isArray(ch) ? ch : []);
    if (!prof.error) setProfileData(prof);
    setLoading(false);
  }

  function openAdd() {
    setEditingId(null);
    setForm({ ...EMPTY_FORM, date: getTodayStr() });
    setShowForm(true);
  }

  function openEdit(ev) {
    setEditingId(ev.id);
    setForm({
      title: ev.title, event_type: ev.event_type,
      start_time: ev.start_time?.slice(0, 5) || '09:00',
      recurrence: (ev.recurrence === 'weekdays' || ev.recurrence === 'weekly' || ev.recurrence === 'custom' || ev.recurrence === 'daily') ? 'weekly' : 'none',
      recurrence_days: ev.recurrence_days || [],
      travel_time_minutes: ev.travel_time_minutes || 0,
      description: ev.description || '', child: ev.child || '', date: getTodayStr(),
    });
    setShowForm(true);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setSaving(true);
    let recurrence = form.recurrence;
    let recurrence_days = [];
    if (form.recurrence === 'weekly') {
      recurrence_days = [...form.recurrence_days].sort();
      if (recurrence_days.length === 7) recurrence = 'daily';
      else if (recurrence_days.length === 5 && [0,1,2,3,4].every(d => recurrence_days.includes(d))) recurrence = 'weekdays';
      else recurrence = 'custom';
    }
    const data = {
      title: form.title, event_type: form.event_type, start_time: form.start_time,
      recurrence, recurrence_days,
      travel_time_minutes: parseInt(form.travel_time_minutes) || 0,
      description: form.description,
    };
    if (form.recurrence === 'none' && form.date) data.event_date = form.date;
    if (form.child) data.child = parseInt(form.child);
    const result = editingId ? await events.update(editingId, data) : await events.create(data);
    if (!result.error) {
      setShowForm(false); setEditingId(null); setForm({ ...EMPTY_FORM }); loadData();
    }
    setSaving(false);
  }

  async function handleDelete(id) { await events.delete(id); loadData(); }

  // For new_mom: hide school/class events linked to infants (age 0)
  const childActivityTypes = ['school_drop', 'school_pick', 'child_activity', 'class'];
  const infantChildIds = new Set(
    profileData?.user_type === 'new_mom'
      ? childList.filter(c => c.age < 1).map(c => c.id)
      : []
  );
  const hasOnlyInfants = profileData?.user_type === 'new_mom' && childList.length > 0 && childList.every(c => c.age < 1);

  function filterEvents(list) {
    let filtered = list;

    // Hide infant-only child activities for new_mom
    if (infantChildIds.size > 0) {
      filtered = filtered.filter(ev => {
        if (!childActivityTypes.includes(ev.event_type)) return true;
        // If event is linked to an infant, hide it
        if (ev.child && infantChildIds.has(ev.child)) return false;
        // If event has no child linked and user has only infants, hide it
        if (!ev.child && hasOnlyInfants) return false;
        return true;
      });
    }

    if (filter === 'all') return filtered;
    const tab = FILTER_TABS.find((t) => t.key === filter);
    return tab?.types ? filtered.filter((ev) => tab.types.includes(ev.event_type)) : filtered;
  }

  const todayEvents = filterEvents(getEventsForDay(allEvents, 0));
  const todayIds = new Set(todayEvents.map((ev) => ev.id));
  const tomorrowEvents = filterEvents(getEventsForDay(allEvents, 1)).filter((ev) => !todayIds.has(ev.id));

  // "Upcoming" = only recurring events (they repeat into future weeks/months)
  // One-off events already show in Today/Tomorrow and have no future date
  const upcomingEvents = filterEvents(
    allEvents.filter((ev) => ev.recurrence && ev.recurrence !== 'none')
  ).sort((a, b) => (a.start_time || '').localeCompare(b.start_time || ''));
  const groupedByType = {};
  upcomingEvents.forEach((ev) => {
    const badge = typeBadge[ev.event_type] || { label: ev.event_type };
    const key = badge.label;
    if (!groupedByType[key]) groupedByType[key] = [];
    groupedByType[key].push(ev);
  });

  if (loading) return <div className="loading"><div className="spinner" />Loading schedule...</div>;

  return (
    <div style={{ paddingBottom: 100 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 16px 0' }}>
        <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Georgia, serif', color: '#1a1a1a' }}>Schedule</div>
        {!showForm && (
          <button onClick={openAdd} style={{
            background: '#C2855A', color: '#fff', border: 'none', borderRadius: 10,
            padding: '8px 16px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
          }}>+ Add Event</button>
        )}
      </div>

      {/* Inline form */}
      {showForm && (
        <div style={{ padding: '16px 16px 0' }}>
          <div style={{
            background: '#fff', border: '1px solid #EDE8E3', borderRadius: 16,
            padding: '20px 18px',
          }}>
            <div style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              marginBottom: 20,
            }}>
              <div style={{ fontSize: 17, fontWeight: 600, fontFamily: 'Georgia, serif', color: '#1a1a1a' }}>
                {editingId ? 'Edit event' : 'New event'}
              </div>
              <button onClick={() => { setShowForm(false); setEditingId(null); }} style={{
                border: 'none', background: 'none', fontSize: 22, color: '#bbb',
                cursor: 'pointer', padding: '0 2px', lineHeight: 1,
              }}>×</button>
            </div>

            <form onSubmit={handleSubmit}>
              <FormLabel>Event name</FormLabel>
              <input className="auth-input" placeholder="e.g. Football — Aiden" value={form.title}
                onChange={(e) => setForm({ ...form, title: e.target.value })} required
                autoFocus style={{ marginBottom: 16, fontSize: 14 }} />

              <FormLabel>Type</FormLabel>
              <select className="auth-input" value={form.event_type}
                onChange={(e) => setForm({ ...form, event_type: e.target.value })} style={{ marginBottom: 16, fontSize: 14 }}>
                <option value="school_drop">School (pickup / dropoff)</option>
                <option value="child_activity">Child activity / class</option>
                <option value="appointment">Appointment</option>
                <option value="personal">Personal</option>
                <option value="meeting">Meeting</option>
                <option value="work_shift">Work shift</option>
                <option value="class">Class / Lecture</option>
                <option value="exam">Exam</option>
              </select>

              {childList.length > 0 && (
                <>
                  <FormLabel>Child (optional)</FormLabel>
                  <select className="auth-input" value={form.child}
                    onChange={(e) => setForm({ ...form, child: e.target.value })} style={{ marginBottom: 16, fontSize: 14 }}>
                    <option value="">None</option>
                    {childList.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                  </select>
                </>
              )}

              <FormLabel>Repeats</FormLabel>
              <div style={{ display: 'flex', gap: 0, marginBottom: 16, borderRadius: 10, overflow: 'hidden', border: '1px solid #EDE8E3' }}>
                {[
                  { value: 'none', label: 'One-off' },
                  { value: 'weekly', label: 'Weekly' },
                ].map((opt) => (
                  <button key={opt.value} type="button" onClick={() => setForm({ ...form, recurrence: opt.value, recurrence_days: opt.value === 'weekly' && form.recurrence_days.length === 0 ? [0,1,2,3,4] : form.recurrence_days })} style={{
                    flex: 1, padding: '10px 0', border: 'none', fontSize: 13, fontWeight: 600, cursor: 'pointer',
                    background: form.recurrence === opt.value ? '#E8F5EE' : '#fff',
                    color: form.recurrence === opt.value ? '#2D7A4F' : '#888',
                  }}>{opt.label}</button>
                ))}
              </div>

              {form.recurrence === 'weekly' && (
                <>
                  <FormLabel>Days</FormLabel>
                  <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
                    {dayNames.map((day, i) => {
                      const selected = form.recurrence_days.includes(i);
                      return (
                        <button key={i} type="button" onClick={() => {
                          const days = selected
                            ? form.recurrence_days.filter((d) => d !== i)
                            : [...form.recurrence_days, i];
                          setForm({ ...form, recurrence_days: days });
                        }} style={{
                          width: 40, height: 34, borderRadius: 20, fontSize: 12, fontWeight: 600,
                          border: selected ? '1.5px solid #C2855A' : '1px solid #EDE8E3',
                          background: selected ? '#FDF2EB' : '#fff',
                          color: selected ? '#C2855A' : '#999',
                          cursor: 'pointer',
                        }}>{day}</button>
                      );
                    })}
                  </div>
                </>
              )}

              {form.recurrence === 'none' && (
                <>
                  <FormLabel>Date</FormLabel>
                  <input className="auth-input" type="date" value={form.date}
                    onChange={(e) => setForm({ ...form, date: e.target.value })} style={{ marginBottom: 16, fontSize: 14 }} />
                </>
              )}

              <div style={{ display: 'flex', gap: 10, marginBottom: 16 }}>
                <div style={{ flex: 1 }}>
                  <FormLabel>Time</FormLabel>
                  <input className="auth-input" type="time" value={form.start_time}
                    onChange={(e) => setForm({ ...form, start_time: e.target.value })} required style={{ fontSize: 14 }} />
                </div>
                <div style={{ flex: 1 }}>
                  <FormLabel>Alert before</FormLabel>
                  <select className="auth-input" value={form.travel_time_minutes}
                    onChange={(e) => setForm({ ...form, travel_time_minutes: e.target.value })} style={{ fontSize: 14 }}>
                    {ALERT_OPTIONS.map((opt) => <option key={opt.value} value={opt.value}>{opt.label}</option>)}
                  </select>
                </div>
              </div>

              <FormLabel>Note (optional)</FormLabel>
              <input className="auth-input" placeholder="e.g. bring kit, leave by 3:15" value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })} style={{ marginBottom: 20, fontSize: 14 }} />

              <div style={{ display: 'flex', gap: 10 }}>
                <button type="button" onClick={() => { setShowForm(false); setEditingId(null); }} style={{
                  flex: 1, padding: '14px 0', background: '#fff', color: '#1a1a1a',
                  border: '1px solid #EDE8E3', borderRadius: 12, fontSize: 15, fontWeight: 600, cursor: 'pointer',
                }}>Cancel</button>
                <button type="submit" disabled={saving} style={{
                  flex: 1, padding: '14px 0', background: '#1a1a1a', color: '#fff',
                  border: 'none', borderRadius: 12, fontSize: 15, fontWeight: 600,
                  cursor: saving ? 'default' : 'pointer', opacity: saving ? 0.6 : 1,
                }}>Save event</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Filter tabs */}
      <div style={{ display: 'flex', gap: 6, padding: '14px 16px', overflowX: 'auto', scrollbarWidth: 'none' }}>
        {FILTER_TABS.filter(tab => {
          // Hide school/classes tabs for new_mom with only infants
          if (hasOnlyInfants && (tab.key === 'school' || tab.key === 'classes')) return false;
          return true;
        }).map((tab) => (
          <button key={tab.key} onClick={() => setFilter(tab.key)} style={{
            padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
            border: 'none', cursor: 'pointer', whiteSpace: 'nowrap', flexShrink: 0,
            background: filter === tab.key ? '#1a1a1a' : '#F3F0ED',
            color: filter === tab.key ? '#fff' : '#666',
          }}>{tab.label}</button>
        ))}
      </div>

      {/* Today */}
      <EventSection label="Today" count={todayEvents.length} events={todayEvents}
        onEdit={openEdit} onDelete={handleDelete} showNow />

      {/* Tomorrow */}
      <EventSection label="Tomorrow" count={tomorrowEvents.length} events={tomorrowEvents}
        onEdit={openEdit} onDelete={handleDelete} emptyText="No additional events" />

      {/* All Events */}
      {Object.keys(groupedByType).length > 0 && (
        <div style={{ padding: '0 16px', marginBottom: 24 }}>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 4 }}>
            Upcoming
          </div>
          <div style={{ fontSize: 12, color: '#bbb', marginBottom: 12 }}>
            Recurring events for the coming weeks
          </div>
          <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #EDE8E3', overflow: 'hidden' }}>
            {Object.entries(groupedByType).map(([groupLabel, groupEvents], gi) => (
              <div key={groupLabel}>
                {gi > 0 && <div style={{ height: 1, background: '#EDE8E3' }} />}
                <div style={{
                  fontSize: 11, fontWeight: 700, color: '#999', textTransform: 'uppercase',
                  letterSpacing: 0.5, padding: '10px 14px 4px', background: '#FAFAF8',
                }}>{groupLabel}</div>
                {groupEvents.map((ev, ei) => {
                  const badge = typeBadge[ev.event_type] || { label: ev.event_type, color: '#888', bg: '#F3F0ED' };
                  const recLabel = getRecurrenceLabel(ev);
                  return (
                    <div key={ev.id} onClick={() => openEdit(ev)} style={{
                      display: 'flex', alignItems: 'center', gap: 10,
                      padding: '10px 14px', cursor: 'pointer',
                      borderTop: ei > 0 ? '1px solid #F3F0ED' : 'none',
                    }}>
                      {/* Color dot */}
                      <div style={{
                        width: 8, height: 8, borderRadius: '50%', flexShrink: 0,
                        background: badge.color, opacity: 0.7,
                      }} />
                      {/* Title + schedule */}
                      <div style={{ flex: 1, minWidth: 0 }}>
                        <div style={{ fontSize: 14, fontWeight: 500, color: '#1a1a1a', lineHeight: 1.3,
                          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
                        }}>{ev.title}</div>
                        <div style={{ fontSize: 11, color: '#aaa', marginTop: 2 }}>
                          {formatTime12(ev.start_time)}{recLabel !== 'one-off' ? ` · ${recLabel}` : ''}
                        </div>
                      </div>
                      {/* Delete */}
                      <button onClick={(e) => { e.stopPropagation(); handleDelete(ev.id); }} style={{
                        border: 'none', background: 'none', color: '#ccc', cursor: 'pointer',
                        fontSize: 16, padding: '2px 4px', flexShrink: 0,
                      }}>×</button>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Form label ──────────────────────────────────────────────────────
function FormLabel({ children }) {
  return <div style={{ fontSize: 11, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5, marginBottom: 6 }}>{children}</div>;
}

// ── Event section (Today / Tomorrow) ────────────────────────────────
function EventSection({ label, count, events: evList, onEdit, onDelete, showNow, emptyText }) {
  return (
    <div style={{ padding: '0 16px', marginBottom: 24 }}>
      {/* Section header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div style={{ fontSize: 13, fontWeight: 600, color: '#999', textTransform: 'uppercase', letterSpacing: 0.5 }}>
          {label}
        </div>
        {count > 0 && (
          <div style={{ fontSize: 12, color: '#999' }}>{count} event{count !== 1 ? 's' : ''}</div>
        )}
      </div>

      {evList.length === 0 ? (
        <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #EDE8E3', padding: '24px 16px', textAlign: 'center', color: '#aaa', fontSize: 13 }}>
          {emptyText || 'No events'}
        </div>
      ) : (
        evList.map((ev) => {
          const minsUntil = showNow ? getMinutesFromNow(ev.start_time) : Infinity;
          const isNow = showNow && minsUntil >= -30 && minsUntil <= 15;
          return <EventCard key={ev.id} ev={ev} isNow={isNow} onEdit={() => onEdit(ev)} onDelete={() => onDelete(ev.id)} />;
        })
      )}
    </div>
  );
}

// ── Event card with time on left ────────────────────────────────────
function EventCard({ ev, isNow, onEdit, onDelete }) {
  const badge = typeBadge[ev.event_type] || { label: ev.event_type, color: '#888', bg: '#F3F0ED' };
  const leaveBy = calcLeaveBy(ev.start_time, ev.travel_time_minutes);
  const recLabel = getRecurrenceLabel(ev);

  return (
    <div style={{ display: 'flex', gap: 0, marginBottom: 8 }}>
      {/* Time column */}
      <div style={{
        width: 58, flexShrink: 0, paddingTop: 14, textAlign: 'right', paddingRight: 12,
      }}>
        <div style={{ fontSize: 12, fontWeight: 600, color: '#999', lineHeight: 1.2 }}>
          {formatTime12(ev.start_time)}
        </div>
      </div>

      {/* Timeline dot */}
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: 16, flexShrink: 0, paddingTop: 14 }}>
        <div style={{
          width: 10, height: 10, borderRadius: '50%',
          background: isNow ? '#3B82F6' : '#3B82F6', opacity: isNow ? 1 : 0.4,
          flexShrink: 0,
        }} />
        <div style={{ width: 2, flex: 1, background: '#E5E7EB', marginTop: 4 }} />
      </div>

      {/* Card */}
      <div style={{
        flex: 1, marginLeft: 10,
        background: isNow ? '#FEF2F2' : '#fff',
        border: isNow ? '1px solid #FECACA' : '1px solid #EDE8E3',
        borderRadius: 14, padding: '12px 14px',
      }}>
        {/* Top row: title + actions */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div style={{ fontSize: 14, fontWeight: 600, color: '#1a1a1a', lineHeight: 1.3, flex: 1, minWidth: 0 }}>
            {ev.title}
          </div>
          <div style={{ display: 'flex', gap: 2, marginLeft: 8, flexShrink: 0 }}>
            <button onClick={onEdit} style={{ border: 'none', background: 'none', color: '#bbb', cursor: 'pointer', fontSize: 13, padding: '2px 4px' }}>✎</button>
            <button onClick={onDelete} style={{ border: 'none', background: 'none', color: '#bbb', cursor: 'pointer', fontSize: 15, padding: '2px 4px' }}>×</button>
          </div>
        </div>

        {/* Meta row: badge, now, alert, recurrence */}
        <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 6, marginTop: 6 }}>
          <span style={{
            fontSize: 10, fontWeight: 700, color: badge.color, background: badge.bg,
            borderRadius: 4, padding: '2px 6px', textTransform: 'uppercase', letterSpacing: 0.3,
          }}>
            {badge.label}
          </span>
          {isNow && (
            <span style={{ fontSize: 11, fontWeight: 700, color: '#DC2626' }}>now</span>
          )}
          {ev.travel_time_minutes > 0 && (
            <span style={{ fontSize: 11, color: '#999' }}>{ev.travel_time_minutes} min alert</span>
          )}
          <span style={{ fontSize: 11, color: '#bbb' }}>{recLabel}</span>
        </div>

        {/* Description */}
        {ev.description && (
          <div style={{ fontSize: 12, color: '#999', marginTop: 5 }}>{ev.description}</div>
        )}

        {/* Leave by */}
        {leaveBy && (
          <div style={{ fontSize: 12, fontWeight: 600, color: '#16A34A', marginTop: 5 }}>
            Leave by {formatTime12(leaveBy + ':00')}
          </div>
        )}
      </div>
    </div>
  );
}
