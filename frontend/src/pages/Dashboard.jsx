import { useState, useEffect } from 'react';
import LogoBar from '../components/LogoBar';
import GreetingStrip from '../components/GreetingStrip';
import AlertPill from '../components/AlertPill';
import DynamicDashboard from '../components/DynamicDashboard';
import {
  plans, reminders as remindersApi,
  profile as profileApi, children as childrenApi,
  kidsActivities, grocery,
} from '../services/api';
import { getCached, setCached } from '../services/cache';

const CACHE_KEY = 'dashboard';

export default function Dashboard() {
  // Seed from the module-level cache so coming back from the recipe page (or
  // any other route) renders the last-loaded dashboard instantly instead of
  // showing the full-screen spinner and refetching from scratch.
  const cached = getCached(CACHE_KEY);
  const [profileData, setProfileData] = useState(cached?.profileData ?? null);
  const [childList, setChildList] = useState(cached?.childList ?? []);
  const [plan, setPlan] = useState(cached?.plan ?? null);
  const [upcomingReminders, setUpcomingReminders] = useState(cached?.reminders ?? []);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState('');
  const [loading, setLoading] = useState(!cached);

  const today = new Date().toISOString().split('T')[0];

  useEffect(() => {
    // With cached data we already show the dashboard, so revalidate quietly
    // (no blocking spinner). First-ever load shows the spinner.
    loadDashboard({ silent: !!cached });
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Merge onto the latest cached snapshot (not closure state, which can be
  // stale inside callbacks) so partial updates never clobber other fields.
  function cacheDashboard(next) {
    setCached(CACHE_KEY, { ...(getCached(CACHE_KEY) || {}), ...next });
  }

  async function loadDashboard({ silent = false } = {}) {
    if (!silent) setLoading(true);
    const [prof, ch, todayPlan, rem] = await Promise.all([
      profileApi.get(),
      childrenApi.list(),
      plans.get(today),
      remindersApi.upcoming(),
    ]);

    const nextProfile = !prof.error ? prof : profileData;
    if (!prof.error) setProfileData(prof);
    const allMembers = !ch.error && Array.isArray(ch) ? ch : [];
    const children = allMembers.filter((m) => (m.role || 'child') === 'child');
    setChildList(children);

    const hasPlan = todayPlan && !todayPlan.error;
    if (hasPlan) setPlan(todayPlan);
    const nextReminders = !rem.error ? rem : upcomingReminders;
    if (!rem.error) setUpcomingReminders(rem);
    setLoading(false);

    cacheDashboard({
      profileData: nextProfile,
      childList: children,
      plan: hasPlan ? todayPlan : plan,
      reminders: nextReminders,
    });

    if (!hasPlan) {
      runPlanGeneration(children);
    }
  }

  async function runPlanGeneration(children) {
    setPlanning(true);
    setPlanError('');
    const result = await plans.generate();
    if (result.error) {
      setPlanError('Could not create your plan right now. Try again in a moment.');
      setPlanning(false);
      return;
    }
    setPlan(result);
    const rem = await remindersApi.upcoming();
    if (!rem.error) setUpcomingReminders(rem);
    cacheDashboard({ plan: result, reminders: !rem.error ? rem : upcomingReminders });

    // Fire kids + grocery as separate requests so each runs on a fresh
    // worker and memory is released between AI calls. Sequential on
    // purpose — parallel would land on the same worker and defeat this.
    (async () => {
      if (children.length > 0) {
        await kidsActivities.generate().catch(() => {});
      }
      await grocery.generate().catch(() => {});
    })();

    setPlanning(false);
  }

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner" />
        Loading your day...
      </div>
    );
  }

  return (
    <>
      <LogoBar displayName={profileData?.display_name} />

      {!plan && (
        <>
          <GreetingStrip displayName={profileData?.display_name} />
          <AlertPill reminders={upcomingReminders} />
          <div className="empty-state">
            {planning ? (
              <>
                <div className="empty-state-emoji">🌅</div>
                <div className="empty-state-text">Creating your day…</div>
              </>
            ) : planError ? (
              <>
                <div className="empty-state-emoji">⚠️</div>
                <div className="empty-state-text">{planError}</div>
                <button
                  onClick={() => runPlanGeneration(childList)}
                  style={{
                    marginTop: 12, padding: '9px 20px', border: 'none', borderRadius: 22,
                    background: '#C2855A', color: 'white', fontWeight: 600, fontSize: 13,
                    cursor: 'pointer',
                  }}
                >
                  Try again
                </button>
              </>
            ) : (
              <div className="empty-state-text">Loading…</div>
            )}
          </div>
        </>
      )}

      {plan && (
        <>
          <AlertPill reminders={upcomingReminders} />
          <DynamicDashboard
            plan={plan}
            profileData={profileData}
            childList={childList}
            planDate={today}
            onPlanUpdate={(updatedPlanData) => setPlan(prev => {
              const next = { ...prev, plan_data: updatedPlanData };
              cacheDashboard({ plan: next });
              return next;
            })}
          />
        </>
      )}
    </>
  );
}
