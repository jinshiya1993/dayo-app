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

export default function Dashboard() {
  const [profileData, setProfileData] = useState(null);
  const [childList, setChildList] = useState([]);
  const [plan, setPlan] = useState(null);
  const [upcomingReminders, setUpcomingReminders] = useState([]);
  const [planning, setPlanning] = useState(false);
  const [planError, setPlanError] = useState('');
  const [loading, setLoading] = useState(true);

  const today = new Date().toISOString().split('T')[0];

  useEffect(() => {
    loadDashboard();
  }, []);

  async function loadDashboard() {
    setLoading(true);
    const [prof, ch, todayPlan, rem] = await Promise.all([
      profileApi.get(),
      childrenApi.list(),
      plans.get(today),
      remindersApi.upcoming(),
    ]);

    if (!prof.error) setProfileData(prof);
    const children = !ch.error && Array.isArray(ch) ? ch : [];
    setChildList(children);

    const hasPlan = todayPlan && !todayPlan.error;
    if (hasPlan) setPlan(todayPlan);
    if (!rem.error) setUpcomingReminders(rem);
    setLoading(false);

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
            onPlanUpdate={(updatedPlanData) => setPlan(prev => ({ ...prev, plan_data: updatedPlanData }))}
          />
        </>
      )}
    </>
  );
}
