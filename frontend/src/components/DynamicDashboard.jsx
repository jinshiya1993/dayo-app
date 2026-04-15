import GreetingSection from './sections/GreetingSection';
import TodaysScheduleSection from './sections/TodaysScheduleSection';
import MealCardsSection from './sections/MealCardsSection';
import MealCompactSection from './sections/MealCompactSection';
import GrocerySection from './sections/GrocerySection';
import KidsActivitiesSection from './sections/KidsActivitiesSection';
import HouseworkSection from './sections/HouseworkSection';
import MeTimeSection from './sections/MeTimeSection';
import DeepWorkSection from './sections/DeepWorkSection';
import PrioritiesSection from './sections/PrioritiesSection';
import MeetingsSection from './sections/MeetingsSection';
import EndOfDaySection from './sections/EndOfDaySection';
import ExerciseSection from './sections/ExerciseSection';
import EveningRoutineSection from './sections/EveningRoutineSection';
import ErrandsSection from './sections/ErrandsSection';
import QuickChipsSection from './sections/QuickChipsSection';
import NotesSection from './sections/NotesSection';
import BabyScheduleSection from './sections/BabyScheduleSection';
import MomRestSection from './sections/MomRestSection';
import RecoveryExerciseSection from './sections/RecoveryExerciseSection';
import SelfcareListSection from './sections/SelfcareListSection';
import MilestonesSection from './sections/MilestonesSection';
import EssentialsSection from './sections/EssentialsSection';
import CustomSection from './sections/CustomSection';

// ─── Section registry ────────────────────────────────────────────
const SECTIONS = {
  greeting:           { component: GreetingSection, dataKey: null },
  // schedule_alert / class_alert rendered outside layout loop — see below
  meal_cards:         { component: MealCardsSection, dataKey: 'meals' },
  meal_compact:       { component: MealCompactSection, dataKey: 'meals' },
  mom_meals:          { component: MealCardsSection, dataKey: 'mom_meals' },
  grocery:            { component: GrocerySection, dataKey: null },
  kids_activities:    { component: KidsActivitiesSection, dataKey: null },
  housework:          { component: HouseworkSection, dataKey: null },
  me_time:            { component: MeTimeSection, dataKey: 'selfcare' },
  deep_work:          { component: DeepWorkSection, dataKey: 'deep_work' },
  priorities:         { component: PrioritiesSection, dataKey: 'priorities' },
  meetings:           { component: MeetingsSection, dataKey: 'meetings' },
  end_of_day:         { component: EndOfDaySection, dataKey: 'end_of_day' },
  exercise:           { component: ExerciseSection, dataKey: 'exercise' },
  evening_routine:    { component: EveningRoutineSection, dataKey: 'evening_routine' },
  errands:            { component: ErrandsSection, dataKey: 'errands' },
  quick_chips:        { component: QuickChipsSection, dataKey: null },
  notes:              { component: NotesSection, dataKey: 'notes' },
  // New mom sections
  baby_schedule:      { component: BabyScheduleSection, dataKey: 'baby_schedule' },
  mom_rest:           { component: MomRestSection, dataKey: 'mom_rest' },
  recovery_exercise:  { component: RecoveryExerciseSection, dataKey: 'recovery_exercise' },
  selfcare_list:      { component: SelfcareListSection, dataKey: 'selfcare' },
  milestones:         { component: MilestonesSection, dataKey: 'milestones' },
  essentials:         { component: EssentialsSection, dataKey: null },
};

// ─── Fallback layouts (only used if custom_layout is empty) ──────
const FALLBACK_LAYOUTS = {
  parent:       ['greeting', 'schedule_alert', 'meal_cards', 'grocery', 'kids_activities', 'housework', 'me_time', 'notes', 'quick_chips'],
  new_mom:      ['greeting', 'schedule_alert', 'meal_cards', 'essentials', 'grocery', 'exercise', 'selfcare_list', 'housework', 'me_time', 'notes', 'quick_chips'],
  homemaker:    ['greeting', 'schedule_alert', 'meal_cards', 'grocery', 'housework', 'me_time', 'notes', 'quick_chips'],
  working_mom:  ['greeting', 'schedule_alert', 'meal_cards', 'grocery', 'priorities', 'kids_activities', 'evening_routine', 'me_time', 'notes', 'quick_chips'],
  professional: ['greeting', 'schedule_alert', 'deep_work', 'priorities', 'meetings', 'meal_compact', 'grocery', 'exercise', 'end_of_day', 'notes', 'quick_chips'],
};

// ─── Build layout from 3 layers ──────────────────────────────────
function buildLayout(profileData, userType) {
  const customLayout = profileData?.custom_layout;

  // Layer 3 wins — if user has customised their layout, use it
  if (customLayout && customLayout.length > 0) {
    const sections = ['greeting']; // greeting always first
    for (const item of customLayout) {
      if (item.visible !== false && item.key !== 'greeting') {
        sections.push(item.key);
      }
    }
    // Always end with quick_chips if not already there
    if (!sections.includes('quick_chips')) sections.push('quick_chips');
    return sections;
  }

  // Layer 1 fallback — use user_type defaults
  return FALLBACK_LAYOUTS[userType] || FALLBACK_LAYOUTS.homemaker;
}

// ─── Quick chips (context-aware) ─────────────────────────────────
function getQuickChips(planData, childList, layout) {
  const d = planData || {};

  // Prefer AI-generated chips from plan data
  if (d.quick_chips?.length > 0) {
    return d.quick_chips.slice(0, 3);
  }

  // Fallback: generate from active sections
  const chips = [];
  const has = (key) => layout.includes(key);

  if (d.baby?.name) chips.push(`${d.baby.name} won't sleep`);
  if (has('schedule_alert') || has('class_alert')) chips.push('Add an event');
  if (childList?.length > 0 && has('kids_activities')) chips.push(`${childList[0].name} is sick`);

  if (has('meal_cards') || has('meal_compact') || has('mom_meals')) chips.push('Quick dinner idea');
  if (has('exercise') || has('recovery_exercise')) chips.push('Skip workout today');
  if (has('selfcare_list') || has('me_time') || has('mom_rest')) chips.push('I need a break');
  if (has('grocery')) chips.push('Skip grocery');
  if (has('meetings')) chips.push('Reschedule meeting');
  if (has('priorities') || has('deep_work')) chips.push('Add a task');
  if (has('baby_schedule')) chips.push('Feeding trouble');

  return [...new Set(chips)].slice(0, 3);
}

// ─── Component ───────────────────────────────────────────────────
export default function DynamicDashboard({ plan, profileData, childList, onPlanDay, planning, planDate, onPlanUpdate }) {
  const planData = plan?.plan_data || {};
  const userType = planData.user_type || profileData?.user_type || 'homemaker';
  const layout = buildLayout(profileData, userType);
  const chips = getQuickChips(planData, childList, layout);

  return (
    <>
      {/* Greeting always first */}
      <GreetingSection profileData={profileData} onPlanDay={onPlanDay} planning={planning} />

      {/* Morning greeting — new mom only */}
      {userType === 'new_mom' && planData.morning_greeting && (
        <div style={{
          margin: '0 16px 14px', padding: '12px 14px',
          background: '#F5F0FF', borderRadius: 14,
          fontSize: 13.5, color: '#6B46C1', lineHeight: 1.5,
          fontStyle: 'italic',
        }}>
          {planData.morning_greeting}
        </div>
      )}

      {/* Schedule alerts — always right after greeting, outside layout */}
      <TodaysScheduleSection />

      {layout.map((sectionKey) => {
        // Skip greeting (rendered above) and schedule (rendered above)
        if (sectionKey === 'greeting' || sectionKey === 'schedule_alert' || sectionKey === 'class_alert') return null;

        const config = SECTIONS[sectionKey];

        // Custom user-added section — interactive checklist
        if (!config) {
          const layoutItem = (profileData?.custom_layout || []).find((i) => i.key === sectionKey);
          if (layoutItem?.added_by_user || layoutItem?.custom_label) {
            const label = layoutItem?.custom_label || sectionKey.replace(/_/g, ' ');
            return <CustomSection key={sectionKey} sectionKey={sectionKey} label={label} />;
          }
          return null;
        }

        const Component = config.component;

        // Special props for specific sections
        if (sectionKey === 'quick_chips') {
          return <Component key={sectionKey} chips={chips} />;
        }

        // Baby schedule needs baby info too
        if (sectionKey === 'baby_schedule') {
          return <Component key={sectionKey} data={planData.baby_schedule} baby={planData.baby} />;
        }

        // Meal sections need planData for banner + actions
        if (sectionKey === 'meal_cards' || sectionKey === 'meal_compact' || sectionKey === 'mom_meals') {
          const data = config.dataKey ? planData[config.dataKey] : null;
          return <Component key={sectionKey} data={data} planData={planData} planDate={planDate} onPlanUpdate={onPlanUpdate} />;
        }

        // Grocery section needs profile for shopping day
        if (sectionKey === 'grocery') {
          return <Component key={sectionKey} profileData={profileData} />;
        }

        // Housework — hide for full_maid, pass profileData
        if (sectionKey === 'housework') {
          if (profileData?.home_help_type === 'full_maid') return null;
          return <Component key={sectionKey} profileData={profileData} />;
        }

        // Kids activities fetches its own data
        if (sectionKey === 'kids_activities') {
          return <Component key={sectionKey} />;
        }

        // Standard sections
        const data = config.dataKey ? planData[config.dataKey] : null;
        return <Component key={sectionKey} data={data} />;
      })}
    </>
  );
}
