import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { profile as profileApi, onboarding as onboardingApi } from '../services/api';

const DIETARY_OPTIONS = ['Vegetarian', 'Vegan', 'Eggetarian', 'Jain', 'Halal', 'Gluten-free', 'Dairy-free', 'High protein'];
const HEALTH_OPTIONS = ['PCOS', 'Diabetes', 'Hypothyroidism', 'Iron deficiency', 'Lactose intolerant', 'Cholesterol'];
const CUISINE_OPTIONS = ['South Indian', 'North Indian', 'Continental', 'Chinese', 'Italian', 'Mediterranean'];
const EXCLUSION_OPTIONS = ['Onion', 'Garlic', 'Beef', 'Pork', 'Seafood', 'Mushrooms'];
const DAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday'];

// Fixed step order. Dashboard sections are now derived server-side from the
// works_outside_home flag plus the children added in the Family step, so
// there's no per-persona step list to branch on.
// 'kids' is conditional — only included when at least one member has role='child'.
const STEPS_BASE = ['family', 'food', 'grocery', 'kids'];

function toggleInArray(arr, value) {
  return arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
}

export default function OnboardingForm() {
  const location = useLocation();
  const navigate = useNavigate();
  const { name, worksOutsideHome, city, wakeTime, sleepTime } = location.state || {};

  const [stepIdx, setStepIdx] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [fadeOut, setFadeOut] = useState(false);

  const [userName, setUserName] = useState(name || '');
  const [userAge, setUserAge] = useState('');
  const [dietary, setDietary] = useState([]);
  const [health, setHealth] = useState([]);
  const [exclusions, setExclusions] = useState([]);
  const [cuisines, setCuisines] = useState([]);
  const [secondaryCuisines, setSecondaryCuisines] = useState([]);
  const [spiceLevel, setSpiceLevel] = useState(3);
  const [groceryDay, setGroceryDay] = useState('');
  const [cookingResponsibility, setCookingResponsibility] = useState('me');
  const [children, setChildren] = useState([]);
  const [kidsActivityFocus, setKidsActivityFocus] = useState([]);
  const [kidsDefaultDifficulty, setKidsDefaultDifficulty] = useState('standard');
  const [kidsTimePref, setKidsTimePref] = useState('');

  const hasChildren = children.some((m) => (m.role || 'child') === 'child');
  const steps = hasChildren ? STEPS_BASE : STEPS_BASE.filter((s) => s !== 'kids');

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

  function addMember(role = 'child') {
    setChildren((prev) => [...prev, {
      role,
      name: '',
      age: '',
      age_months: 0,
      under_one: false,
      school_name: '',
      member_dietary: [],
      member_health_conditions: [],
      member_exclusions: [],
    }]);
  }

  function updateChild(idx, patch) {
    setChildren((prev) => prev.map((c, i) => (i === idx ? { ...c, ...patch } : c)));
  }

  function removeChild(idx) {
    setChildren((prev) => prev.filter((_, i) => i !== idx));
  }

  async function handleSubmit() {
    if (submitting) return;
    setSubmitting(true);

    const membersPayload = children
      .filter((c) => c.under_one ? Number(c.age_months) > 0 : Number(c.age) > 0)
      .map((c) => ({
        role: c.role || 'child',
        name: c.name.trim(),
        age: c.under_one ? 0 : Number(c.age) || 0,
        age_months: c.under_one ? Number(c.age_months) || 0 : 0,
        interests: [],
        school_name: (c.school_name || '').trim(),
        member_dietary: c.member_dietary || [],
        member_health_conditions: c.member_health_conditions || [],
        member_exclusions: c.member_exclusions || [],
      }));

    // No user_type sent — backend derives it from works_outside_home + the
    // children data. No planning_modules either — build_initial_layout now
    // derives sections from the same flags. Recurring schedule events are
    // captured later from the dashboard's Schedule page, not in onboarding.
    const profileData = {
      display_name: (userName || name || '').trim(),
      age: userAge ? Number(userAge) : null,
      works_outside_home: !!worksOutsideHome,
      family_size: 1 + membersPayload.length,
      dietary_restrictions: dietary,
      health_conditions: health,
      exclusions,
      cuisine_preferences: cuisines,
      secondary_cuisines: secondaryCuisines,
      spice_level: spiceLevel,
      grocery_day: groceryDay,
      cooking_responsibility: cookingResponsibility,
      kids_activity_focus: hasChildren ? kidsActivityFocus : [],
      kids_default_difficulty: hasChildren ? kidsDefaultDifficulty : '',
      kids_activity_time_pref: hasChildren ? kidsTimePref : '',
      members: membersPayload,
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
        {currentStep === 'food' && (
          <FoodStep
            cuisines={cuisines}
            setCuisines={setCuisines}
            secondaryCuisines={secondaryCuisines}
            setSecondaryCuisines={setSecondaryCuisines}
            spiceLevel={spiceLevel}
            setSpiceLevel={setSpiceLevel}
          />
        )}
        {currentStep === 'grocery' && (
          <GroceryStep
            groceryDay={groceryDay} setGroceryDay={setGroceryDay}
            cookingResponsibility={cookingResponsibility}
            setCookingResponsibility={setCookingResponsibility}
          />
        )}
        {currentStep === 'family' && (
          <MembersStep
            userName={userName}
            setUserName={setUserName}
            userAge={userAge}
            setUserAge={setUserAge}
            dietary={dietary}
            setDietary={setDietary}
            health={health}
            setHealth={setHealth}
            exclusions={exclusions}
            setExclusions={setExclusions}
            members={children}
            addMember={addMember}
            updateMember={updateChild}
            removeMember={removeChild}
          />
        )}
        {currentStep === 'kids' && (
          <KidsStep
            stepIdx={stepIdx}
            kidsActivityFocus={kidsActivityFocus}
            setKidsActivityFocus={setKidsActivityFocus}
            kidsDefaultDifficulty={kidsDefaultDifficulty}
            setKidsDefaultDifficulty={setKidsDefaultDifficulty}
            kidsTimePref={kidsTimePref}
            setKidsTimePref={setKidsTimePref}
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

const SECONDARY_CUISINE_OPTIONS = [
  'North Indian', 'Continental', 'Italian', 'Lebanese', 'Mediterranean',
  'Thai', 'Chinese', 'Japanese', 'Mexican', 'Korean',
];

const SPICE_LEVELS = [
  { value: 1, label: 'Mild', emoji: '🥛' },
  { value: 2, label: 'Light', emoji: '🌿' },
  { value: 3, label: 'Medium', emoji: '🌶️' },
  { value: 4, label: 'Hot', emoji: '🌶️🌶️' },
  { value: 5, label: 'Fire', emoji: '🔥' },
];

function FoodStep({
  cuisines, setCuisines,
  secondaryCuisines, setSecondaryCuisines,
  spiceLevel, setSpiceLevel,
}) {
  return (
    <>
      <div style={mockupBodyStyle}>
        <div style={mockupEyebrowStyle}>Step 2 — Your kitchen</div>
        <h1 style={mockupHeadingStyle}>
          What does your <em style={mockupHeadingEmStyle}>kitchen</em> taste like?
        </h1>
        <p style={{ ...mockupSubtitleStyle, marginBottom: 22 }}>
          This anchors every meal we suggest. The closer to your real food, the better.
        </p>
      </div>

      <Label>Cuisines</Label>
      <ChipMultiSelect options={CUISINE_OPTIONS} selected={cuisines} onToggle={(v) => setCuisines(toggleInArray(cuisines, v))} />

      <Label>
        Cuisines you enjoy occasionally
        <span style={{ color: '#aaa', fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 6 }}>
          1–2 per week
        </span>
      </Label>
      <ChipMultiSelect
        options={SECONDARY_CUISINE_OPTIONS}
        selected={secondaryCuisines}
        onToggle={(v) => setSecondaryCuisines(toggleInArray(secondaryCuisines, v))}
      />

      <Label>Spice tolerance</Label>
      <div style={spiceCardStyle}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 12 }}>
          <div style={{ fontSize: 13, fontWeight: 500 }}>How spicy do you like food?</div>
          <div style={{ fontFamily: 'Fraunces, Georgia, serif', fontSize: 18, fontWeight: 500, color: '#C2855A' }}>
            {spiceLevel} / 5
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {SPICE_LEVELS.map((s) => {
            const on = spiceLevel === s.value;
            return (
              <button
                key={s.value}
                type="button"
                onClick={() => setSpiceLevel(s.value)}
                style={{
                  flex: 1,
                  background: on ? '#C2855A' : '#FAF7F5',
                  border: '1px solid',
                  borderColor: on ? '#C2855A' : '#EDE8E3',
                  borderRadius: 10,
                  padding: '8px 4px',
                  textAlign: 'center',
                  cursor: 'pointer',
                  color: on ? 'white' : '#1a1a1a',
                }}
              >
                <div style={{ fontSize: 16, lineHeight: 1, marginBottom: 2 }}>{s.emoji}</div>
                <div style={{ fontSize: 9, fontWeight: 500 }}>{s.label}</div>
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

const spiceCardStyle = {
  background: 'white',
  border: '1px solid #EDE8E3',
  borderRadius: 14,
  padding: '14px 16px',
  marginBottom: 14,
};

const COOKING_OPTIONS = [
  { value: 'me', label: 'I cook', sub: 'Recipes will assume your skill level' },
  { value: 'helper', label: 'Our helper cooks', sub: 'Recipes written step-by-step' },
  { value: 'eat_out', label: 'We mostly order or eat out', sub: 'Plans focus on dining suggestions' },
];

function GroceryStep({ groceryDay, setGroceryDay, cookingResponsibility, setCookingResponsibility }) {
  return (
    <>
      <StepHeading title="Cooking & shopping" subtitle="A bit about how food happens at home" />

      <Label>Who does the cooking?</Label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
        {COOKING_OPTIONS.map((opt) => {
          const on = cookingResponsibility === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => setCookingResponsibility(opt.value)}
              style={{
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: 12,
                border: '0.5px solid',
                borderColor: on ? '#C2855A' : '#EDE8E3',
                background: on ? '#FFF8F0' : 'white',
                color: '#1a1a1a',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: on ? 600 : 500 }}>{opt.label}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{opt.sub}</div>
            </button>
          );
        })}
      </div>

      <Label>Grocery day <span style={{ color: '#aaa', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional)</span></Label>
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

const MEMBER_ROLES = [
  { value: 'child', label: 'Child' },
  { value: 'partner', label: 'Partner' },
  { value: 'parent', label: 'Parent' },
  { value: 'grandparent', label: 'Grandparent' },
  { value: 'sibling', label: 'Sibling' },
  { value: 'helper', label: 'Helper' },
];

const ROLE_AVATAR_BG = {
  partner: '#C97D5A',
  child: '#C9A84C',
  helper: '#6B5B95',
  parent: '#1A1A1A',
  grandparent: '#1A1A1A',
  sibling: '#C97D5A',
  roommate: '#1A1A1A',
  other: '#1A1A1A',
};

function roleLabel(value) {
  return (MEMBER_ROLES.find((r) => r.value === value) || { label: 'Member' }).label;
}

function memberMetaText(m) {
  const role = roleLabel(m.role);
  if (m.role === 'helper') return `${role} · also cooks`;
  if (m.under_one) return `${role} · ${m.age_months || 0}mo`;
  if (m.age) return `${role} · ${m.age}`;
  return role;
}

function Avatar({ letter, bg, size = 38 }) {
  return (
    <div style={{
      width: size,
      height: size,
      borderRadius: '50%',
      background: bg,
      color: 'white',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      fontFamily: 'Fraunces, Georgia, serif',
      fontWeight: 500,
      fontSize: 14,
      flexShrink: 0,
    }}>{letter}</div>
  );
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/>
    </svg>
  );
}

function MembersStep({
  userName, setUserName, userAge, setUserAge,
  dietary, setDietary, health, setHealth, exclusions, setExclusions,
  members, addMember, updateMember, removeMember,
}) {
  const [editingIdx, setEditingIdx] = useState(null);
  const [editingYou, setEditingYou] = useState(false);
  const [showRolePicker, setShowRolePicker] = useState(false);

  function handleAdd(role) {
    addMember(role);
    setShowRolePicker(false);
    setEditingIdx(members.length);  // open editor for the just-added one
  }

  const youInitial = (userName || 'Y').trim().charAt(0).toUpperCase() || 'Y';
  const youMeta = userAge ? `Adult · ${userAge}` : 'Adult';

  return (
    <div style={mockupBodyStyle}>
      <div style={mockupEyebrowStyle}>Step 1 — Household</div>
      <h1 style={mockupHeadingStyle}>
        Who's in your <em style={mockupHeadingEmStyle}>household?</em>
      </h1>
      <p style={mockupSubtitleStyle}>Add yourself first, then anyone you cook for or with.</p>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 22 }}>
        {/* YOU card */}
        {editingYou ? (
          <YouEditCard
            userName={userName}
            setUserName={setUserName}
            userAge={userAge}
            setUserAge={setUserAge}
            dietary={dietary}
            setDietary={setDietary}
            health={health}
            setHealth={setHealth}
            exclusions={exclusions}
            setExclusions={setExclusions}
            onDone={() => setEditingYou(false)}
          />
        ) : (
          <div style={youCardStyle}>
            <Avatar letter={youInitial} bg="#1A1A1A" />
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={memberNameStyle}>
                {userName || 'You'}
                <span style={youTagStyle}>YOU</span>
              </div>
              <div style={memberMetaStyle}>{youMeta}</div>
            </div>
            <button type="button" onClick={() => setEditingYou(true)} style={memberEditBtnStyle} aria-label="Edit your details">
              <PencilIcon />
            </button>
          </div>
        )}

        {members.map((m, idx) => (
          editingIdx === idx ? (
            <MemberEditCard
              key={idx}
              idx={idx}
              member={m}
              onChange={(patch) => updateMember(idx, patch)}
              onDone={() => setEditingIdx(null)}
              onRemove={() => { removeMember(idx); setEditingIdx(null); }}
            />
          ) : (
            <MemberRow
              key={idx}
              member={m}
              onEdit={() => setEditingIdx(idx)}
            />
          )
        ))}

        {showRolePicker ? (
          <div style={rolePickerCardStyle}>
            <div style={rolePickerHeaderStyle}>What's their role?</div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {MEMBER_ROLES.map((r) => (
                <button
                  key={r.value}
                  type="button"
                  onClick={() => handleAdd(r.value)}
                  style={rolePickerChipStyle}
                >
                  {r.label}
                </button>
              ))}
            </div>
            <button
              type="button"
              onClick={() => setShowRolePicker(false)}
              style={{ ...expandToggleStyle, marginTop: 10 }}
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            type="button"
            onClick={() => setShowRolePicker(true)}
            style={addPersonBtnStyle}
          >
            + Add another person
          </button>
        )}
      </div>
    </div>
  );
}

function MemberRow({ member, onEdit }) {
  const initial = (member.name || roleLabel(member.role)).trim().charAt(0).toUpperCase() || '?';
  const bg = ROLE_AVATAR_BG[member.role] || '#1A1A1A';
  const meta = memberMetaText(member);

  return (
    <div style={memberCardStyle}>
      <Avatar letter={initial} bg={bg} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={memberNameStyle}>
          {member.name || `${roleLabel(member.role)} (tap to edit)`}
        </div>
        <div style={memberMetaStyle}>{meta}</div>
      </div>
      <button type="button" onClick={onEdit} style={memberEditBtnStyle} aria-label="Edit">
        <PencilIcon />
      </button>
    </div>
  );
}

function MemberEditCard({ idx, member, onChange, onDone, onRemove }) {
  const isChild = member.role === 'child';
  const showAgeMonths = isChild && member.under_one;
  const [showOverrides, setShowOverrides] = useState(false);

  return (
    <div style={{ ...memberCardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 0, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 14, fontFamily: 'Fraunces, Georgia, serif' }}>
          Editing {roleLabel(member.role)}
        </div>
        <button type="button" onClick={onRemove} style={removeBtnStyle}>×</button>
      </div>

      <Label>Name</Label>
      <input
        className="auth-input"
        value={member.name}
        onChange={(e) => onChange({ name: e.target.value })}
        placeholder={isChild ? 'e.g. Zidan' : 'e.g. Ahmed'}
        style={{ marginBottom: 10 }}
      />

      {isChild && (
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10 }}>
          <input
            type="checkbox"
            id={`under_one_${idx}`}
            checked={!!member.under_one}
            onChange={(e) => onChange({ under_one: e.target.checked })}
          />
          <label htmlFor={`under_one_${idx}`} style={{ fontSize: 13 }}>Under 1 year old</label>
        </div>
      )}

      {showAgeMonths ? (
        <>
          <Label>Age (months)</Label>
          <input
            type="number" min="0" max="11" className="auth-input"
            value={member.age_months}
            onChange={(e) => onChange({ age_months: e.target.value })}
            style={{ marginBottom: 10 }}
          />
        </>
      ) : (
        <>
          <Label>Age (years)</Label>
          <input
            type="number" min={isChild ? '1' : '0'} max={isChild ? '20' : '120'} className="auth-input"
            value={member.age}
            onChange={(e) => onChange({ age: e.target.value })}
            style={{ marginBottom: 10 }}
          />
        </>
      )}

      {isChild && (
        <>
          <Label>School (optional)</Label>
          <input
            className="auth-input"
            value={member.school_name}
            onChange={(e) => onChange({ school_name: e.target.value })}
            placeholder="e.g. Little Stars Preschool"
            style={{ marginBottom: 10 }}
          />
        </>
      )}

      <button
        type="button"
        onClick={() => setShowOverrides((v) => !v)}
        style={expandToggleStyle}
      >
        {showOverrides ? '− Hide dietary / health' : '+ Edit dietary / health (optional)'}
      </button>

      {showOverrides && (
        <div style={{ marginTop: 10 }}>
          <p style={{ fontSize: 11, color: '#888', marginBottom: 8 }}>
            These are <i>in addition to</i> the family-wide preferences — leave empty to inherit.
          </p>
          <Label>Dietary additions</Label>
          <ChipMultiSelect
            options={DIETARY_OPTIONS}
            selected={member.member_dietary || []}
            onToggle={(v) => onChange({ member_dietary: toggleInArray(member.member_dietary || [], v) })}
          />
          <Label>Health conditions</Label>
          <ChipMultiSelect
            options={HEALTH_OPTIONS}
            selected={member.member_health_conditions || []}
            onToggle={(v) => onChange({ member_health_conditions: toggleInArray(member.member_health_conditions || [], v) })}
          />
          <Label>Foods to avoid</Label>
          <ChipMultiSelect
            options={EXCLUSION_OPTIONS}
            selected={member.member_exclusions || []}
            onToggle={(v) => onChange({ member_exclusions: toggleInArray(member.member_exclusions || [], v) })}
          />
        </div>
      )}

      <button
        type="button"
        onClick={onDone}
        style={{
          marginTop: 14,
          padding: '10px 14px',
          borderRadius: 999,
          border: 'none',
          background: '#1A1A1A',
          color: 'white',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
        }}
      >
        Done
      </button>
    </div>
  );
}

function YouEditCard({
  userName, setUserName, userAge, setUserAge,
  dietary, setDietary, health, setHealth, exclusions, setExclusions,
  onDone,
}) {
  return (
    <div style={{ ...youCardStyle, flexDirection: 'column', alignItems: 'stretch', gap: 0, padding: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <div style={{ fontWeight: 600, fontSize: 14, fontFamily: 'Fraunces, Georgia, serif' }}>
          Editing you
        </div>
      </div>

      <Label>Your name</Label>
      <input
        className="auth-input"
        value={userName}
        onChange={(e) => setUserName(e.target.value)}
        placeholder="e.g. Sara"
        style={{ marginBottom: 10 }}
      />

      <Label>Your age <span style={{ color: '#aaa', fontWeight: 400, textTransform: 'none', letterSpacing: 0 }}>(optional)</span></Label>
      <input
        type="number"
        min="13"
        max="120"
        className="auth-input"
        value={userAge}
        onChange={(e) => setUserAge(e.target.value)}
        placeholder="e.g. 32"
        style={{ marginBottom: 14 }}
      />

      <p style={{ fontSize: 11, color: '#5A5A5A', marginBottom: 8 }}>
        These set the family-wide defaults — every meal will respect them.
      </p>

      <Label>Dietary preferences</Label>
      <ChipMultiSelect
        options={DIETARY_OPTIONS}
        selected={dietary}
        onToggle={(v) => setDietary(toggleInArray(dietary, v))}
      />

      <Label>Health conditions</Label>
      <ChipMultiSelect
        options={HEALTH_OPTIONS}
        selected={health}
        onToggle={(v) => setHealth(toggleInArray(health, v))}
      />

      <Label>Foods to avoid</Label>
      <ChipMultiSelect
        options={EXCLUSION_OPTIONS}
        selected={exclusions}
        onToggle={(v) => setExclusions(toggleInArray(exclusions, v))}
      />

      <button
        type="button"
        onClick={onDone}
        style={{
          marginTop: 6,
          padding: '10px 14px',
          borderRadius: 999,
          border: 'none',
          background: '#1A1A1A',
          color: 'white',
          fontSize: 13,
          fontWeight: 500,
          cursor: 'pointer',
        }}
      >
        Done
      </button>
    </div>
  );
}

const KIDS_FOCUS_OPTIONS = [
  'Academic', 'Creative', 'Physical', 'Music', 'Outdoor',
  'Reading', 'Arts & crafts', 'Screen-free',
];

const KIDS_DIFFICULTY_OPTIONS = [
  { value: 'easy', label: 'Easy', sub: 'Extra scaffolding, simpler vocab' },
  { value: 'standard', label: 'Standard', sub: 'Age-appropriate' },
  { value: 'advanced', label: 'Advanced', sub: '1-2 years above age' },
  { value: 'olympiad', label: 'Olympiad', sub: 'Competition-grade puzzles' },
];

const KIDS_TIME_OPTIONS = [
  { value: '', label: 'No preference' },
  { value: 'after_school', label: 'After school' },
  { value: 'weekend', label: 'Weekend' },
  { value: 'both', label: 'Both' },
];

function KidsStep({
  stepIdx,
  kidsActivityFocus, setKidsActivityFocus,
  kidsDefaultDifficulty, setKidsDefaultDifficulty,
  kidsTimePref, setKidsTimePref,
}) {
  return (
    <>
      <div style={mockupBodyStyle}>
        <div style={mockupEyebrowStyle}>Step {stepIdx + 1} — Kids</div>
        <h1 style={mockupHeadingStyle}>
          What do your <em style={mockupHeadingEmStyle}>kids</em> enjoy?
        </h1>
        <p style={{ ...mockupSubtitleStyle, marginBottom: 22 }}>
          A nudge for the activities and stories we generate. You can fine-tune per child later.
        </p>
      </div>

      <Label>
        Activity focus
        <span style={{ color: '#aaa', fontWeight: 400, textTransform: 'none', letterSpacing: 0, marginLeft: 6 }}>
          select all that fit
        </span>
      </Label>
      <ChipMultiSelect
        options={KIDS_FOCUS_OPTIONS}
        selected={kidsActivityFocus}
        onToggle={(v) => setKidsActivityFocus(toggleInArray(kidsActivityFocus, v))}
      />

      <Label>Default difficulty</Label>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 18 }}>
        {KIDS_DIFFICULTY_OPTIONS.map((opt) => {
          const on = kidsDefaultDifficulty === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => setKidsDefaultDifficulty(opt.value)}
              style={{
                textAlign: 'left',
                padding: '12px 14px',
                borderRadius: 12,
                border: '0.5px solid',
                borderColor: on ? '#C2855A' : '#EDE8E3',
                background: on ? '#FFF8F0' : 'white',
                color: '#1a1a1a',
                cursor: 'pointer',
              }}
            >
              <div style={{ fontSize: 14, fontWeight: on ? 600 : 500 }}>{opt.label}</div>
              <div style={{ fontSize: 12, color: '#888', marginTop: 2 }}>{opt.sub}</div>
            </button>
          );
        })}
      </div>

      <Label>Best time for activities</Label>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
        {KIDS_TIME_OPTIONS.map((opt) => {
          const on = kidsTimePref === opt.value;
          return (
            <button
              key={opt.value || 'none'}
              type="button"
              onClick={() => setKidsTimePref(opt.value)}
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
              {opt.label}
            </button>
          );
        })}
      </div>
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
const addRoleBtnStyle = {
  padding: '8px 14px',
  borderRadius: 20,
  border: '1px dashed #C2855A',
  background: 'transparent',
  color: '#C2855A',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
};
const expandToggleStyle = {
  background: 'transparent',
  border: 'none',
  padding: 0,
  color: '#C2855A',
  fontSize: 12,
  fontWeight: 600,
  cursor: 'pointer',
  textAlign: 'left',
};

// ── Mockup-style design tokens for the Members (step 1) screen ──────
const mockupBodyStyle = { padding: '4px 0' };
const mockupEyebrowStyle = {
  fontSize: 11,
  letterSpacing: '0.12em',
  textTransform: 'uppercase',
  color: '#C2855A',
  fontWeight: 500,
  marginBottom: 12,
};
const mockupHeadingStyle = {
  fontFamily: 'Fraunces, Georgia, serif',
  fontWeight: 500,
  fontSize: 30,
  lineHeight: 1.1,
  letterSpacing: '-0.02em',
  marginBottom: 8,
  color: '#1A1A1A',
};
const mockupHeadingEmStyle = {
  fontStyle: 'italic',
  fontWeight: 400,
  color: '#C2855A',
};
const mockupSubtitleStyle = {
  color: '#5A5A5A',
  fontSize: 14,
  lineHeight: 1.5,
  maxWidth: 360,
};
const memberCardStyle = {
  background: '#FFFFFF',
  border: '1px solid #E8E3D8',
  borderRadius: 14,
  padding: '12px 14px',
  display: 'flex',
  alignItems: 'center',
  gap: 12,
  transition: 'all 0.2s',
};
const youCardStyle = {
  ...memberCardStyle,
  background: 'linear-gradient(135deg, #FFF8F0 0%, #FFFFFF 60%)',
  borderColor: 'rgba(194,133,90,0.25)',
};
const memberNameStyle = {
  fontSize: 14,
  fontWeight: 500,
  lineHeight: 1.2,
  color: '#1A1A1A',
};
const memberMetaStyle = {
  fontSize: 11.5,
  color: '#5A5A5A',
  marginTop: 1,
};
const youTagStyle = {
  display: 'inline-block',
  background: '#C2855A',
  color: 'white',
  fontSize: 9,
  padding: '2px 6px',
  borderRadius: 4,
  marginLeft: 6,
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  fontWeight: 600,
  verticalAlign: 'middle',
};
const memberEditBtnStyle = {
  width: 28,
  height: 28,
  borderRadius: '50%',
  background: 'transparent',
  border: '1px solid #E8E3D8',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  cursor: 'pointer',
  flexShrink: 0,
  color: '#5A5A5A',
};
const addPersonBtnStyle = {
  background: 'transparent',
  border: '1.5px dashed #9A9A9A',
  borderRadius: 14,
  padding: 14,
  color: '#5A5A5A',
  fontSize: 13,
  fontWeight: 500,
  cursor: 'pointer',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  gap: 8,
};
const rolePickerCardStyle = {
  background: '#FFFFFF',
  border: '1px solid #E8E3D8',
  borderRadius: 14,
  padding: 14,
};
const rolePickerHeaderStyle = {
  fontSize: 12,
  fontWeight: 500,
  color: '#5A5A5A',
  letterSpacing: '0.04em',
  textTransform: 'uppercase',
  marginBottom: 10,
};
const rolePickerChipStyle = {
  background: '#FFFFFF',
  border: '1px solid #E8E3D8',
  borderRadius: 999,
  padding: '8px 14px',
  fontSize: 13,
  color: '#1A1A1A',
  cursor: 'pointer',
  fontFamily: 'inherit',
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
