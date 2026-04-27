from datetime import date, timedelta
import math


def build_new_mom_context(profile):
    """Build context dict for new mom users. Safe fallbacks for day 1."""
    baby_name = profile.baby_name or 'Baby'
    weeks_postpartum = 0
    if profile.baby_date_of_birth:
        days = (date.today() - profile.baby_date_of_birth).days
        weeks_postpartum = max(0, days // 7)

    # Check essentials unchecked for 2+ consecutive days
    from ..models import EssentialsCheck
    essentials_low = []
    yesterday = date.today() - timedelta(days=1)
    day_before = date.today() - timedelta(days=2)
    yesterday_unchecked = set(
        EssentialsCheck.objects.filter(
            profile=profile, date=yesterday, is_checked=False,
        ).values_list('item', flat=True)
    )
    day_before_unchecked = set(
        EssentialsCheck.objects.filter(
            profile=profile, date=day_before, is_checked=False,
        ).values_list('item', flat=True)
    )
    essentials_low = list(yesterday_unchecked & day_before_unchecked)

    return {
        'baby_name': baby_name,
        'weeks_postpartum': weeks_postpartum,
        'is_breastfeeding': profile.is_breastfeeding,
        'had_csection': profile.had_csection,
        'support_type': profile.support_type or 'flying_solo',
        'essentials_low': essentials_low,
    }


class AIContextAssembler:
    """
    Builds the system prompt and user message for Claude API calls
    based on the user's profile type and related data.
    """

    def __init__(self, profile):
        self.profile = profile

    def build_plan_generation_context(self, target_date):
        """Returns dict with system_prompt and user_message for day plan generation."""
        sections = [
            self._base_profile_section(),
            self._preferences_section(),
            self._schedule_section(target_date),
        ]

        if self.profile.user_type in ('parent', 'new_mom', 'working_mom'):
            sections.append(self._children_section())

        if self.profile.user_type == 'new_mom':
            sections.append(self._new_mom_section())

        if self.profile.works_outside_home:
            sections.append(self._work_section(target_date))

        fav_section = self._favourites_section()
        if fav_section:
            sections.append(fav_section)

        swap_section = self._swap_patterns_section()
        if swap_section:
            sections.append(swap_section)

        hw_history = self._housework_history_section()
        if hw_history:
            sections.append(hw_history)

        cs_history = self._custom_section_history_section()
        if cs_history:
            sections.append(cs_history)

        system_prompt = self._assemble_system_prompt(sections)
        user_message = self._build_plan_request(target_date)
        return {'system_prompt': system_prompt, 'user_message': user_message}

    def build_chat_context(self):
        """Full context for chat — profile, preferences, today's + tomorrow's plan, schedule, grocery, housework."""
        target_date = date.today()
        tomorrow = target_date + timedelta(days=1)
        sections = [
            self._base_profile_section(),
            self._preferences_section(),
            self._schedule_section(target_date),
            self._day_plan_section(target_date, "Today"),
            self._day_plan_section(tomorrow, "Tomorrow"),
            self._active_grocery_section(),
            self._todays_housework_section(target_date),
        ]

        if self.profile.user_type in ('parent', 'new_mom', 'working_mom'):
            sections.append(self._children_section())

        today_str = target_date.strftime('%Y-%m-%d')
        tomorrow_str = (target_date + timedelta(days=1)).strftime('%Y-%m-%d')
        display_name = self.profile.display_name or 'there'

        header = (
            "You are Dayo — %s's personal day planner and trusted friend. "
            "You know their schedule, meals, kids, grocery list, and daily plan inside out.\n\n"

            "## Your personality\n"
            "- Talk like a warm, caring friend — not an assistant or a robot\n"
            "- Be empathetic. If someone says their child is sick, show you care first, then help\n"
            "- Use their name and their children's names naturally\n"
            "- Reference SPECIFIC details from their actual plan: real meal names, real event times, "
            "real child activities — never generic placeholders\n"
            "- Keep responses concise (2-4 sentences usually). Don't over-explain\n"
            "- Be proactive — if you notice something helpful, suggest it\n"
            "- Add a human touch: 'That sounds lovely', 'Oh no, hope she feels better', "
            "'Good call — I'll sort that out'\n"
            "- When suggesting something (like a me-time activity), briefly explain WHY it helps\n"
            "- Never say 'I am an AI' or 'As an AI assistant'\n\n"

            "## How to handle actions\n"
            "- When the user asks to DO something, use the right tool immediately — don't ask unnecessary "
            "confirmation questions. Just explain what you're doing and call the tool.\n"
            "- NEVER claim you did an action ('I added X', 'I swapped Y', 'I cancelled Z', "
            "'I've put X on your list') unless you actually CALLED the tool in this turn. "
            "If you did not call a tool, do not pretend you did — instead ask for the missing "
            "detail or do nothing. Hallucinating actions is worse than asking a clarifying question.\n"
            "- Treat short follow-up replies (e.g. user just says 'mango' after you asked which "
            "fruit to add) as a continuation of the previous request — call the tool with that value, "
            "do not just reply in text.\n"
            "- When explaining an action, reference the REAL current data. "
            "e.g. 'I'll swap your lunch from Grilled Salmon to Butter Chicken' (not just 'I'll swap your lunch')\n"
            "- Call at most ONE tool per response. If multiple actions are needed, "
            "handle the most important first.\n"
            "- You are an expert in cooking, nutrition, and meal planning. "
            "When the user asks to swap meals or suggests a cuisine, use swap_meal "
            "with the preference — do NOT use web_search for recipes. Just swap directly.\n"
            "- When asked to change ALL meals, swap them one at a time: breakfast → lunch → dinner. "
            "Pick a great dish that fits their request — don't ask for options.\n"
            "- When the user mentions a day other than today for a meal swap "
            "(e.g. 'change tomorrow's lunch', 'swap Friday's dinner'), pass "
            "swap_meal's target_date in YYYY-MM-DD format. Default is today.\n"
            "- When the user wants to make kids' activities easier, harder, "
            "advanced, or olympiad/competition-level, call regenerate_kids_activities "
            "with the appropriate level. Pass child_name only if the user named a "
            "specific child; otherwise leave it empty to apply to all kids.\n"
            "- When adding schedule events, ALWAYS include event_date in YYYY-MM-DD format. "
            "Today is %s. Tomorrow is %s.\n\n"

            "## When someone shares something emotional\n"
            "- Lead with empathy, not action: 'Oh no, I'm sorry to hear that' before offering help\n"
            "- If a child is sick: acknowledge it warmly, then list what's on the schedule for that "
            "child today and offer to cancel/reschedule each one\n"
            "- If they're stressed: suggest a specific self-care activity and explain why it would help\n"
            "- If they ask about health/wellness: give thoughtful, specific advice based on their plan\n\n"

            "## Features you DON'T have tools for (guide the user instead)\n"
            "- Kids activity PDFs: Tell the user to go to the Kids Activities section on their "
            "dashboard and tap the download button on the activity card. You cannot generate or "
            "download PDFs directly.\n"
            "- Weekly meal plans: Tell them to go to Meals section and tap 'Upcoming meals'.\n"
            "- Profile changes: Tell them to go to the Profile page.\n\n"

            "## NEVER use web_search\n"
            "The web_search tool is not available yet. NEVER call it.\n"
            "You are an expert in cooking, nutrition, kids activities, crafts, fitness, and wellness. "
            "You already know thousands of recipes, DIY activities, craft ideas, workout routines, etc. "
            "When the user asks for a recipe (playdough, cookie, dinner), a craft idea, a workout, "
            "or any knowledge question — just ANSWER DIRECTLY from your own knowledge. "
            "Give them the full recipe or instructions right in the chat. "
            "Do not search the web. Do not say you need to search. Just answer.\n\n"
        ) % (display_name, today_str, tomorrow_str)
        return header + '\n'.join(filter(None, sections))

    def build_grocery_context(self, week_start):
        """Context for grocery list generation — profile + week's meal ingredients."""
        sections = [
            self._base_profile_section(),
            self._preferences_section(),
            self._weekly_meals_section(week_start),
        ]

        system_prompt = (
            "You are Dayo, a helpful personal AI assistant. "
            "You are generating a consolidated weekly grocery list.\n\n"
        ) + '\n'.join(sections)

        user_message = (
            f"Generate a grocery list for the week starting {week_start.strftime('%B %d, %Y')}.\n\n"
            "Return a JSON array of items with this structure:\n"
            "[\n"
            "  {\n"
            '    "name": "item name",\n'
            '    "quantity": "estimated quantity (e.g. 1 kg, 500 ml, 6 pieces)",\n'
            '    "category": "produce|dairy|grains|protein|spices|snacks|other"\n'
            "  }\n"
            "]\n\n"
            "Rules:\n"
            "- Consolidate duplicate ingredients across meals and estimate total quantity\n"
            "- Categorize every item\n"
            "- Include basic pantry staples if meals need them (oil, salt, etc.)\n"
            "- Keep quantities realistic for a family\n"
            "- Return ONLY valid JSON, no other text\n"
        )

        return {'system_prompt': system_prompt, 'user_message': user_message}

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    def _base_profile_section(self):
        return (
            "## About the User\n"
            f"- Name: {self.profile.display_name}\n"
            f"- Type: {self.profile.get_user_type_display()}\n"
            f"- Location: {self.profile.location_city or 'Not specified'}\n"
            f"- Timezone: {self.profile.timezone}\n"
        )

    def _preferences_section(self):
        dietary = ', '.join(self.profile.dietary_restrictions) if self.profile.dietary_restrictions else 'None'
        cuisine = ', '.join(self.profile.cuisine_preferences) if self.profile.cuisine_preferences else 'Any'
        custom = self.profile.custom_cuisines or ''
        if custom:
            cuisine += f', {custom}'

        health = ', '.join(self.profile.health_conditions) if self.profile.health_conditions else 'None'
        family_size = self.profile.family_size or 1

        # Meal-specific preferences
        bf_types = ', '.join(self.profile.breakfast_types) if self.profile.breakfast_types else 'Any'
        ln_types = ', '.join(self.profile.lunch_types) if self.profile.lunch_types else 'Any'
        dn_types = ', '.join(self.profile.dinner_types) if self.profile.dinner_types else 'Any'
        snacks = ', '.join(self.profile.snack_preferences) if self.profile.snack_preferences else 'Any'

        exclusions = ', '.join(self.profile.exclusions) if self.profile.exclusions else 'None'
        modules = ', '.join(self.profile.planning_modules) if self.profile.planning_modules else 'General planning'

        result = (
            "## Preferences\n"
            f"- Wake time: {self.profile.wake_time.strftime('%H:%M')}\n"
            f"- Sleep time: {self.profile.sleep_time.strftime('%H:%M')}\n"
            f"- Dietary restrictions: {dietary}\n"
            f"- Cuisine preferences: {cuisine}\n"
            f"- Health conditions / dietary goals: {health}\n"
            f"- Family size: {family_size} people (meals should be suitable for the whole family)\n"
            f"\n## Planning Focus Areas\n"
            f"The user wants their day plan to focus on: {modules}\n"
            f"Only include activities related to these areas. Do NOT plan activities outside these unless necessary.\n"
        )

        # Health-aware meal instructions
        if self.profile.health_conditions:
            conditions = ', '.join(self.profile.health_conditions)
            result += (
                f"\n## IMPORTANT — Health-Aware Meals\n"
                f"The user has: {conditions}.\n"
                f"Every meal MUST be adapted to these conditions. For example:\n"
                f"- PCOS → low glycemic, anti-inflammatory, avoid refined carbs/sugar\n"
                f"- Diabetes → low GI, controlled carbs, high fiber\n"
                f"- High protein diet → protein-rich ingredients in every meal\n"
                f"- Iron deficiency → iron-rich foods (spinach, lentils, meat)\n"
                f"- Thyroid → avoid goitrogens, include selenium/zinc-rich foods\n"
                f"- Cholesterol → low saturated fat, heart-healthy fats\n"
                f"Use your medical nutrition knowledge to adapt meals for {conditions}.\n"
                f"Meals must ALSO work for the whole family ({family_size} people) — "
                f"healthy for the user, enjoyable for everyone.\n"
            )

        # Only include meal preferences if meals module is active
        if self._has_module('meals'):
            result += (
                "\n## Meal Preferences\n"
                f"- Breakfast: {self.profile.breakfast_weight} meal — styles: {bf_types}\n"
                f"- Lunch: {self.profile.lunch_weight} meal — styles: {ln_types}\n"
                f"- Dinner: {self.profile.dinner_weight} meal — styles: {dn_types}\n"
                f"- Snacks: {snacks}\n"
            )

        # Include per-module preferences
        mod_prefs = self.profile.module_preferences or {}
        if mod_prefs:
            result += "\n## Module-Specific Preferences\n"
            for mod_key, prefs in mod_prefs.items():
                if isinstance(prefs, dict) and prefs:
                    result += f"\n### {mod_key.replace('_', ' ').title()}\n"
                    for pref_key, pref_val in prefs.items():
                        label = pref_key.replace('_', ' ').title()
                        if isinstance(pref_val, list):
                            result += f"- {label}: {', '.join(pref_val)}\n"
                        else:
                            result += f"- {label}: {pref_val}\n"

        result += (
            f"\n- Grocery shopping day: {self.profile.grocery_day or 'Monday'}\n"
            f"- Do NOT include in plan: {exclusions}\n"
            f"- Additional notes: {self.profile.notes or 'None'}\n"
        )
        return result

    def _has_module(self, module_key):
        """Check if user has a specific planning module enabled."""
        modules = self.profile.planning_modules or []
        return any(module_key.lower() in m.lower() for m in modules)

    def _new_mom_section(self):
        """Build comprehensive new mom context for AI prompts."""
        ctx = build_new_mom_context(self.profile)
        weeks = ctx['weeks_postpartum']
        support = ctx['support_type']
        solo = support == 'flying_solo'

        lines = [
            "## New Mom Context",
            f"- Baby: {ctx['baby_name']}, {weeks} weeks old",
            f"- Breastfeeding: {'Yes' if ctx['is_breastfeeding'] else 'No'}",
            f"- C-section: {'Yes' if ctx['had_csection'] else 'No'}",
            f"- Support: {support.replace('_', ' ')}",
        ]

        if ctx['essentials_low']:
            lines.append(f"- LOW ESSENTIALS (unchecked 2+ days): {', '.join(ctx['essentials_low'])}")

        # Meal rules
        lines.append("\n## IMPORTANT — New Mom Meal Rules")
        lines.append("- Iron-rich food daily (lentils, spinach, red meat, fortified cereals)")
        lines.append("- Calcium at every meal")
        lines.append("- Omega-3 three times per week")
        lines.append("- Max 20 min prep per meal")
        lines.append("- At least one meal under 5 minutes prep")
        lines.append("- At least one meal must be one-handed (can eat while holding baby)")
        if ctx['is_breastfeeding']:
            lines.append("- BREASTFEEDING: +500 calories, no high-mercury fish, max one caffeine source")
        if solo:
            lines.append("- FLYING SOLO: no-cook or microwave meals preferred")
        if ctx['had_csection'] and weeks < 6:
            lines.append("- POST C-SECTION (<6 weeks): high fibre, no bloating foods, plenty of fluids")
        lines.append("- NEVER use language like: lose weight, get your body back, post-baby diet")
        lines.append("- Frame ALL nutrition as recovery and energy, never aesthetics")

        # Exercise rules
        lines.append("\n## IMPORTANT — New Mom Exercise Rules")
        if weeks <= 2:
            lines.append("- Weeks 1-2: pelvic floor exercises ONLY, no other exercise")
        elif weeks <= 6:
            lines.append(f"- Week {weeks}: gentle walking max 15 mins, pelvic floor, NO core work, NO high impact")
        elif ctx['had_csection'] and weeks < 12:
            lines.append(f"- Week {weeks} (post C-section): low impact cardio, postnatal yoga, swimming — no high impact until week 12")
        else:
            lines.append(f"- Week {weeks}: low impact cardio, postnatal yoga, swimming, light strength")
        lines.append("- NEVER say: get your pre-baby body back, burn calories")
        lines.append("- Frame as: recovery, energy, strength for carrying baby")

        # Me time rules
        lines.append("\n## IMPORTANT — New Mom Me Time Rules")
        lines.append("- Frame as medically necessary, NOT a luxury")
        lines.append("- Max 30 minutes suggestions")
        lines.append("- Realistic only: hot shower, one TV episode, quiet tea, short walk, phone call, reading")
        if solo:
            lines.append("- FLYING SOLO: in-home options only, acknowledge the difficulty warmly")
        elif support in ('partner_all_day', 'partner_after_6'):
            lines.append("- Partner available — name specific window ('Use 8:30-9:30pm — partner can take the baby')")

        # Selfcare rules
        lines.append("\n## IMPORTANT — New Mom Self-care Rules")
        if ctx['is_breastfeeding']:
            lines.append("- Always include hydration reminder")
        lines.append("- Postnatal vitamin reminder daily")
        if ctx['had_csection'] and weeks < 8:
            lines.append("- Include wound care check reminder")

        # Housework rules
        lines.append("\n## IMPORTANT — New Mom Housework Rules")
        lines.append("- Maximum 2 housework items per day")
        if solo:
            lines.append("- FLYING SOLO: maximum 1 item, all optional")
        if weeks < 6:
            lines.append("- No physical strain tasks (heavy lifting, scrubbing, mopping)")
        lines.append("- Section note MUST read: 'Keep it minimal — the house can wait. You cannot.'")

        return '\n'.join(lines) + '\n'

    def _schedule_section(self, target_date):
        events = self._get_events_for_date(target_date)
        if not events:
            return "## Today's Schedule\nNo fixed events scheduled.\n"

        lines = ["## Today's Schedule"]
        for event in events:
            end = f"–{event.end_time.strftime('%H:%M')}" if event.end_time else ''
            line = f"- {event.start_time.strftime('%H:%M')}{end}: {event.title}"
            if event.location:
                line += f" at {event.location}"
            if event.travel_time_minutes:
                line += f" (travel: {event.travel_time_minutes} min)"
            if event.child:
                line += f" [for {event.child.name}]"
            lines.append(line)
        return '\n'.join(lines) + '\n'

    def _favourites_section(self):
        """Include the user's favourite meals so AI can repeat/vary them."""
        favourites = self.profile.favourite_meals.all()[:15]
        if not favourites:
            return None

        lines = [
            "## Favourite Meals",
            "The user has liked these meals before. Try to include some of them "
            "(or creative variations) in today's plan. Don't repeat the exact same "
            "meal every day — rotate and vary, but keep the style she loves.",
        ]
        for fav in favourites:
            line = f"- {fav.meal_name} ({fav.meal_type})"
            if fav.description:
                line += f" — {fav.description}"
            lines.append(line)
        return '\n'.join(lines) + '\n'

    def _swap_patterns_section(self):
        """Include swap/change patterns so AI learns what the user rejects and prefers."""
        from django.db.models import Count
        logs = self.profile.meal_swap_logs.all()[:30]
        if not logs:
            return None

        # Find frequently rejected meals
        rejected = self.profile.meal_swap_logs.values('rejected_meal').annotate(
            count=Count('id')
        ).filter(count__gte=2).order_by('-count')[:5]

        # Find user change requests (what they specifically ask for)
        change_requests = self.profile.meal_swap_logs.exclude(
            user_request=''
        ).values('meal_type', 'user_request', 'day_of_week')[:10]

        lines = ["## Meal Preferences (learned from user behavior)"]

        if rejected:
            lines.append("The user frequently rejects these meals — AVOID suggesting them:")
            for r in rejected:
                lines.append(f"- {r['rejected_meal']} (rejected {r['count']} times)")

        if change_requests:
            lines.append("\nThe user has specifically requested these — factor them in:")
            for c in change_requests:
                day = f" on {c['day_of_week']}s" if c['day_of_week'] else ""
                lines.append(f"- Wants '{c['user_request']}' for {c['meal_type']}{day}")

        return '\n'.join(lines) + '\n'

    def _housework_history_section(self):
        """Include housework completion/deletion patterns so AI learns user preferences."""
        from django.db.models import Count
        from ..models import HouseworkTask, HouseworkTaskDeletionLog

        lookback = date.today() - timedelta(days=14)

        # Frequently completed tasks — things user actually does
        completed_tasks = HouseworkTask.objects.filter(
            housework_list__profile=self.profile,
            housework_list__date__gte=lookback,
            completed=True,
        ).values('name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        # Frequently skipped tasks — AI-generated but never completed
        skipped_tasks = HouseworkTask.objects.filter(
            housework_list__profile=self.profile,
            housework_list__date__gte=lookback,
            completed=False,
            is_user_added=False,
        ).values('name').annotate(
            count=Count('id')
        ).filter(count__gte=2).order_by('-count')[:5]

        # Frequently deleted tasks
        deleted_tasks = HouseworkTaskDeletionLog.objects.filter(
            profile=self.profile,
            deleted_at__gte=lookback,
            was_ai_generated=True,
        ).values('task_name').annotate(
            count=Count('id')
        ).filter(count__gte=2).order_by('-count')[:5]

        # User-added tasks — strong signal of what they want
        user_added = HouseworkTask.objects.filter(
            housework_list__profile=self.profile,
            housework_list__date__gte=lookback,
            is_user_added=True,
        ).values('name').annotate(
            count=Count('id')
        ).order_by('-count')[:5]

        if not any([completed_tasks, skipped_tasks, deleted_tasks, user_added]):
            return None

        lines = ["## Housework Preferences (learned from recent behavior)"]

        if deleted_tasks:
            lines.append("The user frequently REMOVES these tasks — AVOID suggesting them:")
            for d in deleted_tasks:
                lines.append(f"- {d['task_name']} (removed {d['count']} times)")

        if skipped_tasks:
            lines.append("\nThese tasks are frequently left incomplete — suggest less often:")
            for s in skipped_tasks:
                lines.append(f"- {s['name']} (skipped {s['count']} times)")

        if completed_tasks:
            lines.append("\nTasks the user consistently completes (good to suggest similar):")
            for c in completed_tasks:
                lines.append(f"- {c['name']} (done {c['count']} times)")

        if user_added:
            lines.append("\nTasks the user adds manually — include these proactively:")
            for u in user_added:
                lines.append(f"- {u['name']} (added {u['count']} times)")

        return '\n'.join(lines) + '\n'

    def _custom_section_history_section(self):
        """Include custom section task patterns so AI learns user preferences per section."""
        from django.db.models import Count
        from ..models import CustomSectionTask, CustomSectionDeletionLog

        lookback = date.today() - timedelta(days=14)

        # Get all custom section keys this user has
        layout = self.profile.custom_layout or []
        custom_keys = [
            item.get('key') for item in layout
            if item.get('custom_label') or item.get('added_by_user')
        ]
        if not custom_keys:
            return None

        all_lines = []

        for key in custom_keys:
            label = next(
                (item.get('custom_label', key) for item in layout if item.get('key') == key),
                key,
            )
            lines = []

            # Frequently deleted tasks for this section
            deleted = CustomSectionDeletionLog.objects.filter(
                profile=self.profile, section_key=key,
                deleted_at__gte=lookback, was_ai_generated=True,
            ).values('task_name').annotate(
                count=Count('id')
            ).filter(count__gte=2).order_by('-count')[:5]

            if deleted:
                lines.append(f"AVOID for {label}:")
                for d in deleted:
                    lines.append(f"- {d['task_name']} (removed {d['count']} times)")

            # Frequently completed
            completed = CustomSectionTask.objects.filter(
                section_list__profile=self.profile, section_list__section_key=key,
                section_list__date__gte=lookback, completed=True,
            ).values('name').annotate(
                count=Count('id')
            ).order_by('-count')[:5]

            if completed:
                lines.append(f"User completes for {label}:")
                for c in completed:
                    lines.append(f"- {c['name']} (done {c['count']} times)")

            # User-added tasks
            user_added = CustomSectionTask.objects.filter(
                section_list__profile=self.profile, section_list__section_key=key,
                section_list__date__gte=lookback, is_user_added=True,
            ).values('name').annotate(
                count=Count('id')
            ).order_by('-count')[:3]

            if user_added:
                lines.append(f"User adds for {label}:")
                for u in user_added:
                    lines.append(f"- {u['name']} (added {u['count']} times)")

            if lines:
                all_lines.extend(lines)

        if not all_lines:
            return None

        return "## Custom Section Preferences (learned)\n" + '\n'.join(all_lines) + '\n'

    def _children_section(self):
        children = self.profile.children.all()
        if not children:
            return "## Children\nNo children added yet.\n"

        lines = ["## Children"]
        for child in children:
            interests = ', '.join(child.interests) if child.interests else 'not specified'
            line = f"- {child.name} (age {child.age}): interests in {interests}"
            if child.school_name:
                line += f", attends {child.school_name}"
            lines.append(line)
        return '\n'.join(lines) + '\n'

    def _academic_section(self, target_date):
        academic_types = ['class', 'exam', 'assignment_due', 'study']
        events = self._get_events_for_date(target_date, event_types=academic_types)
        if not events:
            return "## Academic Schedule\nNo classes or academic events today.\n"

        lines = ["## Academic Schedule"]
        for event in events:
            end = f"–{event.end_time.strftime('%H:%M')}" if event.end_time else ''
            line = f"- {event.start_time.strftime('%H:%M')}{end}: {event.title} ({event.get_event_type_display()})"
            if event.location:
                line += f" at {event.location}"
            if event.travel_time_minutes:
                line += f" (commute: {event.travel_time_minutes} min)"
            lines.append(line)
        return '\n'.join(lines) + '\n'

    def _work_section(self, target_date):
        work_types = ['work_shift', 'meeting']
        events = self._get_events_for_date(target_date, event_types=work_types)
        if not events:
            return "## Work Schedule\nNo work events today.\n"

        lines = ["## Work Schedule"]
        for event in events:
            end = f"–{event.end_time.strftime('%H:%M')}" if event.end_time else ''
            line = f"- {event.start_time.strftime('%H:%M')}{end}: {event.title} ({event.get_event_type_display()})"
            if event.location:
                line += f" at {event.location}"
            if event.travel_time_minutes:
                line += f" (commute: {event.travel_time_minutes} min)"
            lines.append(line)
        return '\n'.join(lines) + '\n'

    def _weekly_meals_section(self, week_start):
        """Collect all meal ingredients from the week's day plans."""
        from datetime import timedelta
        from ..models import DayPlan

        week_end = week_start + timedelta(days=6)
        plans = DayPlan.objects.filter(
            profile=self.profile,
            date__gte=week_start,
            date__lte=week_end,
            status='ready',
        ).prefetch_related('meals')

        if not plans.exists():
            return (
                "## This Week's Meals\n"
                "No meal plans generated yet for this week. Generate a grocery list "
                "based on the user's cuisine preferences and dietary restrictions instead.\n"
            )

        lines = ["## This Week's Meals and Ingredients"]
        for plan in plans:
            day_name = plan.date.strftime('%A')
            for meal in plan.meals.all():
                ingredients = ', '.join(meal.ingredients) if meal.ingredients else 'no ingredients listed'
                lines.append(f"- {day_name} {meal.get_meal_type_display()}: {meal.name} ({ingredients})")

        return '\n'.join(lines) + '\n'

    # ------------------------------------------------------------------
    # Chat-specific context sections
    # ------------------------------------------------------------------

    def _day_plan_section(self, target_date, label="Today"):
        """Summarise a day plan for chat context. `label` is used in the
        heading and the empty-state message ('Today' / 'Tomorrow')."""
        from ..models import DayPlan
        try:
            plan = DayPlan.objects.get(profile=self.profile, date=target_date, status='ready')
        except DayPlan.DoesNotExist:
            return f"## {label}'s Plan\nNo plan generated yet for {label.lower()}.\n"

        d = plan.plan_data or {}
        lines = [f"## {label}'s Plan"]

        # Meals
        meals = d.get('meals') or d.get('mom_meals') or {}
        for meal_type in ('breakfast', 'lunch', 'dinner'):
            meal = meals.get(meal_type)
            if isinstance(meal, dict):
                lines.append(f"- {meal_type.title()}: {meal.get('name', '?')}")

        snacks = meals.get('snacks')
        if isinstance(snacks, list) and snacks:
            lines.append(f"- Snacks: {', '.join(str(s) for s in snacks)}")

        # Priorities
        priorities = d.get('priorities', [])
        if priorities:
            lines.append("\nPriorities:")
            for p in priorities[:5]:
                if isinstance(p, dict):
                    done = "done" if p.get('done') else "pending"
                    lines.append(f"- {p.get('title', '?')} ({done})")

        # Selfcare / me-time
        selfcare = d.get('selfcare')
        if selfcare:
            if isinstance(selfcare, dict):
                lines.append(f"\nMe-time: {selfcare.get('activity', '?')}")
            elif isinstance(selfcare, list):
                lines.append("\nMe-time:")
                for s in selfcare:
                    lines.append(f"- {s.get('activity', '?')}")

        # Errands
        errands = d.get('errands', [])
        if errands:
            lines.append("\nErrands:")
            for e in errands:
                if isinstance(e, dict):
                    lines.append(f"- {e.get('title', '?')}")

        return '\n'.join(lines) + '\n'

    def _active_grocery_section(self):
        """Summarise the active grocery list for chat context."""
        from ..models import GroceryList, GroceryItem
        grocery_list = GroceryList.objects.filter(
            profile=self.profile, completed=False
        ).order_by('-generated_at').first()
        if not grocery_list:
            return "## Grocery List\nNo active grocery list.\n"

        items = GroceryItem.objects.filter(grocery_list=grocery_list, checked=False)
        if not items.exists():
            return "## Grocery List\nAll items checked off.\n"

        by_category = {}
        for item in items:
            cat = item.get_category_display()
            by_category.setdefault(cat, []).append(
                f"{item.name}{f' ({item.quantity})' if item.quantity else ''}"
            )

        lines = ["## Active Grocery List"]
        for cat, names in by_category.items():
            lines.append(f"\n{cat}:")
            for n in names:
                lines.append(f"- {n}")
        return '\n'.join(lines) + '\n'

    def _todays_housework_section(self, target_date):
        """Summarise today's housework for chat context."""
        from ..models import HouseworkList
        hw_list = HouseworkList.objects.filter(
            profile=self.profile, date=target_date
        ).first()
        if not hw_list:
            return None  # No housework section if none exists

        tasks = hw_list.tasks.all()
        if not tasks.exists():
            return "## Today's Housework\nNo tasks.\n"

        lines = ["## Today's Housework"]
        for t in tasks:
            status = "done" if t.completed else "pending"
            lines.append(f"- {t.name} ({status})")
        return '\n'.join(lines) + '\n'

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _get_events_for_date(self, target_date, event_types=None):
        """Get active events that occur on the given date based on recurrence rules."""
        events = self.profile.schedule_events.filter(is_active=True)
        if event_types:
            events = events.filter(event_type__in=event_types)

        day_of_week = target_date.weekday()  # 0=Monday

        matching = []
        for event in events:
            if event.recurrence == 'none':
                # One-time events: match by event_date if set, otherwise show always
                if event.event_date:
                    if event.event_date == target_date:
                        matching.append(event)
                else:
                    matching.append(event)
            elif event.recurrence == 'daily':
                matching.append(event)
            elif event.recurrence == 'weekdays' and day_of_week < 5:
                matching.append(event)
            elif event.recurrence == 'weekly' and day_of_week == 0:
                # Weekly events default to Monday; for a proper implementation
                # you'd store which day. For now this works with recurrence_days.
                if event.recurrence_days and day_of_week in event.recurrence_days:
                    matching.append(event)
                elif not event.recurrence_days:
                    matching.append(event)
            elif event.recurrence == 'custom' and day_of_week in (event.recurrence_days or []):
                matching.append(event)

        return sorted(matching, key=lambda e: e.start_time)

    def _assemble_system_prompt(self, sections):
        header = (
            "You are Dayo, a warm and helpful personal AI day planner assistant. "
            "You create detailed, realistic daily schedules that are practical and "
            "achievable. You consider travel times, meal prep, and rest periods.\n\n"
        )
        return header + '\n'.join(sections)

    def _build_plan_request(self, target_date):
        day_name = target_date.strftime('%A')
        date_str = target_date.strftime('%B %d, %Y')
        wake = self.profile.wake_time.strftime('%H:%M')
        sleep = self.profile.sleep_time.strftime('%H:%M')

        return (
            f"Generate my complete day plan for {day_name}, {date_str}.\n\n"
            f"Plan from {wake} to {sleep}.\n\n"
            "Return a JSON object with exactly this structure:\n"
            "{\n"
            '  "blocks": [\n'
            "    {\n"
            '      "block_type": "wake_up|meal|activity|child_care|travel|work|study|exercise|free_time|errand|sleep",\n'
            '      "title": "short title",\n'
            '      "description": "brief description",\n'
            '      "start_time": "HH:MM",\n'
            '      "end_time": "HH:MM",\n'
            '      "is_fixed": true/false\n'
            "    }\n"
            "  ],\n"
            '  "meals": [\n'
            "    {\n"
            '      "meal_type": "breakfast|lunch|snack|dinner",\n'
            '      "name": "meal name",\n'
            '      "description": "brief recipe or description",\n'
            '      "prep_time_minutes": 30,\n'
            '      "ingredients": ["ingredient 1", "ingredient 2"]\n'
            "    }\n"
            "  ]\n"
            "}\n\n"
            "Rules:\n"
            "- Include ALL meals (breakfast, lunch, snack, dinner)\n"
            "- Add travel blocks before events that have travel time\n"
            "- Mark scheduled/fixed events with is_fixed: true\n"
            "- Fill gaps with useful activities, rest, or free time\n"
            "- Keep it realistic and not over-packed\n"
            "- Return ONLY valid JSON, no other text\n"
        )
