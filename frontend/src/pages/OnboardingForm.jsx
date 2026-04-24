import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { profile as profileApi, onboarding as onboardingApi } from '../services/api';

const DIETARY_OPTIONS = ['Vegetarian', 'Vegan', 'Eggetarian', 'Jain', 'Halal', 'Gluten-free', 'Dairy-free'];
const HEALTH_OPTIONS = ['PCOS', 'Diabetes', 'Hypothyroidism', 'Iron deficiency', 'High protein', 'Lactose intolerant', 'Cholesterol'];
const CUISINE_OPTIONS = ['South Indian', 'North Indian', 'Continental', 'Chinese', 'Italian', 'Mediterranean'];
const EXCLUSION_OPTIONS = ['Onion', 'Garlic', 'Beef', 'Pork', 'Seafood', 'Mushrooms'];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];
const SHORT_DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

const EVENT_TYPES = [
  { value: 'personal', label: 'Personal' },
  { value: 'appointment', label: 'Appointment' },
  { value: 'school_drop', label: 'School drop-off' },
  { value: 'school_pick', label: 'School pick-up' },
  { value: 'child_activity', label: 'Kids activity' },
  { value: 'class', label: 'Class' },
  { value: 'study', label: 'Study' },
  { value: 'work_shift', label: 'Work shift' },
  { value: 'meeting', label: 'Meeting' },
];

const RECURRENCE_OPTIONS = [
  { value: 'none', label: 'Once' },
  { value: 'daily', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'custom', label: 'Custom days' },
];

// Fixed step order. Dashboard sections are now derived server-side from the
// works_outside_home flag plus the children added in the Family step, so
// there's no per-persona step list to branch on.
const STEPS = ['household', 'food', 'grocery', 'family', 'schedule'];

function toggleInArray(arr, value) {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

export default function OnboardingForm() {
  const location = useLocation();
  const navigate = useNavigate();
  const { name, worksOutsideHome, city, wakeTime, sleepTime } = location.state || {};

  const steps = STEPS;

  const [stepIdx, setStepIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  const [familySize, setFamilySize] = useState(1);
  const [dietary, setDietary] = useState([]);
  const [health, setHealth] = useState([]);
  const [exclusions, setExclusions] = useState([]);
  const [cuisines, setCuisines] = useState([]);
  const [groceryDay, setGroceryDay] = useState('');
  const [children, setChildren] = useState([]);
  const [events, setEvents] = useState([]);

  useEffect(() => {
    if (!name) {
      navigate('/onboarding', { replace: true });
    }
  }, [name, navigate]);

  const currentStep = steps[stepIdx];
  const isLast = stepIdx === steps.length - 1;

  function next() {
    if (stepIdx < steps.length - 1) setStepIdx(stepIdx + 1);
  }

  function back() {
    if (stepIdx > 0) setStepIdx(stepIdx - 1);
  }

  function addChild() {
    setChildren((prev) => [...prev, { name: '', age: '', age_months: 0, under_one: false, school_name: '' }]);
  }

  function updateChild(idx, patch) {
    setChildren((prev) => prev.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }

  function removeChild(idx) {
    setChildren((prev) => prev.filter((_, i) => i !== idx));
  }

  function addEvent() {
    setEvents((prev) => [
      ...prev,
      {
        title: '',
        event_type: 'personal',
        start_time: '09:00',
        end_time: '',
        recurrence: 'weekdays',
        recurrence_days: [],
        child_name: '',
      },
    ]);
  }

  function updateEvent(idx, patch) {
    setEvents((prev) => prev.map((e, i) => (i === idx ? { ...e, ...patch } : e)));
  }

  function removeEvent(idx) {
    setEvents((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit() {
    if (submitting) return;
    setSubmitting(true);

    const childrenPayload = children
      .filter((c) => c.under_one ? Number(c.age_months) > 0 : Number(c.age) > 0)
      .map((c) => ({
        name: c.name.trim(),
        age: c.under_one ? 0 : Number(c.age) || 0,
        age_months: c.under_one ? Number(c.age_months) || 0 : 0,
        interests: [],
        school_name: (c.school_name || '').trim(),
      }));

    const eventsPayload = events
      .filter((e) => e.title.trim())
      .map((e) => ({
        title: e.title.trim(),
        event_type: e.event_type,
        start_time: e.start_time || '09:00',
        end_time: e.end_time || '',
        recurrence: e.recurrence,
        recurrence_days: e.recurrence === 'custom' ? e.recurrence_days : [],
        child_name: e.child_name || '',
      }));

    // No user_type sent — backend derives it from works_outside_home + the
    // children data. No planning_modules either — build_initial_layout now
    // derives sections from the same flags.
    const profileData = {
      display_name: name,
      works_outside_home: !!worksOutsideHome,
      family_size: Number(familySize) || 1,
      dietary_restrictions: dietary,
      health_conditions: health,
      exclusions,
      cuisine_preferences: cuisines,
      grocery_day: groceryDay,
      children: childrenPayload,
      schedule_events: eventsPayload,
      notes: '',
    };

    const result = await onboardingApi.complete(profileData);
    if (result?.error) {
      setSubmitting(false);
      alert(result.error || 'Something went wrong. Please try again.');
      return;
    }

    // Save city/wake/sleep in the background — same pattern as the chat flow.
    const update = {};
    if (city) update.location_city = city;
    if (wakeTime) update.wake_time = wakeTime;
    if (sleepTime) update.sleep_time = sleepTime;
    if (Object.keys(update).length > 0) profileApi.update(update);

    setFadeOut(true);
    setTimeout(() => {
      navigate('/onboarding/preview', {
        replace: true,
        state: { name, profileData: result.profile_data || profileData },
      });
    }, 400);
  }

  return (
    <div style={{ ...shellStyle, opacity: fadeOut ? 0 : 1 }}>
      <div style={topBarStyle}>
        <div style={logoStyle}>
          da<span style={{ color: '#C2855A' }}>yo</span>
        </div>
        <ProgressDots current={stepIdx + 1} total={steps.length} />
      </div>

      <div style={contentStyle}>
        {currentStep === 'household' && (
          <HouseholdStep
            familySize={familySize}
            setFamilySize={setFamilySize}
            dietary={dietary}
            setDietary={setDietary}
            health={health}
            setHealth={setHealth}
            exclusions={exclusions}
            setExclusions={setExclusions}
          />
        )}
        {currentStep === 'food' && (
          <FoodStep cuisines={cuisines} setCuisines={setCuisines} />
        )}
        {currentStep === 'grocery' && (
          <GroceryStep groceryDay={groceryDay} setGroceryDay={setGroceryDay} />
        )}
        {currentStep === 'family' && (
          <ChildrenStep
            children={children}
            addChild={addChild}
            updateChild={updateChild}
            removeChild={removeChild}
          />
        )}
        {currentStep === 'schedule' && (
          <ScheduleStep
            events={events}
            addEvent={addEvent}
            updateEvent={updateEvent}
            removeEvent={removeEvent}
            children={children}
          />
        )}
      </div>

      <div style={footerStyle}>
        {stepIdx > 0 ? (
          <button onClick={back} style={backBtnStyle} disabled={submitting}>
            Back
          </button>
        ) : (
          <span />
        )}
        {isLast ? (
          <button
            onClick={handleSubmit}
            className="auth-btn"
            style={primaryBtnStyle}
            disabled={submitting}
          >
            {submitting ? 'Creating...' : 'Create my plan'}
          </button>
        ) : (
          <button onClick={next} className="auth-btn" style={primaryBtnStyle}>
            Next
          </button>
        )}
      </div>
    </div>
  );
}

// ── Sub-components ───────────────────────────────────────────────────

function ProgressDots({ current, total }) {
  return (
    <div style={{ display: 'flex', gap: 6 }}>
      {Array.from({ length: total }, (_, i) => (
        <div
          key={i}
          style={{
            width: 8,
            height: 8,
            borderRadius: '50%',
            background: i < current ? '#C2855A' : '#EDE8E3',
            transition: 'background 0.3s',
          }}
        />
      ))}
    </div>
  );
}

function ChipMultiSelect({ options, selected, onToggle, allowCustom = true }) {
  const [draft, setDraft] = useState('');
  // Always show options ∪ selected so custom chips survive step navigation.
  const rendered = [...options, ...selected.filter((s) => !options.includes(s))];

  function addCustom() {
    const text = draft.trim();
    if (!text) return;
    if (!selected.includes(text)) onToggle(text);
    setDraft('');
  }

  return (
    <>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 10 }}>
        {rendered.map((opt) => {
          const on = selected.includes(opt);
          return (
            <button
              key={opt}
              type="button"
              onClick={() => onToggle(opt)}
              style={{
                padding: '8px 14px',
                borderRadius: 20,
                border: '0.5px solid',
                borderColor: on ? '#C2855A' : '#EDE8E3',
                background: on ? '#FFF8F0' : 'white',
                color: '#1a1a1a',
                fontSize: 13,
                fontWeight: on ? 600 : 500,
                cursor: 'pointer',
              }}
            >
              {opt}
            </button>
          );
        })}
      </div>
      {allowCustom && (
        <div style={{ display: 'flex', gap: 6, marginBottom: 12 }}>
          <input
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                addCustom();
              }
            }}
            placeholder="Add your own..."
            style={customInputStyle}
          />
          <button type="button" onClick={addCustom} style={addBtnStyle} disabled={!draft.trim()}>
            Add
          </button>
        </div>
      )}
    </>
  );
}

function StepHeading({ title, subtitle }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <h2 style={{ fontFamily: 'Georgia, serif', fontSize: 22, margin: 0 }}>{title}</h2>
      {subtitle && <p style={{ color: '#888', fontSize: 13, marginTop: 4 }}>{subtitle}</p>}
    </div>
  );
}

function Label({ children }) {
  return (
    <label
      style={{
        display: 'block',
        fontSize: 12,
        fontWeight: 600,
        color: '#888',
        textTransform: 'uppercase',
        letterSpacing: 0.5,
        marginBottom: 6,
        marginTop: 6,
      }}
    >
      {children}
    </label>
  );
}

function HouseholdStep({ familySize, setFamilySize, dietary, setDietary, health, setHealth, exclusions, setExclusions }) {
  return (
    <>
      <StepHeading title="Your household" subtitle="We'll use this to plan meals and portions" />
      <Label>How many people do you cook for?</Label>
      <input
        type="number"
        min="1"
        max="20"
        value={familySize}
        onChange={(e) => setFamilySize(e.target.value)}
        className="auth-input"
        style={{ marginBottom: 14 }}
      />
      <Label>Any dietary restrictions?</Label>
      <ChipMultiSelect options={DIETARY_OPTIONS} selected={dietary} onToggle={(v) => setDietary(toggleInArray(dietary, v))} />
      <Label>Any health conditions we should plan around?</Label>
      <ChipMultiSelect options={HEALTH_OPTIONS} selected={health} onToggle={(v) => setHealth(toggleInArray(health, v))} />
      <Label>Any foods to avoid?</Label>
      <ChipMultiSelect options={EXCLUSION_OPTIONS} selected={exclusions} onToggle={(v) => setExclusions(toggleInArray(exclusions, v))} />
    </>
  );
}

function FoodStep({ cuisines, setCuisines }) {
  return (
    <>
      <StepHeading title="Food preferences" subtitle="Pick the cuisines you cook most" />
      <Label>Cuisines</Label>
      <ChipMultiSelect options={CUISINE_OPTIONS} selected={cuisines} onToggle={(v) => setCuisines(toggleInArray(cuisines, v))} />
    </>
  );
}

function GroceryStep({ groceryDay, setGroceryDay }) {
  return (
    <>
      <StepHeading title="Grocery day" subtitle="When do you usually shop? (optional)" />
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8 }}>
        {DAYS.map((day) => {
          const on = groceryDay === day;
          return (
            <button
              key={day}
              type="button"
              onClick={() => setGroceryDay(on ? '' : day)}
              style={{
                padding: '12px 14px',
                borderRadius: 12,
                border: '0.5px solid',
                borderColor: on ? '#C2855A' : '#EDE8E3',
                background: on ? '#FFF8F0' : 'white',
                color: '#1a1a1a',
                fontSize: 14,
                fontWeight: on ? 600 : 500,
                cursor: 'pointer',
              }}
            >
              {day}
            </button>
          );
        })}
      </div>
    </>
  );
}

function ChildrenStep({ children, addChild, updateChild, removeChild }) {
  return (
    <>
      <StepHeading title="Your family" subtitle="Add each child so we can plan around them. Skip this step if you don't have kids." />
      {children.length === 0 && <p style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>No children added yet — tap below to add one, or leave empty.</p>}
      {children.map((child, idx) => (
        <div key={idx} style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Child {idx + 1}</div>
            <button type="button" onClick={() => removeChild(idx)} style={removeBtnStyle}>×</button>
          </div>
          <Label>Name</Label>
          <input className="auth-input" value={child.name} onChange={(e) => updateChild(idx, { name: e.target.value })} placeholder="e.g. Zidan" style={{ marginBottom: 10 }} />
          <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
            <input
              type="checkbox"
              id={`under_one_${idx}`}
              checked={!!child.under_one}
              onChange={(e) => updateChild(idx, { under_one: e.target.checked })}
            />
            <label htmlFor={`under_one_${idx}`} style={{ fontSize: 13 }}>Under 1 year old</label>
          </div>
          {child.under_one ? (
            <>
              <Label>Age (months)</Label>
              <input type="number" min="0" max="11" className="auth-input" value={child.age_months} onChange={(e) => updateChild(idx, { age_months: e.target.value })} style={{ marginBottom: 10 }} />
            </>
          ) : (
            <>
              <Label>Age (years)</Label>
              <input type="number" min="1" max="20" className="auth-input" value={child.age} onChange={(e) => updateChild(idx, { age: e.target.value })} style={{ marginBottom: 10 }} />
            </>
          )}
          <Label>School (optional)</Label>
          <input className="auth-input" value={child.school_name} onChange={(e) => updateChild(idx, { school_name: e.target.value })} placeholder="e.g. Little Stars Preschool" />
        </div>
      ))}
      <button type="button" onClick={addChild} style={addRowBtnStyle}>+ Add a child</button>
    </>
  );
}

function ScheduleStep({ events, addEvent, updateEvent, removeEvent, children }) {
  const childNames = children.map((c) => c.name).filter(Boolean);
  return (
    <>
      <StepHeading title="Recurring commitments" subtitle="School runs, classes, work shifts — anything that repeats. Optional." />
      {events.length === 0 && <p style={{ color: '#888', fontSize: 13, marginBottom: 12 }}>No events added yet.</p>}
      {events.map((ev, idx) => (
        <div key={idx} style={cardStyle}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <div style={{ fontWeight: 600, fontSize: 14 }}>Event {idx + 1}</div>
            <button type="button" onClick={() => removeEvent(idx)} style={removeBtnStyle}>×</button>
          </div>
          <Label>Title</Label>
          <input className="auth-input" value={ev.title} onChange={(e) => updateEvent(idx, { title: e.target.value })} placeholder="e.g. Piano class" style={{ marginBottom: 10 }} />
          <Label>Type</Label>
          <select
            value={ev.event_type}
            onChange={(e) => updateEvent(idx, { event_type: e.target.value })}
            className="auth-input"
            style={{ marginBottom: 10 }}
          >
            {EVENT_TYPES.map((t) => (
              <option key={t.value} value={t.value}>{t.label}</option>
            ))}
          </select>
          <div style={{ display: 'flex', gap: 8 }}>
            <div style={{ flex: 1 }}>
              <Label>Start</Label>
              <input type="time" className="auth-input" value={ev.start_time} onChange={(e) => updateEvent(idx, { start_time: e.target.value })} />
            </div>
            <div style={{ flex: 1 }}>
              <Label>End (optional)</Label>
              <input type="time" className="auth-input" value={ev.end_time} onChange={(e) => updateEvent(idx, { end_time: e.target.value })} />
            </div>
          </div>
          <Label>Repeat</Label>
          <select
            value={ev.recurrence}
            onChange={(e) => updateEvent(idx, { recurrence: e.target.value })}
            className="auth-input"
            style={{ marginBottom: 10 }}
          >
            {RECURRENCE_OPTIONS.map((r) => (
              <option key={r.value} value={r.value}>{r.label}</option>
            ))}
          </select>
          {ev.recurrence === 'custom' && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
              {SHORT_DAYS.map((sd, dayIdx) => {
                const full = DAYS[dayIdx];
                const on = (ev.recurrence_days || []).includes(full);
                return (
                  <button
                    key={full}
                    type="button"
                    onClick={() =>
                      updateEvent(idx, { recurrence_days: toggleInArray(ev.recurrence_days || [], full) })
                    }
                    style={{
                      padding: '8px 12px',
                      borderRadius: 16,
                      border: '0.5px solid',
                      borderColor: on ? '#C2855A' : '#EDE8E3',
                      background: on ? '#FFF8F0' : 'white',
                      fontSize: 12,
                      fontWeight: on ? 600 : 500,
                      cursor: 'pointer',
                    }}
                  >
                    {sd}
                  </button>
                );
              })}
            </div>
          )}
          {childNames.length > 0 && (
            <>
              <Label>Linked child (optional)</Label>
              <select
                value={ev.child_name}
                onChange={(e) => updateEvent(idx, { child_name: e.target.value })}
                className="auth-input"
              >
                <option value="">— None —</option>
                {childNames.map((cn) => (
                  <option key={cn} value={cn}>{cn}</option>
                ))}
              </select>
            </>
          )}
        </div>
      ))}
      <button type="button" onClick={addEvent} style={addRowBtnStyle}>+ Add an event</button>
    </>
  );
}

// ── Shared inline styles ─────────────────────────────────────────────
const shellStyle = {
  display: 'flex',
  flexDirection: 'column',
  minHeight: '100dvh',
  maxWidth: 430,
  margin: '0 auto',
  background: '#FAF7F5',
  transition: 'opacity 0.4s ease-out',
};
const topBarStyle = {
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'space-between',
  padding: '14px 16px',
  borderBottom: '0.5px solid #EDE8E3',
  background: 'white',
};
const logoStyle = { fontFamily: 'Georgia, serif', fontSize: 22, fontWeight: 700 };
const contentStyle = { flex: 1, overflowY: 'auto', padding: '20px 16px 16px' };
const footerStyle = {
  display: 'flex',
  justifyContent: 'space-between',
  alignItems: 'center',
  padding: '12px 16px calc(12px + env(safe-area-inset-bottom)) 16px',
  borderTop: '0.5px solid #EDE8E3',
  background: 'white',
  gap: 12,
};
const primaryBtnStyle = { background: '#C2855A', flex: 1, maxWidth: 240 };
const backBtnStyle = {
  background: 'transparent',
  border: 'none',
  color: '#888',
  fontSize: 14,
  fontWeight: 600,
  padding: '12px 4px',
  cursor: 'pointer',
};
const cardStyle = {
  background: 'white',
  border: '0.5px solid #EDE8E3',
  borderRadius: 14,
  padding: 16,
  marginBottom: 12,
};
const removeBtnStyle = {
  background: 'transparent',
  border: 'none',
  fontSize: 22,
  color: '#888',
  cursor: 'pointer',
  lineHeight: 1,
  padding: '0 6px',
};
const addRowBtnStyle = {
  width: '100%',
  padding: '12px',
  borderRadius: 12,
  border: '1px dashed #C2855A',
  background: 'transparent',
  color: '#C2855A',
  fontSize: 14,
  fontWeight: 600,
  cursor: 'pointer',
  marginTop: 4,
};
const customInputStyle = {
  flex: 1,
  padding: '10px 14px',
  borderRadius: 20,
  border: '0.5px solid #EDE8E3',
  background: 'white',
  fontSize: 13,
  outline: 'none',
};
const addBtnStyle = {
  padding: '10px 16px',
  borderRadius: 20,
  border: 'none',
  background: '#1a1a1a',
  color: 'white',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
};
