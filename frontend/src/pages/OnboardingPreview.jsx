import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { profile as profileApi, members as membersApi, plans } from '../services/api';

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

const ROLE_LABEL = {
  child: 'Child',
  partner: 'Partner',
  parent: 'Parent',
  grandparent: 'Grandparent',
  sibling: 'Sibling',
  helper: 'Helper',
  roommate: 'Roommate',
  other: 'Member',
};

const SPICE_LABELS = {
  1: { label: 'Mild', emoji: '🥛' },
  2: { label: 'Light', emoji: '🌿' },
  3: { label: 'Medium', emoji: '🌶️' },
  4: { label: 'Hot', emoji: '🌶️🌶️' },
  5: { label: 'Fire', emoji: '🔥' },
};

const COOKING_LABEL = {
  me: 'I cook',
  helper: 'Our helper',
  eat_out: 'Mostly order or eat out',
};

export default function OnboardingPreview() {
  const navigate = useNavigate();
  const location = useLocation();

  const { profileData: initialData, name } = location.state || {};
  const [profileData, setProfileData] = useState(initialData || {});
  const [memberList, setMemberList] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [stageIdx, setStageIdx] = useState(0);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const [prof, mems] = await Promise.all([profileApi.get(), membersApi.list()]);
      if (cancelled) return;
      if (!prof.error) setProfileData((prev) => ({ ...prev, ...prof }));
      if (!mems.error && Array.isArray(mems)) setMemberList(mems);
      setLoading(false);
    })();
    return () => { cancelled = true; };
  }, []);

  const loadingStages = buildLoadingStages(profileData, memberList, name);

  useEffect(() => {
    if (!saving) { setStageIdx(0); return; }
    const id = setInterval(() => {
      setStageIdx((prev) => Math.min(prev + 1, loadingStages.length - 1));
    }, 2400);
    return () => clearInterval(id);
  }, [saving, loadingStages.length]);

  async function handleConfirm() {
    setSaving(true);
    await plans.generate();
    navigate('/', { replace: true });
  }

  function goEdit() {
    navigate('/onboarding/form', { state: { name: profileData.display_name || name } });
  }

  if (loading) {
    return <div className="loading"><div className="spinner" />Loading summary...</div>;
  }

  const displayName = profileData.display_name || name || 'You';
  const isHalal = (profileData.dietary_restrictions || []).some(
    (d) => d.toLowerCase() === 'halal'
  );

  return (
    <div style={shellStyle}>
      <div style={topBarStyle}>
        <button onClick={() => navigate(-1)} style={backCircleStyle} aria-label="Back">
          <BackIcon />
        </button>
        <span style={{ fontSize: 12, color: '#5A5A5A' }}>Almost there</span>
        <div style={{ width: 40 }} />
      </div>

      <div style={contentStyle}>
        <div style={mockupBodyStyle}>
          <div style={mockupEyebrowStyle}>Almost there</div>
          <h1 style={mockupHeadingStyle}>
            Here's your <em style={mockupHeadingEmStyle}>household</em>, {displayName}
          </h1>
          <p style={{ ...mockupSubtitleStyle, marginBottom: 22 }}>
            Tap edit on anything you'd like to change. Otherwise, let's plan your first week.
          </p>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <SummaryCard
            avatar={<Avatar letter={initialOf(displayName)} bg="#1A1A1A" />}
            title={<span>{displayName}<YouTag /></span>}
            subtitle={profileData.age ? `Adult · ${profileData.age}` : 'Adult'}
            rows={[
              ['Diet', summarize(profileData.dietary_restrictions, 'Any')],
              ['Health', summarize(profileData.health_conditions, 'None')],
              ['Avoids', summarize(profileData.exclusions, 'None')],
            ]}
            onEdit={goEdit}
          />

          {memberList.map((m) => (
            <SummaryCard
              key={m.id}
              avatar={<Avatar letter={initialOf(m.name || ROLE_LABEL[m.role])} bg={ROLE_AVATAR_BG[m.role] || '#1A1A1A'} />}
              title={m.name || ROLE_LABEL[m.role]}
              subtitle={memberSubtitle(m)}
              rows={[
                m.member_dietary?.length ? ['Diet', summarize(m.member_dietary)] : null,
                m.member_health_conditions?.length ? ['Health', summarize(m.member_health_conditions)] : null,
                m.member_exclusions?.length ? ['Avoids', summarize(m.member_exclusions)] : null,
              ].filter(Boolean)}
              onEdit={goEdit}
            />
          ))}

          <SummaryCard
            avatar={<IconAvatar emoji="🍳" bg="#FFF8F0" />}
            title="Your kitchen"
            subtitle="Cuisine & spice"
            rows={[
              ['Primary', summarize(profileData.cuisine_preferences, 'Any')],
              profileData.secondary_cuisines?.length ? ['Occasional', summarize(profileData.secondary_cuisines)] : null,
              ['Spice', spiceText(profileData.spice_level)],
              isHalal ? ['Halal', 'Yes'] : null,
            ].filter(Boolean)}
            onEdit={goEdit}
          />

          <SummaryCard
            avatar={<IconAvatar emoji="🛒" bg="#FAF7F5" />}
            title="Cooking & shopping"
            subtitle="How food happens"
            rows={[
              ['Cooks', COOKING_LABEL[profileData.cooking_responsibility] || 'I cook'],
              profileData.grocery_day ? ['Shopping day', profileData.grocery_day] : null,
            ].filter(Boolean)}
            onEdit={goEdit}
          />

          {(profileData.kids_activity_focus?.length || profileData.kids_default_difficulty) && (
            <SummaryCard
              avatar={<IconAvatar emoji="🎨" bg="#FFF8F0" />}
              title="Kids"
              subtitle="Activity preferences"
              rows={[
                profileData.kids_activity_focus?.length
                  ? ['Focus', summarize(profileData.kids_activity_focus)]
                  : null,
                profileData.kids_default_difficulty
                  ? ['Difficulty', titleCase(profileData.kids_default_difficulty)]
                  : null,
              ].filter(Boolean)}
              onEdit={goEdit}
            />
          )}
        </div>
      </div>

      <div style={footerStyle}>
        <button onClick={handleConfirm} disabled={saving} style={ctaStyle}>
          {saving ? 'Creating your plan…' : 'Plan my first week →'}
        </button>
        <p style={{ fontSize: 11.5, color: '#9A9A9A', textAlign: 'center', marginTop: 10 }}>
          You can change everything later in settings.
        </p>
      </div>

      {saving && (
        <div style={overlayStyle}>
          <div style={overlayCardStyle}>
            <div style={{ display: 'flex', gap: 6 }}>
              {[0, 1, 2].map((i) => (
                <div key={i} style={{
                  width: 8, height: 8, borderRadius: '50%', background: '#C2855A',
                  animation: `dotPulse 1.2s ease-in-out ${i * 0.15}s infinite`,
                }} />
              ))}
            </div>
            <div
              key={stageIdx}
              style={{
                fontSize: 14, color: '#1a1a1a', fontWeight: 500,
                textAlign: 'center', maxWidth: 260, lineHeight: 1.4,
                animation: 'stageFade 0.4s ease-out',
              }}
            >
              {loadingStages[stageIdx]}
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes dotPulse {
          0%, 100% { opacity: 0.3; transform: scale(1); }
          50% { opacity: 1; transform: scale(1.4); }
        }
        @keyframes stageFade {
          from { opacity: 0; transform: translateY(4px); }
          to { opacity: 1; transform: translateY(0); }
        }
      `}</style>
    </div>
  );
}

function SummaryCard({ avatar, title, subtitle, rows, onEdit }) {
  return (
    <div style={summaryCardStyle}>
      <div style={summaryHeaderStyle}>
        {avatar}
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={summaryTitleStyle}>{title}</div>
          <div style={summarySubStyle}>{subtitle}</div>
        </div>
        <button onClick={onEdit} style={editPencilStyle} aria-label="Edit">
          <PencilIcon />
        </button>
      </div>
      {rows.length > 0 && (
        <div style={summaryBodyStyle}>
          {rows.map(([label, value]) => (
            <div key={label} style={summaryRowStyle}>
              <span style={summaryRowLabelStyle}>{label}</span>
              <span style={summaryRowValueStyle}>{value}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Avatar({ letter, bg }) {
  return (
    <div style={{
      width: 38, height: 38, borderRadius: '50%', background: bg, color: 'white',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontFamily: 'Fraunces, Georgia, serif', fontWeight: 500, fontSize: 14,
      flexShrink: 0,
    }}>{letter}</div>
  );
}

function IconAvatar({ emoji, bg }) {
  return (
    <div style={{
      width: 38, height: 38, borderRadius: '50%', background: bg,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      fontSize: 18, flexShrink: 0,
    }}>{emoji}</div>
  );
}

function YouTag() {
  return (
    <span style={{
      display: 'inline-block', background: '#C2855A', color: 'white',
      fontSize: 9, padding: '2px 6px', borderRadius: 4, marginLeft: 6,
      letterSpacing: '0.04em', textTransform: 'uppercase', fontWeight: 600,
      verticalAlign: 'middle',
    }}>YOU</span>
  );
}

function PencilIcon() {
  return (
    <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 20h9M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4z"/>
    </svg>
  );
}

function BackIcon() {
  return (
    <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor"
         strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M15 18l-6-6 6-6"/>
    </svg>
  );
}

function initialOf(s) {
  return (s || '?').trim().charAt(0).toUpperCase() || '?';
}
function summarize(arr, fallback = '—') {
  if (!arr || arr.length === 0) return fallback;
  return arr.join(' · ');
}
function spiceText(level) {
  const s = SPICE_LABELS[level] || SPICE_LABELS[3];
  return `${s.emoji} ${s.label} (${level || 3}/5)`;
}
function titleCase(s) {
  return (s || '').charAt(0).toUpperCase() + (s || '').slice(1);
}
function memberSubtitle(m) {
  const role = ROLE_LABEL[m.role] || 'Member';
  if (m.role === 'helper') return `${role} · also cooks`;
  if (m.age != null) return `${role} · ${m.age}`;
  return role;
}

// Truthful, personalised loading stages shown while the AI builds the
// first plan. Each stage describes work the backend is genuinely doing.
function buildLoadingStages(profile, members, fallbackName) {
  const name = profile.display_name || fallbackName || 'you';
  const cuisines = profile.cuisine_preferences || [];
  const primaryCuisine = cuisines[0];
  const health = profile.health_conditions || [];
  const exclusions = profile.exclusions || [];
  const isHalal = (profile.dietary_restrictions || []).some(
    (d) => d.toLowerCase() === 'halal'
  );

  const childNames = members
    .filter((m) => (m.role || 'child') === 'child')
    .map((m) => m.name)
    .filter(Boolean);
  const familyMention = childNames.length > 0
    ? `${name} and ${childNames.slice(0, 2).join(' & ')}`
    : `${name}`;

  const stages = [
    `Reading what you told me about your kitchen…`,
    primaryCuisine
      ? `Picking ${primaryCuisine} dishes for ${familyMention}…`
      : `Picking dishes for ${familyMention}…`,
  ];

  const constraints = [];
  if (isHalal) constraints.push('Halal');
  if (health.length) constraints.push(health[0]);
  if (exclusions.length) constraints.push(`no ${exclusions[0].toLowerCase()}`);
  if (constraints.length) {
    stages.push(`Calibrating to ${constraints.join(', ')}…`);
  }

  stages.push(`Plating up your week…`);
  stages.push(`Almost ready…`);
  return stages;
}

// ── Styles ──────────────────────────────────────────────────────
const shellStyle = {
  display: 'flex', flexDirection: 'column', minHeight: '100dvh',
  maxWidth: 430, margin: '0 auto', background: '#FAF7F5',
};
const topBarStyle = {
  display: 'flex', alignItems: 'center', justifyContent: 'space-between',
  padding: '12px 16px',
};
const backCircleStyle = {
  width: 40, height: 40, borderRadius: '50%', background: 'white',
  border: '1px solid #EDE8E3', display: 'flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', color: '#1A1A1A',
};
const contentStyle = { flex: 1, padding: '4px 16px 24px' };
const footerStyle = {
  position: 'sticky', bottom: 0, padding: '12px 16px calc(20px + env(safe-area-inset-bottom)) 16px',
  background: '#FAF7F5', borderTop: '0.5px solid #EDE8E3',
};
const ctaStyle = {
  width: '100%', padding: '16px 24px', borderRadius: 999, border: 'none',
  background: '#C2855A', color: 'white', fontSize: 14.5, fontWeight: 500,
  cursor: 'pointer',
};
const overlayStyle = {
  position: 'fixed', inset: 0, background: 'rgba(26,26,26,0.45)',
  backdropFilter: 'blur(2px)', display: 'flex', alignItems: 'center',
  justifyContent: 'center', zIndex: 100,
};
const overlayCardStyle = {
  background: 'white', borderRadius: 16, padding: '28px 36px',
  display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 16,
  boxShadow: '0 12px 40px rgba(0,0,0,0.18)',
};

const mockupBodyStyle = { padding: '4px 0' };
const mockupEyebrowStyle = {
  fontSize: 11, letterSpacing: '0.12em', textTransform: 'uppercase',
  color: '#C2855A', fontWeight: 500, marginBottom: 12,
};
const mockupHeadingStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontWeight: 500, fontSize: 30,
  lineHeight: 1.1, letterSpacing: '-0.02em', marginBottom: 8, color: '#1A1A1A',
};
const mockupHeadingEmStyle = { fontStyle: 'italic', fontWeight: 400, color: '#C2855A' };
const mockupSubtitleStyle = { color: '#5A5A5A', fontSize: 14, lineHeight: 1.5, maxWidth: 360 };

const summaryCardStyle = {
  background: 'white', border: '1px solid #E8E3D8', borderRadius: 14,
  overflow: 'hidden',
};
const summaryHeaderStyle = {
  padding: '12px 14px', display: 'flex', alignItems: 'center', gap: 12,
  background: '#FAF7F5', borderBottom: '1px solid #E8E3D8',
};
const summaryTitleStyle = {
  fontFamily: 'Fraunces, Georgia, serif', fontSize: 14.5, fontWeight: 500,
  lineHeight: 1.2, color: '#1A1A1A',
};
const summarySubStyle = { fontSize: 11, color: '#5A5A5A', marginTop: 1 };
const summaryBodyStyle = {
  padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 8,
};
const summaryRowStyle = {
  display: 'flex', justifyContent: 'space-between', gap: 10, alignItems: 'flex-start',
};
const summaryRowLabelStyle = {
  fontSize: 11, color: '#9A9A9A', textTransform: 'uppercase',
  letterSpacing: '0.04em', fontWeight: 500, flexShrink: 0, width: 90, paddingTop: 1,
};
const summaryRowValueStyle = {
  fontSize: 12.5, color: '#1A1A1A', textAlign: 'right', flex: 1, lineHeight: 1.4,
};
const editPencilStyle = {
  width: 26, height: 26, borderRadius: '50%', background: 'transparent',
  border: '1px solid #E8E3D8', display: 'flex', alignItems: 'center',
  justifyContent: 'center', cursor: 'pointer', flexShrink: 0, color: '#5A5A5A',
};
