import json
import logging
from datetime import date, timedelta

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import DayPlan, GroceryItem, GroceryList, MealPlan
from .ai_context import AIContextAssembler

logger = logging.getLogger(__name__)

FREQUENCY_DAYS = {
    'weekly': 7,
    'biweekly': 14,
    'monthly': 30,
}


class GroceryGenerator:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.5,
            max_output_tokens=4096,
            transport='rest',
        )

    def generate_grocery_list(self, profile, week_start=None):
        """
        Generate a grocery list from the weekly meal plans already saved in DB.
        Returns the new GroceryList on success, or None if AI generation fails
        (so the previous active list stays intact and a future call can retry).
        """
        if week_start is None:
            today = date.today()
            week_start = today

        # Use grocery frequency to determine how many days to cover
        days = FREQUENCY_DAYS.get(profile.grocery_frequency, 7)
        end_date = week_start + timedelta(days=days - 1)

        # Step 1: Collect ingredients from existing meal plans
        existing_meals = self._collect_existing_meals(profile, week_start, end_date)

        # Step 2: Get pantry items to exclude
        pantry = list(profile.pantry_items.values_list('name', flat=True))

        # Step 3: Build context and ask AI to generate consolidated grocery.
        # We call the AI FIRST — before any DB mutations — so a failure here
        # leaves the existing active list (if any) untouched for a clean retry.
        try:
            assembler = AIContextAssembler(profile)
            system_prompt = self._build_system_prompt(assembler)
            user_message = self._build_user_message(
                profile, week_start, end_date, days, existing_meals, pantry
            )

            messages = [
                SystemMessage(content=system_prompt),
                HumanMessage(content=user_message),
            ]

            # Debug: how many meals made it into the prompt, and a preview.
            # Using warning level so Render's default log config shows them.
            meals_with_ingredients = sum(
                1 for m in existing_meals['meals'] if m.get('ingredients')
            )
            logger.warning(
                f'Grocery prompt — {meals_with_ingredients}/{len(existing_meals["meals"])} '
                f'meals have ingredients'
            )
            logger.warning(f'Grocery user message (first 1200 chars):\n{user_message[:1200]}')

            # Try up to 2 times — retry on malformed JSON OR a suspiciously
            # short list (Gemini sometimes stops after a handful of items and
            # the JSON happens to be valid).
            MIN_EXPECTED_ITEMS = 10
            parsed_items = None
            for attempt in range(2):
                response = self.llm.invoke(messages)
                raw_content = response.content.strip()
                try:
                    candidate = self._parse_response(raw_content)
                except json.JSONDecodeError as e:
                    logger.error(f'Grocery JSON parse attempt {attempt + 1} failed: {e}')
                    if attempt == 0:
                        messages.append(HumanMessage(
                            content="Your response was not valid JSON. Return ONLY a valid JSON array, nothing else."
                        ))
                    continue

                if attempt == 0 and len(candidate) < MIN_EXPECTED_ITEMS:
                    logger.warning(
                        f'Grocery list only had {len(candidate)} items — retrying for a more complete list'
                    )
                    messages.append(HumanMessage(content=(
                        f"Your previous response only returned {len(candidate)} items. "
                        f"The user has diverse weekly meals. Return a more complete list of 20-25 items "
                        f"spanning produce, grains, proteins, dairy, and spices. Do not return only produce."
                    )))
                    continue

                parsed_items = candidate
                break
        except Exception as e:
            logger.error(f'Grocery AI call failed: {e}')
            return None

        if not parsed_items:
            logger.error('Grocery generation failed after 2 attempts — keeping existing list intact.')
            return None

        # Collect unchecked user-added items from the previous list before closing it
        carryover_items = []
        prev_list = GroceryList.objects.filter(profile=profile).order_by('-generated_at').first()
        if prev_list:
            carryover_items = list(
                prev_list.items.filter(checked=False, is_user_added=True).values('name', 'quantity', 'category')
            )

        # AI succeeded — safe to do DB mutations now
        GroceryList.objects.filter(profile=profile, completed=False).update(completed=True)

        grocery_list = GroceryList.objects.create(
            profile=profile,
            week_start_date=week_start,
        )

        self._save_items(grocery_list, parsed_items)

        existing_names = set(grocery_list.items.values_list('name', flat=True))

        for item in carryover_items:
            if item['name'] not in existing_names:
                GroceryItem.objects.create(
                    grocery_list=grocery_list,
                    name=item['name'],
                    quantity=item.get('quantity', ''),
                    category=item.get('category', 'other'),
                    is_user_added=True,
                )
                existing_names.add(item['name'])

        # Add low-stock essentials to grocery list
        from ..models import EssentialsCheck
        today = date.today()
        yesterday = today - timedelta(days=1)
        day_before = today - timedelta(days=2)
        unchecked_y = set(
            EssentialsCheck.objects.filter(
                profile=profile, date=yesterday, is_checked=False,
            ).values_list('item', flat=True)
        )
        unchecked_db = set(
            EssentialsCheck.objects.filter(
                profile=profile, date=day_before, is_checked=False,
            ).values_list('item', flat=True)
        )
        low_items = unchecked_y & unchecked_db
        for item_name in low_items:
            if item_name not in existing_names:
                GroceryItem.objects.create(
                    grocery_list=grocery_list,
                    name=item_name,
                    quantity='',
                    category='other',
                    is_user_added=True,
                )
                existing_names.add(item_name)

        return grocery_list

    def _collect_existing_meals(self, profile, start_date, end_date):
        """Collect all meal ingredients from existing day plans in the period."""
        plans = DayPlan.objects.filter(
            profile=profile,
            date__gte=start_date,
            date__lte=end_date,
            status='ready',
        ).prefetch_related('meals')

        meals_info = []
        planned_dates = set()

        for plan in plans:
            planned_dates.add(plan.date)
            # From MealPlan records
            for meal in plan.meals.all():
                if meal.ingredients:
                    meals_info.append({
                        'date': str(plan.date),
                        'day': plan.date.strftime('%A'),
                        'meal_type': meal.meal_type,
                        'name': meal.name,
                        'ingredients': meal.ingredients,
                    })

            # Also check plan_data for inline meals
            plan_data = plan.plan_data or {}
            meals_data = plan_data.get('meals') or plan_data.get('mom_meals') or {}
            if isinstance(meals_data, dict):
                for meal_type in ['breakfast', 'lunch', 'dinner']:
                    meal = meals_data.get(meal_type)
                    if meal and isinstance(meal, dict) and meal.get('name'):
                        # Only add if not already captured from MealPlan
                        already = any(
                            m['date'] == str(plan.date) and m['meal_type'] == meal_type
                            for m in meals_info
                        )
                        if not already:
                            meals_info.append({
                                'date': str(plan.date),
                                'day': plan.date.strftime('%A'),
                                'meal_type': meal_type,
                                'name': meal.get('name', ''),
                                'ingredients': meal.get('ingredients', []),
                            })

        total_days = (end_date - start_date).days + 1
        unplanned_days = total_days - len(planned_dates)

        return {
            'meals': meals_info,
            'planned_days': len(planned_dates),
            'unplanned_days': unplanned_days,
            'total_days': total_days,
        }

    def _build_system_prompt(self, assembler):
        sections = [
            assembler._base_profile_section(),
            assembler._preferences_section(),
        ]

        fav_section = assembler._favourites_section()
        if fav_section:
            sections.append(fav_section)

        header = (
            "You are Dayo, a smart grocery planning assistant. "
            "You generate accurate, realistic grocery lists based on the user's "
            "actual meal plans and cooking habits. You know local ingredients, "
            "realistic quantities, and how families actually cook.\n\n"
        )
        return header + '\n'.join(sections)

    def _build_user_message(self, profile, start_date, end_date, days, existing_meals, pantry):
        family = profile.family_size or 1
        freq = profile.grocery_frequency or 'weekly'

        # Format planned meals — grouped by day with ingredients when known.
        # Passing ingredients is critical: without them Gemini guesses from the
        # dish name alone and under-reports (just produce), missing the grains,
        # proteins, dairy, and spices the meals actually need.
        meals_text = "\n## Planned Dishes\n"
        if existing_meals['meals']:
            days_grouped = {}
            for m in existing_meals['meals']:
                day = m['day']
                days_grouped.setdefault(day, []).append(m)
            for day, meals in days_grouped.items():
                meals_text += f"- {day}:\n"
                for m in meals:
                    ing = m.get('ingredients') or []
                    if ing:
                        meals_text += f"    - {m['name']}: {', '.join(str(i) for i in ing)}\n"
                    else:
                        meals_text += f"    - {m['name']}\n"
        else:
            meals_text += "No meals planned yet.\n"

        pantry_text = ""
        if pantry:
            pantry_text = (
                f"\n## Pantry Items (DO NOT include these)\n"
                f"The user already has: {', '.join(pantry)}\n"
                f"Do NOT add these to the grocery list.\n"
            )

        return (
            f"Generate a grocery list for {days} days ({start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}).\n"
            f"Family size: {family} people\n"
            f"{meals_text}"
            f"{pantry_text}\n"
            "Rules:\n"
            "- Extract EVERY ingredient from EVERY planned meal listed above. Do not skip any.\n"
            "- Consolidate duplicate ingredients across meals (onion appearing in 8 meals → one entry with total kg)\n"
            f"- Scale ALL quantities for {family} people\n"
            "- Use realistic local quantities: kg, g, litres, packets, pieces — NOT cups or tablespoons\n"
            "- Categorise every item: produce, dairy, grains, protein, spices, snacks, other\n"
            "- Include cooking essentials needed for the meals (oil, ghee, salt) unless in pantry\n"
            "- Do NOT include pantry items listed above\n"
            "- Minimum 15 items, ideally 20-25. DO NOT under-return — err on the side of more items, never fewer.\n"
            "- Your list MUST contain items from EACH of these categories (unless the meals genuinely don't need them): produce, grains (rice/flour/lentils), proteins (meat/fish/eggs/pulses), dairy (milk/curd/cheese), spices, cooking oils.\n"
            "- List each vegetable SEPARATELY (onion, tomato, potato, carrot, cabbage, etc.) — do NOT merge them into a single 'Mixed Vegetables' entry.\n"
            "- Keep separate: each protein (chicken, fish, meat, eggs), each grain (rice, lentils, bulgur), each dairy (yogurt, cheese, butter), each spice.\n"
            "- Short names: 1-3 words max per item\n"
            "- Short quantities: '2 kg', '500 g', '1 L', '6 pcs', '2 pkt'\n\n"
            "Return ONLY valid JSON array, each item on one line:\n"
            '[{"name":"Onion","quantity":"2 kg","category":"produce"},\n'
            '{"name":"Chicken","quantity":"1.5 kg","category":"protein"},\n'
            '{"name":"Rice","quantity":"3 kg","category":"grains"}]\n'
        )

    def _parse_response(self, raw_content):
        import re
        content = raw_content
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        # Fix common JSON issues from AI
        # Remove trailing commas before ] or }
        content = re.sub(r',\s*([}\]])', r'\1', content)

        # If JSON is truncated (cut off mid-item), try to salvage what we can
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            # Try to find the last complete item and close the array
            last_brace = content.rfind('}')
            if last_brace > 0:
                truncated = content[:last_brace + 1]
                # Close the array
                if not truncated.rstrip().endswith(']'):
                    truncated = truncated.rstrip().rstrip(',') + ']'
                # Make sure it starts with [
                if not truncated.lstrip().startswith('['):
                    truncated = '[' + truncated
                return json.loads(truncated)
            raise

    def _save_items(self, grocery_list, items):
        for item in items:
            category = item.get('category', 'other')
            valid_categories = [c[0] for c in GroceryItem.Category.choices]
            if category not in valid_categories:
                category = 'other'

            GroceryItem.objects.create(
                grocery_list=grocery_list,
                name=item.get('name', ''),
                quantity=item.get('quantity', ''),
                category=category,
            )
