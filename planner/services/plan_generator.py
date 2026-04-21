import json
import logging
from datetime import date, datetime, timedelta

from django.conf import settings
from django.utils import timezone
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import CustomSectionList, CustomSectionTask, DayPlan, HouseworkList, HouseworkTask, HouseworkTemplate, MealPlan, PlanBlock, Reminder
from .ai_context import AIContextAssembler

logger = logging.getLogger(__name__)

# ─── User-type-specific JSON templates for the AI ─────────────────

PROFESSIONAL_JSON = """{
  "user_type": "professional",
  "deep_work": {
    "title": "Main focus task for today",
    "start": "09:00",
    "end": "12:00",
    "description": "What to focus on"
  },
  "priorities": [
    {"number": 1, "title": "Task name", "notes": "Brief note", "urgency": "today", "done": false},
    {"number": 2, "title": "Task name", "notes": "Brief note", "urgency": "this-week", "done": false},
    {"number": 3, "title": "Task name", "notes": "Brief note", "urgency": "someday", "done": false}
  ],
  "meetings": [
    {"time": "14:00", "title": "Meeting name", "duration": "45 mins", "platform": "Zoom", "note": "Prepare slides"}
  ],
  "meals": {
    "breakfast": {"name": "Meal name", "prep_mins": 10, "ingredients": ["ingredient 1", "ingredient 2"]},
    "lunch":     {"name": "Meal name", "prep_mins": 5, "ingredients": ["ingredient 1", "ingredient 2"]},
    "dinner":    {"name": "Meal name", "prep_mins": 25, "ingredients": ["ingredient 1", "ingredient 2"]}
  },
  "exercise": {"activity": "Gym", "time": "18:00", "duration": "45 mins"},
  "end_of_day": "18:00",
  "notes": "Any important note for today",
  "quick_chips": ["Specific action chip 1", "Specific action chip 2", "Specific action chip 3"]
}"""

HOMEMAKER_JSON = """{
  "user_type": "homemaker",
  "meals": {
    "breakfast": {"name": "Meal name", "prep_mins": 20, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},
    "lunch":     {"name": "Meal name", "prep_mins": 35, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},
    "dinner":    {"name": "Meal name", "prep_mins": 40, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},
    "snacks":    ["Snack item 1", "Snack item 2"]
  },
  "class_alerts": [
    {"child": "Child name", "class": "Class name", "time": "17:00", "leave_by": "16:30", "location": "Place"}
  ],
  "kids_activities": [
    {"child": "Child name", "age": 3, "activity": "Activity name", "duration": "40 mins", "materials": ["item1", "item2"], "description": "What to do"}
  ],
  "grocery_list": {
    "Vegetables": ["Onion", "Tomato"],
    "Dairy": ["Milk", "Curd"],
    "Meat": ["Chicken 1kg"]
  },
  "housework": ["Task 1", "Task 2"],
  "selfcare": {"activity": "Reading", "time": "14:00", "duration": "30 mins"},
  "notes": "Any note for the day",
  "quick_chips": ["Specific action chip 1", "Specific action chip 2", "Specific action chip 3"]
}"""

WORKING_MOM_JSON = """{
  "user_type": "working_mom",
  "work_schedule": {
    "start": "09:00",
    "end": "17:00",
    "type": "office/remote/hybrid",
    "commute_mins": 30
  },
  "class_alerts": [
    {"child": "Child name", "class": "Class name", "time": "17:00", "leave_by": "16:30"}
  ],
  "meals": {
    "breakfast": {"name": "Meal name", "prep_mins": 10, "description": "Quick description", "ingredients": ["ingredient 1", "ingredient 2"]},
    "lunch":     {"name": "Meal name", "prep_mins": 5, "description": "Packed or ordered", "ingredients": ["ingredient 1", "ingredient 2"]},
    "dinner":    {"name": "Meal name", "prep_mins": 30, "description": "Quick description", "ingredients": ["ingredient 1", "ingredient 2"]},
    "snacks":    ["Snack 1", "Snack 2"]
  },
  "kids_activities": [
    {"child": "Child name", "age": 3, "activity": "Activity name", "duration": "30 mins", "when": "after school", "materials": ["item1"]}
  ],
  "priorities": [
    {"number": 1, "title": "Task name", "notes": "Brief note", "urgency": "today", "done": false}
  ],
  "evening_routine": {
    "start": "18:00",
    "tasks": ["Pick up kids", "Dinner prep", "Bath time", "Bedtime story"]
  },
  "selfcare": {"activity": "Reading", "time": "21:00", "duration": "30 mins"},
  "grocery_list": {
    "Vegetables": ["Onion", "Tomato"],
    "Dairy": ["Milk"]
  },
  "notes": "Any note for the day",
  "quick_chips": ["Specific action chip 1", "Specific action chip 2", "Specific action chip 3"]
}"""

NEW_MOM_JSON = """{
  "user_type": "new_mom",
  "morning_greeting": "1-2 sentence warm personalised greeting for the mom based on her situation",
  "meal_health_banner": "A warm one-line note about recovery nutrition — never about weight or aesthetics",
  "meals": {
    "breakfast": {"name": "Meal name", "prep_mins": 5, "description": "One-hand friendly recipe", "ingredients": ["ingredient 1", "ingredient 2"]},
    "lunch":     {"name": "Meal name", "prep_mins": 10, "description": "Quick and nutritious", "ingredients": ["ingredient 1", "ingredient 2"]},
    "dinner":    {"name": "Meal name", "prep_mins": 20, "description": "Prep during nap time", "ingredients": ["ingredient 1", "ingredient 2"]},
    "snacks":    ["Snack 1", "Snack 2", "Snack 3"]
  },
  "exercise": {"activity": "Activity name", "time": "10:00", "duration": "15 mins", "note": "Encouraging note about recovery"},
  "selfcare": [
    {"time": "08:30", "activity": "Quick shower", "duration": "10 mins"},
    {"time": "14:00", "activity": "Cup of tea & read", "duration": "15 mins"}
  ],
  "housework": ["Task 1"],
  "essentials_check": ["Nappies", "Wipes", "Formula/milk bags", "Clean bottles"],
  "grocery_list": {
    "Vegetables": ["Spinach", "Tomato"],
    "Dairy": ["Milk", "Curd"]
  },
  "notes": "Gentle encouragement note — frame around recovery and strength, never guilt",
  "quick_chips": ["Specific action chip 1", "Specific action chip 2", "Specific action chip 3"]
}"""

JSON_TEMPLATES = {
    'professional': PROFESSIONAL_JSON,
    'working_mom': WORKING_MOM_JSON,
    'new_mom': NEW_MOM_JSON,
    'parent': HOMEMAKER_JSON,
    'homemaker': HOMEMAKER_JSON,
}


class PlanGenerator:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=8192,
            transport='rest',
        )

    # ------------------------------------------------------------------
    # Weekly meal generation — generates 7 days of meals in one AI call
    # ------------------------------------------------------------------
    @staticmethod
    def _meals_are_complete(meals):
        """True when breakfast, lunch, and dinner all have a non-empty name."""
        if not isinstance(meals, dict):
            return False
        for mt in ('breakfast', 'lunch', 'dinner'):
            m = meals.get(mt)
            if not isinstance(m, dict):
                return False
            if not (m.get('name') or '').strip():
                return False
        return True

    def generate_weekly_meals(self, profile, start_date=None, num_days=7):
        """Generate meals for multiple days in one AI call.
        Returns list of DayPlan objects created/updated.
        """
        if start_date is None:
            start_date = date.today()

        assembler = AIContextAssembler(profile)
        user_type = profile.user_type

        # Collect last week's meals to avoid repetition
        last_week_meals = self._get_last_week_meals(profile, start_date)

        # Collect favourites
        favourites = list(
            profile.favourite_meals.values_list('meal_name', flat=True)[:15]
        )

        # Build the weekly meals prompt
        context = assembler.build_plan_generation_context(start_date)
        user_message = self._build_weekly_meals_request(
            profile, start_date, num_days, last_week_meals, favourites
        )

        messages = [
            SystemMessage(content=context['system_prompt']),
            HumanMessage(content=user_message),
        ]

        logger.info(f'Weekly meals: requesting {num_days} days from {start_date}')
        try:
            response = self.llm.invoke(messages)
            raw_content = response.content
            weekly_data = self._parse_response(raw_content)

            if not isinstance(weekly_data, dict) or 'days' not in weekly_data:
                logger.error('Weekly meals response missing "days" key')
                return []

            created_plans = []
            skipped = 0
            for day_data in weekly_data.get('days', []):
                day_date_str = day_data.get('date', '')
                try:
                    day_date = datetime.strptime(day_date_str, '%Y-%m-%d').date()
                except (ValueError, TypeError):
                    continue

                # Skip days whose meals came back incomplete — leave them
                # unplanned so the next ensure_meals_ahead call retries, rather
                # than poison the DayPlan with a ready-but-empty meals dict.
                day_meals = day_data.get('meals') or {}
                if not self._meals_are_complete(day_meals):
                    logger.warning(f'Weekly meals: skipping {day_date_str} — incomplete meals from AI')
                    skipped += 1
                    continue

                # Create or update day plan
                day_plan, _ = DayPlan.objects.update_or_create(
                    profile=profile,
                    date=day_date,
                    defaults={'status': DayPlan.Status.GENERATING},
                )

                # Build plan_data — merge meals into existing plan_data or create new
                plan_data = day_plan.plan_data or {}
                plan_data['user_type'] = user_type
                plan_data['date'] = day_date_str

                # Store meals
                meals_key = 'mom_meals' if user_type == 'new_mom' else 'meals'
                plan_data[meals_key] = day_meals

                # Store health banner
                if day_data.get('meal_health_banner'):
                    plan_data['meal_health_banner'] = day_data['meal_health_banner']

                day_plan.plan_data = plan_data
                day_plan.raw_ai_response = raw_content
                day_plan.status = DayPlan.Status.READY
                day_plan.save()

                # Save MealPlan records
                self._save_meals_from_plan_data(day_plan, plan_data)
                created_plans.append(day_plan)

            logger.info(f'Weekly meals: saved {len(created_plans)} days, skipped {skipped}')
            return created_plans

        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse weekly meals JSON: {e}')
            return []
        except Exception as e:
            logger.error(f'Weekly meal generation failed: {e}')
            return []

    def ensure_meals_ahead(self, profile, min_days=3, total_days=7):
        """Auto-fill: if fewer than min_days have COMPLETE meals planned, generate more.
        A DayPlan with status=ready but empty/partial meals counts as unplanned
        so we retry instead of leaving the user with blank meal cards.
        """
        today = date.today()
        window_end = today + timedelta(days=total_days - 1)
        ready_plans = DayPlan.objects.filter(
            profile=profile,
            date__gte=today,
            date__lte=window_end,
            status='ready',
        )
        meals_key_for = lambda ut: 'mom_meals' if ut == 'new_mom' else 'meals'
        ready_dates = {
            p.date for p in ready_plans
            if self._meals_are_complete(
                (p.plan_data or {}).get(meals_key_for(p.plan_data.get('user_type') if p.plan_data else profile.user_type), {})
            )
        }
        planned_count = len(ready_dates)

        if planned_count < min_days:
            # First day in the window that isn't already planned-with-meals
            start = today
            for i in range(total_days):
                d = today + timedelta(days=i)
                if d not in ready_dates:
                    start = d
                    break

            days_needed = total_days - planned_count
            logger.info(f'ensure_meals_ahead: {planned_count}/{total_days} complete — generating {days_needed} from {start}')
            return self.generate_weekly_meals(profile, start, days_needed)
        return []

    def _get_last_week_meals(self, profile, reference_date):
        """Get last 7 days of meals to avoid repetition."""
        week_ago = reference_date - timedelta(days=7)
        plans = DayPlan.objects.filter(
            profile=profile,
            date__gte=week_ago,
            date__lt=reference_date,
            status='ready',
        ).order_by('date')

        meals = []
        for plan in plans:
            pd = plan.plan_data or {}
            meals_data = pd.get('meals') or pd.get('mom_meals') or {}
            day_meals = []
            for mt in ['breakfast', 'lunch', 'dinner']:
                m = meals_data.get(mt)
                if isinstance(m, dict) and m.get('name'):
                    day_meals.append(f"{mt}: {m['name']}")
            if day_meals:
                meals.append(f"{plan.date.strftime('%A')}: {', '.join(day_meals)}")
        return meals

    def _build_weekly_meals_request(self, profile, start_date, num_days, last_week_meals, favourites):
        wake = profile.wake_time.strftime('%H:%M')
        sleep = profile.sleep_time.strftime('%H:%M')

        # Build day list
        days_list = []
        for i in range(num_days):
            d = start_date + timedelta(days=i)
            days_list.append(f"{d.strftime('%A')} ({d.strftime('%Y-%m-%d')})")
        days_str = ', '.join(days_list)

        # Last week context
        last_week_text = ''
        if last_week_meals:
            last_week_text = (
                "\n## Last Week's Meals (DO NOT repeat the same pattern)\n"
                "Mix and match — vary the meals. Don't copy last week.\n"
            )
            for m in last_week_meals:
                last_week_text += f"- {m}\n"

        # Favourites context
        fav_text = ''
        if favourites:
            fav_text = (
                "\n## User's Favourite Meals (include some of these, rotated across the week)\n"
                f"{', '.join(favourites)}\n"
            )

        return (
            f"Generate meals for {num_days} days: {days_str}\n"
            f"Plan meals between {wake} and {sleep}.\n\n"
            f"{last_week_text}"
            f"{fav_text}\n"
            "Rules:\n"
            "- VARIETY is critical — different breakfast each day, different lunch each day, different dinner each day\n"
            "- Mix cuisines within the user's preferences — don't serve the same cuisine for all 7 days\n"
            "- Use my food preferences AND cuisine preferences\n"
            "- If I have health conditions, EVERY meal must respect them\n"
            f"- I cook for {profile.family_size} people — family-friendly AND healthy for me\n"
            "- EVERY meal must be balanced: protein + carbs + healthy fats + fiber\n"
            "- Make meals SPECIFIC — real dish names, not generic labels\n"
            "- ALWAYS use English names for dishes. If the dish has a local name, write the English translation. e.g. 'Red Lentil Soup' not 'Mercimek Çorbası', 'Scrambled Eggs with Vegetables' not 'Menemen'\n"
            "- Each day gets a different meal_health_banner (warm, caring, under 20 words)\n"
            "  If NO health conditions, set banner to empty string\n"
            "- Keep ALL descriptions under 15 words\n\n"
            "Return ONLY a JSON object with this structure:\n"
            "{\n"
            '  "days": [\n'
            "    {\n"
            '      "date": "YYYY-MM-DD",\n'
            '      "meal_health_banner": "Warm caring line about today\'s meals",\n'
            '      "meals": {\n'
            '        "breakfast": {"name": "Dish name", "prep_mins": 15, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},\n'
            '        "lunch": {"name": "Dish name", "prep_mins": 30, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},\n'
            '        "dinner": {"name": "Dish name", "prep_mins": 30, "description": "Brief recipe", "ingredients": ["ingredient 1", "ingredient 2"]},\n'
            '        "snacks": ["Snack 1", "Snack 2"]\n'
            "      }\n"
            "    }\n"
            "  ]\n"
            "}\n"
            "Return ONLY valid JSON, no other text.\n"
        )

    # ------------------------------------------------------------------
    # Daily plan generation — for non-meal sections (housework, etc.)
    # ------------------------------------------------------------------
    def generate_day_plan(self, profile, target_date=None):
        """Generate a user-type-specific day plan.
        If weekly meals already exist for this date, preserves them.
        """
        if target_date is None:
            target_date = date.today()

        # Check if meals already exist from weekly generation
        existing = DayPlan.objects.filter(profile=profile, date=target_date).first()
        existing_meals = None
        if existing and existing.plan_data:
            pd = existing.plan_data
            existing_meals = pd.get('meals') or pd.get('mom_meals')

        if existing:
            existing.delete()

        # Delete old housework list so fresh tasks are generated
        HouseworkList.objects.filter(profile=profile, date=target_date).delete()
        # Delete old custom section lists too
        CustomSectionList.objects.filter(profile=profile, date=target_date).delete()

        day_plan = DayPlan.objects.create(
            profile=profile,
            date=target_date,
            status=DayPlan.Status.GENERATING,
        )

        try:
            assembler = AIContextAssembler(profile)
            context = assembler.build_plan_generation_context(target_date)

            # Build user-type-specific prompt
            user_type = profile.user_type
            json_template = JSON_TEMPLATES.get(user_type, HOMEMAKER_JSON)

            # Detect custom sections from user's layout
            custom_sections = self._get_custom_sections(profile)

            user_message = self._build_request(profile, target_date, json_template, custom_sections)

            messages = [
                SystemMessage(content=context['system_prompt']),
                HumanMessage(content=user_message),
            ]

            response = self.llm.invoke(messages)
            raw_content = response.content
            day_plan.raw_ai_response = raw_content

            parsed = self._parse_response(raw_content)

            # Store the full structured JSON for the frontend
            parsed['date'] = str(target_date)
            parsed['user_type'] = user_type

            # Preserve weekly meals only if they're actually usable. A truthy
            # but incomplete existing_meals dict (e.g. all-null values) would
            # otherwise wipe out the day-plan AI's valid meals.
            meals_key = 'mom_meals' if user_type == 'new_mom' else 'meals'
            if self._meals_are_complete(existing_meals):
                parsed[meals_key] = existing_meals
                logger.info(f'Day plan {target_date}: using weekly meals')
            elif not self._meals_are_complete(parsed.get(meals_key)):
                logger.warning(f'Day plan {target_date}: both weekly and day-plan meals missing/incomplete')

            day_plan.plan_data = parsed

            # Also save normalized records for backwards compatibility
            self._save_meals_from_plan_data(day_plan, parsed)

            # Save housework records if included in the plan
            if parsed.get('housework'):
                self._save_housework_from_plan_data(profile, target_date, parsed)

            # Save custom section records
            if custom_sections:
                self._save_custom_sections_from_plan_data(profile, target_date, parsed, custom_sections)

            day_plan.status = DayPlan.Status.READY
            day_plan.save()

        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse AI response as JSON: {e}')
            day_plan.status = DayPlan.Status.FAILED
            day_plan.save()

        except Exception as e:
            logger.error(f'Plan generation failed: {e}')
            day_plan.raw_ai_response = str(e)
            day_plan.status = DayPlan.Status.FAILED
            day_plan.save()

        return day_plan

    def _get_custom_sections(self, profile):
        """Extract custom (user-added) sections from the user's layout."""
        from .ai_context import AIContextAssembler
        layout = profile.custom_layout or []
        known_keys = set(SECTION_REGISTRY.keys()) if 'SECTION_REGISTRY' in dir() else set()

        # Import the registry to check known keys
        try:
            from ..section_registry import SECTION_REGISTRY as reg
            known_keys = set(reg.keys())
        except ImportError:
            known_keys = set()

        custom = []
        for item in layout:
            if item.get('visible') is False:
                continue
            key = item.get('key', '')
            if key and key not in known_keys and (item.get('custom_label') or item.get('added_by_user')):
                label = item.get('custom_label', key.replace('_', ' '))
                custom.append({'key': key, 'label': label})
        return custom

    def _build_request(self, profile, target_date, json_template, custom_sections=None):
        day_name = target_date.strftime('%A')
        date_str = target_date.strftime('%B %d, %Y')
        wake = profile.wake_time.strftime('%H:%M')
        sleep = profile.sleep_time.strftime('%H:%M')

        # Build housework-specific instructions for user types that have it
        housework_rules = ''
        if profile.user_type in ('homemaker', 'parent', 'working_mom', 'new_mom'):
            template_names = self._get_template_tasks(profile, target_date)

            if profile.user_type == 'new_mom':
                housework_rules = self._new_mom_housework_rules(profile, template_names)
            else:
                weekday = target_date.weekday()
                is_weekend = weekday >= 5

                if profile.user_type == 'working_mom':
                    target_total = 4 if not is_weekend else 6
                else:
                    target_total = 6 if not is_weekend else 8

                ai_count = max(1, target_total - len(template_names))

                housework_rules = (
                    f"\nHousework rules:\n"
                    f"- Generate EXACTLY {ai_count} housework tasks in the 'housework' array\n"
                    f"- Short task names (2-4 words), action-based\n"
                    f"- e.g. 'Vacuum and mop', 'Do laundry', 'Wash dishes', 'Dust furniture'\n"
                    f"- Do NOT specify rooms — say 'Vacuum and mop' NOT 'Vacuum living room'\n"
                    f"- Vary tasks day to day\n"
                )

                if template_names:
                    housework_rules += (
                        f"- These recurring tasks are already scheduled: {', '.join(template_names)}\n"
                        f"- Do NOT include any of those in the housework array — generate DIFFERENT tasks\n"
                    )

                if profile.home_help_type == 'partial_help':
                    housework_rules += (
                        f"- This user has part-time domestic help — frame tasks as clear instructions for a helper\n"
                    )

        return (
            f"Generate my complete day plan for {day_name}, {date_str}.\n"
            f"Plan from {wake} to {sleep}.\n\n"
            f"Return a JSON object with EXACTLY this structure:\n"
            f"{json_template}\n\n"
            "Rules:\n"
            "- Fill in real, specific, personalised content based on my profile\n"
            "- Use my food preferences AND cuisine preferences for meal suggestions\n"
            "- If I have health conditions or dietary goals, EVERY meal must respect them:\n"
            "  * Use ingredients that are beneficial for my conditions\n"
            "  * Avoid ingredients that are harmful for my conditions\n"
            "  * Suggest real, named dishes from my preferred cuisine that fit my health needs\n"
            "  * Example: Kerala cuisine + PCOS → brown rice puttu, avial with coconut oil, fish molee (not generic 'healthy curry')\n"
            f"- I cook for {profile.family_size} people — meals should be family-friendly AND healthy for me\n"
            "- Use my schedule events for meetings/classes\n"
            "- Use my children's info for kids activities\n"
            "- Only include sections that are relevant — if I have no meetings, return an empty meetings array\n"
            "- If I have no kids, omit class_alerts and kids_activities\n"
            "- Make meals SPECIFIC — name the actual dish, not generic labels like 'healthy breakfast' or 'protein-rich lunch'\n"
            "- ALWAYS use English names for dishes. If the dish has a local name, write the English translation. e.g. 'Red Lentil Soup' not 'Mercimek Çorbası'\n"
            "- EVERY meal must be nutritionally balanced — include ALL four:\n"
            "  * Protein: eggs, lentils, chicken, fish, paneer, curd, chickpeas, etc.\n"
            "  * Carbs: rice, roti, oats, millet, bread, dosa, etc.\n"
            "  * Healthy fats: coconut oil, ghee, nuts, avocado, seeds, etc.\n"
            "  * Fiber: vegetables, salad, thoran, beans, whole grains, fruits, etc.\n"
            "  * Even breakfast — never suggest just toast or fruit alone. Always include protein, fat, and fiber.\n"
            "  * Example: 'Puttu with kadala curry, coconut, and thoran' → carbs (puttu) + protein (kadala) + fat (coconut) + fiber (thoran)\n"
            "- meal_health_banner: If the user has health conditions, write ONE warm, caring line (under 20 words) about why today's meals are tailored for them.\n"
            "  * Mention the condition and family naturally. Sound like a caring friend, not a doctor.\n"
            "  * Example: 'Today's meals are gentle on your PCOS — low GI, anti-inflammatory, and your family will love them too'\n"
            "  * Example: 'Packed with protein and iron today — exactly what your body needs, and tasty for the whole family'\n"
            "  * If NO health conditions, set meal_health_banner to empty string ''\n"
            "- Make activities specific and age-appropriate\n"
            "- Keep priorities actionable and realistic\n"
            "- Keep ALL descriptions under 15 words — be concise\n"
            f"{housework_rules}"
            "- quick_chips: Generate exactly 3 short action phrases the user might ask their AI assistant today.\n"
            "  * Based on what's actually in the plan (specific meals, events, kids, tasks)\n"
            "  * e.g. 'Swap dinner to something lighter', 'Add milk to groceries', 'Skip Arya\\'s football today'\n"
            "  * Make them specific to today's plan, not generic\n"
            f"{self._build_custom_sections_prompt(custom_sections)}"
            "- Return ONLY valid JSON, no other text\n"
        )

    def _new_mom_housework_rules(self, profile, template_names):
        """Postpartum-safe housework rules scaled to the mom's recovery stage.

        Replaces the generic housework prompt for new_mom user type so the AI
        doesn't hand a week-3-postpartum mom tasks like vacuuming or mopping.
        If she has a part-time helper, heavy tasks are allowed (framed as
        helper instructions) because she isn't the one doing them.
        """
        from .ai_context import build_new_mom_context
        ctx = build_new_mom_context(profile)
        weeks = ctx['weeks_postpartum']
        had_csection = ctx['had_csection']
        solo = ctx['support_type'] == 'flying_solo'

        # Part-time helper case: tasks are for the helper, so heavy tasks are fine
        if profile.home_help_type == 'partial_help':
            count = 1 if solo else 2
            ai_count = max(1, count - len(template_names))
            rules = (
                f"\nHousework rules (new mom with part-time helper):\n"
                f"- Generate EXACTLY {ai_count} task(s) framed as instructions for her helper\n"
                f"- Heavy tasks OK since the helper does them (vacuum, laundry, dishes, etc.)\n"
                f"- Short task names (2-4 words), action-based\n"
                f"- Do NOT specify rooms — say 'Vacuum and mop' NOT 'Vacuum living room'\n"
                f"- Vary tasks day to day\n"
            )
            if template_names:
                rules += (
                    f"- Already scheduled: {', '.join(template_names)} — pick DIFFERENT tasks\n"
                )
            return rules

        # Stage 1: weeks 0-2 — immediate recovery, no housework
        if weeks <= 2:
            return (
                f"\nHousework rules (new mom, {weeks} weeks postpartum"
                f"{', post C-section' if had_csection else ''} — immediate recovery):\n"
                "- Return an EMPTY 'housework' array: []\n"
                "- She needs rest. No household tasks. Focus on baby, meals, and healing.\n"
            )

        # Shared: forbidden + safe lists for recovering moms (no helper)
        forbidden = (
            "- NEVER suggest: vacuuming, mopping, sweeping, washing dishes at the sink,\n"
            "  scrubbing, cleaning bathrooms or toilets, carrying laundry baskets,\n"
            "  deep cleaning, changing bedsheets, lifting heavier than the baby,\n"
            "  prolonged standing, deep bending, reaching overhead.\n"
        )
        safe_examples = (
            "- ONLY suggest light, seated-or-short-standing micro-tasks like:\n"
            "  'Fold baby clothes' (sitting), 'Rinse bottles', 'Wipe changing table',\n"
            "  'Tidy play mat area', 'Sort mail', 'Quick counter wipe', 'Put 5 items away'.\n"
        )

        # Stage 2: weeks 2-6 (or <12 if C-section) — early recovery, one micro-task
        early_recovery = weeks <= 6 or (had_csection and weeks < 12)
        if early_recovery:
            header = (
                f"\nHousework rules (new mom, {weeks} weeks postpartum"
                f"{', post C-section' if had_csection else ''} — early recovery):\n"
                "- Generate EXACTLY 1 housework task.\n"
                "- Under 5 minutes, seated or very short standing.\n"
            )
        else:
            # Stage 3: weeks 6+ (vaginal) / 12+ (C-section) — light tasks only
            count = 1 if solo else 2
            header = (
                f"\nHousework rules (new mom, {weeks} weeks postpartum):\n"
                f"- Generate EXACTLY {count} housework task(s).\n"
                "- Each task under 10 minutes and light. Still avoid heavy cleaning.\n"
            )

        solo_note = ''
        if solo:
            solo_note = (
                "- She is flying solo — tasks must be doable while baby is on the\n"
                "  play mat in view. No leaving the room.\n"
            )

        template_note = ''
        if template_names:
            template_note = (
                f"- Already scheduled: {', '.join(template_names)} — pick DIFFERENT micro-tasks.\n"
            )

        return header + forbidden + safe_examples + solo_note + template_note

    def _build_custom_sections_prompt(self, custom_sections):
        """Build prompt instructions for user-added custom sections."""
        if not custom_sections:
            return ''

        lines = ["\n- The user has added CUSTOM sections to their dashboard. For EACH one, generate content:\n"]
        for cs in custom_sections:
            key = cs['key']
            label = cs['label']
            lines.append(
                f'  * "{key}": Generate a JSON object for "{label}" with this structure:\n'
                f'    {{"title": "{label}", "items": ["actionable item 1", "actionable item 2", "actionable item 3"], '
                f'"tip": "A short helpful tip related to {label}"}}\n'
                f'    Make items specific and personalised to the user\'s profile and today\'s context.\n'
            )
        lines.append("  * Add each custom section as a top-level key in the JSON response.\n")
        return ''.join(lines)

    def _parse_response(self, raw_content):
        content = raw_content.strip()
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        return json.loads(content)

    def _save_meals_from_plan_data(self, day_plan, data):
        """Extract meals from the plan_data and save as MealPlan records."""
        meals_data = data.get('meals', {})
        if not isinstance(meals_data, dict):
            return

        for meal_type in ['breakfast', 'lunch', 'dinner']:
            meal = meals_data.get(meal_type)
            if meal and isinstance(meal, dict):
                MealPlan.objects.create(
                    day_plan=day_plan,
                    meal_type=meal_type,
                    name=meal.get('name', ''),
                    description=meal.get('description', ''),
                    prep_time_minutes=meal.get('prep_mins', 0),
                    ingredients=meal.get('ingredients', []),
                )

        # Save snacks if present
        snacks = meals_data.get('snacks')
        if snacks and isinstance(snacks, list):
            MealPlan.objects.create(
                day_plan=day_plan,
                meal_type='snack',
                name=', '.join(snacks),
                description='',
                prep_time_minutes=0,
            )

    # ------------------------------------------------------------------
    # Housework — extract from plan data and save as HouseworkList/Task
    # ------------------------------------------------------------------
    def _get_template_tasks(self, profile, target_date):
        """Return recurring template task names that match this weekday."""
        weekday = target_date.weekday()  # 0=Mon … 6=Sun
        templates = HouseworkTemplate.objects.filter(
            profile=profile,
            is_active=True,
        )
        names = []
        for t in templates:
            if not t.days or weekday in t.days:
                names.append(t.name)
        return names

    def _save_housework_from_plan_data(self, profile, target_date, plan_data):
        """Create HouseworkList + HouseworkTask records from plan_data['housework']."""
        # Idempotent — skip if already exists
        if HouseworkList.objects.filter(profile=profile, date=target_date).exists():
            return

        hw_list = HouseworkList.objects.create(
            profile=profile,
            date=target_date,
        )

        # Add recurring template tasks
        template_names = self._get_template_tasks(profile, target_date)
        for name in template_names:
            HouseworkTask.objects.create(housework_list=hw_list, name=name)

        # Add AI-generated tasks, skipping duplicates with templates
        template_lower = [n.lower() for n in template_names]
        for task_name in plan_data.get('housework', []):
            if isinstance(task_name, str) and task_name.strip():
                if task_name.strip().lower() not in template_lower:
                    HouseworkTask.objects.create(
                        housework_list=hw_list,
                        name=task_name.strip(),
                    )

    def _save_custom_sections_from_plan_data(self, profile, target_date, plan_data, custom_sections):
        """Create CustomSectionList + CustomSectionTask records for each custom section."""
        for cs in custom_sections:
            key = cs['key']
            section_data = plan_data.get(key)
            if not isinstance(section_data, dict):
                continue

            # Idempotent
            if CustomSectionList.objects.filter(profile=profile, section_key=key, date=target_date).exists():
                continue

            cs_list = CustomSectionList.objects.create(
                profile=profile, section_key=key, date=target_date,
            )

            for item in section_data.get('items', []):
                if isinstance(item, str) and item.strip():
                    CustomSectionTask.objects.create(
                        section_list=cs_list, name=item.strip(),
                    )
