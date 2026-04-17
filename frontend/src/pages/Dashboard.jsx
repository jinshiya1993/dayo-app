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
    if (!ch.error) setChildList(Array.isArray(ch) ? ch : []);
    if (!todayPlan.error) setPlan(todayPlan);
    if (!rem.error) setUpcomingReminders(rem);
    setLoading(false);
  }

  async function handlePlanDay() {
    setPlanning(true);
    const result = await plans.generate();
    if (!result.error) {
      setPlan(result);
      const rem = await remindersApi.upcoming();
      if (!rem.error) setUpcomingReminders(rem);

      // Fire kids + grocery as separate requests so each runs on a fresh
      // worker and memory is released between AI calls. Sequential on
      // purpose — parallel would land on the same worker and defeat this.
      (async () => {
        if (childList.length > 0) {
          await kidsActivities.generate().catch(() => {});
        }
        await grocery.generate().catch(() => {});
      })();
    }
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

      {/* No plan yet */}
      {!plan && (
        <>
          <GreetingStrip
            displayName={profileData?.display_name}
            onPlanDay={handlePlanDay}
            loading={planning}
          />
          <AlertPill reminders={upcomingReminders} />
          {!planning && (
            <div className="empty-state">
              <div className="empty-state-emoji">🌅</div>
              <div className="empty-state-text">
                No plan for today yet. Tap "Plan my day" to get started!
              </div>
            </div>
          )}
        </>
      )}

      {/* Plan exists — render user-type-specific dashboard */}
      {plan && (
        <>
          <AlertPill reminders={upcomingReminders} />
          <DynamicDashboard
            plan={plan}
            profileData={profileData}
            childList={childList}
            onPlanDay={handlePlanDay}
            planning={planning}
            planDate={today}
            onPlanUpdate={(updatedPlanData) => setPlan(prev => ({ ...prev, plan_data: updatedPlanData }))}
          />
        </>
      )}
    </>
  );
}
