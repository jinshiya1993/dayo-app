import json
import logging
import re
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

# Keyword-based category classifier. First match wins, so ordering matters
# (e.g. dairy before protein so paneer is dairy, grains before produce so
# "rice flour" isn't classified as produce via "flour").
_CATEGORY_KEYWORDS = [
    ('dairy', ['milk', 'yogurt', 'yoghurt', 'curd', 'cheese', 'butter', 'ghee', 'cream', 'paneer']),
    ('grains', ['flour', 'atta', 'rice', 'roti', 'bread', 'oats', 'quinoa', 'millet',
                'pasta', 'noodle', 'bulgur', 'couscous', 'jowar', 'bajra', 'ragi', 'poha', 'semolina', 'suji', 'rava']),
    ('protein', ['chicken', 'fish', 'tofu', 'lentil', 'dal', 'bean', 'chickpea',
                 'egg', 'meat', 'mutton', 'turkey', 'lamb', 'pulse', 'masoor',
                 'moong', 'toor', 'rajma', 'chana', 'peanut', 'soy']),
    ('spices', ['spice', 'turmeric', 'cumin', 'coriander powder', 'chili', 'chilli',
                'salt', 'masala', 'cardamom', 'cinnamon', 'mustard', 'clove',
                'fenugreek', 'asafoetida', 'hing', 'garam']),
    ('produce', ['onion', 'tomato', 'potato', 'vegetable', 'spinach', 'carrot',
                 'cauliflower', 'pea', 'cabbage', 'lemon', 'garlic', 'ginger',
                 'mint', 'cilantro', 'coriander', 'basil', 'lettuce', 'cucumber',
                 'zucchini', 'okra', 'bhindi', 'coconut', 'herb', 'asparagus',
                 'pepper', 'tamarind', 'fruit', 'apple', 'banana', 'berry', 'orange']),
]

# Ingredient strings we refuse to turn into grocery items because they are
# either meaningless on a shopping list ("as needed") or generic placeholders
# the AI refinement step is expected to expand into concrete items. Values
# here are compared against the dedupe key (lowercased + singularised), so
# use the singular form.
_VAGUE_INGREDIENT_NAMES = {'spice', 'herb', 'cooking oil', 'oil', 'salt', 'water'}

# Always-stocked staples — things the user almost never runs out of. These
# are filtered out entirely so the list stays focused on items the user
# actually needs to go out and buy. Other grain items (bread, oats, pasta,
# noodles, quinoa) aren't blocked — they flow through into the grains
# quota in _build_base_list.
_STAPLE_KEYWORDS = (
    # Core grains / flours
    'rice', 'flour', 'atta', 'semolina', 'suji', 'rava',
    # Dried pulses / dals / legumes typically stocked in the pantry
    'lentil', 'dal', 'masoor', 'moong', 'toor', 'urad',
    'kidney bean', 'black chickpea', 'black chana', 'rajma', 'chana',
    # Dried spices / seeds / seasonings
    'turmeric', 'cumin', 'mustard seed', 'fenugreek',
    'cardamom', 'cinnamon', 'clove', 'asafoetida', 'hing', 'garam',
    'sesame seed', 'bay leaf',
)

# Lower priority_order = appears first when we truncate at 25 items.
_CATEGORY_PRIORITY = {
    'produce': 0,
    'protein': 1,
    'dairy': 2,
    'other': 3,
    'spices': 4,
    'grains': 5,
}

MAX_GROCERY_ITEMS = 40


def _is_pantry_staple(name, category):
    """True when the ingredient is an always-stocked staple the user buys
    monthly, not weekly (rice, flour, dried pulses, dried spices). Grain
    items like bread/oats/pasta/noodles aren't treated as staples — they
    flow through into the grains quota."""
    lower = name.lower()
    return any(kw in lower for kw in _STAPLE_KEYWORDS)


def _classify_category(name):
    n = name.lower()
    for category, keywords in _CATEGORY_KEYWORDS:
        for kw in keywords:
            if kw in n:
                return category
    return 'other'


def _normalise_ingredient(raw):
    """Return a cleaned ingredient name, or None if it's too vague to shop for."""
    if not raw:
        return None
    # Strip parentheticals: "Chicken breast (or chickpeas)" → "Chicken breast"
    cleaned = re.sub(r'\s*\([^)]*\)', '', str(raw)).strip()
    # Drop trailing qualifiers like "low sodium", "dairy-free", etc that are
    # useful for cooking but noisy for the grocery list.
    cleaned = re.sub(r',\s*.*$', '', cleaned).strip()
    if not cleaned:
        return None
    return cleaned


# Prep/adjective words we strip when building the dedupe key so that "Chopped
# onions" / "Grated onions" / "Onion" all land in the same bucket.
_PREP_QUALIFIERS = re.compile(
    r'\b(cooked|raw|fresh|dried|chopped|grated|mixed|assorted|minced|ground|sliced|diced|shredded|boiled)\s+',
    re.IGNORECASE,
)

# Hardcoded plural→singular map. Using a curated list instead of a generic
# regex because English is messy (hummus, asparagus end in 's' but aren't
# plural; chilies→chili, not chily).
_SINGULAR_OVERRIDES = {
    'onions': 'onion', 'tomatoes': 'tomato', 'potatoes': 'potato',
    'chilies': 'chili', 'chillies': 'chili',
    'carrots': 'carrot', 'beans': 'bean', 'lentils': 'lentil',
    'peas': 'pea', 'eggs': 'egg', 'peanuts': 'peanut',
    'chickpeas': 'chickpea', 'seeds': 'seed', 'fillets': 'fillet',
    'noodles': 'noodle', 'berries': 'berry',
    'apples': 'apple', 'bananas': 'banana', 'oranges': 'orange',
    'peppers': 'pepper',
    # Also funnel vague plurals through to their singular so the
    # _VAGUE_INGREDIENT_NAMES filter catches them uniformly.
    'spices': 'spice', 'herbs': 'herb',
}


def _dedup_key(name):
    """Normalise to a lowercase canonical form used only for bucketing.

    The displayed name keeps its original casing; this key just decides when
    two entries are the same shopping-list item.
    """
    key = name.lower().strip()
    key = _PREP_QUALIFIERS.sub('', key).strip()
    # "<anything> vegetables" → "vegetables" so mixed/grated/chopped all
    # collapse into one entry.
    if key.endswith('vegetables'):
        key = 'vegetables'
    if key in _SINGULAR_OVERRIDES:
        return _SINGULAR_OVERRIDES[key]
    # Multi-word: try to singularise just the head noun (last word).
    parts = key.split()
    if len(parts) > 1 and parts[-1] in _SINGULAR_OVERRIDES:
        parts[-1] = _SINGULAR_OVERRIDES[parts[-1]]
        key = ' '.join(parts)
    return key


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

        # Step 3: Build a deterministic base list from the meals. This is the
        # floor — every ingredient that appeared in a planned meal ends up
        # here, so the list can never fall below what the user actually
        # cooks. The AI refinement step then scales quantities, adds cooking
        # essentials, and expands vague entries like "Spices".
        pantry_set = {p.strip().lower() for p in pantry if p and p.strip()}
        base_list = self._build_base_list(existing_meals, pantry_set)
        logger.warning(
            f'Grocery base list: {len(base_list)} unique ingredients from '
            f'{len(existing_meals["meals"])} meals'
        )

        parsed_items = None
        try:
            refined = self._refine_with_ai(
                profile, week_start, end_date, days, existing_meals, pantry, base_list
            )
            # Only accept the AI refinement if it isn't shorter than the
            # deterministic floor — a shorter response means Gemini dropped
            # real ingredients the user actually cooks with.
            if refined and len(refined) >= len(base_list):
                parsed_items = refined
            elif refined:
                logger.warning(
                    f'Grocery AI returned {len(refined)} items but base list has '
                    f'{len(base_list)} — falling back to deterministic list'
                )
        except Exception as e:
            logger.error(f'Grocery AI refinement failed, using deterministic list: {e}')

        if parsed_items is None:
            parsed_items = self._base_list_to_items(base_list, profile.family_size or 1)

        if not parsed_items:
            logger.error('Grocery generation produced no items — keeping existing list intact.')
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

    def _build_base_list(self, existing_meals, pantry_set):
        """Dedupe ingredients from planned meals into a list of unique items.

        Returns a list of {name, category, meal_count} dicts ordered by the
        category order in _CATEGORY_KEYWORDS so the deterministic fallback
        still looks coherent to the user.
        """
        buckets = {}  # normalised_key → {name, count, meals}
        pantry_keys = {_dedup_key(p) for p in pantry_set}
        for meal in existing_meals['meals']:
            for raw in meal.get('ingredients') or []:
                cleaned = _normalise_ingredient(raw)
                if not cleaned:
                    continue
                key = _dedup_key(cleaned)
                if not key or key in pantry_keys or key in _VAGUE_INGREDIENT_NAMES:
                    continue
                bucket = buckets.get(key)
                if not bucket:
                    display = key[:1].upper() + key[1:]
                    buckets[key] = {
                        'name': display,
                        'count': 1,
                        'meals': [meal.get('name', '')],
                    }
                else:
                    bucket['count'] += 1
                    bucket['meals'].append(meal.get('name', ''))

        base = []
        for b in buckets.values():
            cat = _classify_category(b['name'])
            if _is_pantry_staple(b['name'], cat):
                # Staple — user keeps it at home, don't add to weekly list
                continue
            base.append({'name': b['name'], 'category': cat, 'meal_count': b['count']})

        # Cap at MAX_GROCERY_ITEMS but make sure fresh proteins and dairy
        # aren't squeezed out by a long tail of single-mention produce. We
        # allocate soft quotas per category — produce gets the most slots,
        # protein and dairy are guaranteed a fair share, and any unused
        # slots are reassigned to whichever category has leftover candidates.
        CATEGORY_QUOTAS = {
            'produce': 15,
            'protein': 8,
            'dairy': 5,
            'grains': 5,
            'other': 7,
        }

        def rank_key(item):
            # Within a category, most-used ingredients come first.
            return -item['meal_count']

        by_cat = {}
        for item in base:
            by_cat.setdefault(item['category'], []).append(item)
        for cat in by_cat:
            by_cat[cat].sort(key=rank_key)

        picked = []
        leftovers = []
        for cat, quota in CATEGORY_QUOTAS.items():
            items = by_cat.pop(cat, [])
            picked.extend(items[:quota])
            leftovers.extend(items[quota:])
        # Any leftover category buckets (e.g. spices that slipped past the
        # staple filter) are appended after the quota picks.
        for cat_items in by_cat.values():
            leftovers.extend(cat_items)
        leftovers.sort(key=rank_key)

        remaining = MAX_GROCERY_ITEMS - len(picked)
        if remaining > 0:
            picked.extend(leftovers[:remaining])

        # Final ordering for display: category priority then meal count.
        picked.sort(key=lambda item: (
            _CATEGORY_PRIORITY.get(item['category'], 99),
            -item['meal_count'],
        ))
        return picked[:MAX_GROCERY_ITEMS]

    def _refine_with_ai(self, profile, start_date, end_date, days, existing_meals, pantry, base_list):
        """Ask Gemini to scale quantities, add cooking essentials, expand vague entries.

        Returns a list of {name, quantity, category} dicts, or None on failure.
        """
        assembler = AIContextAssembler(profile)
        system_prompt = self._build_system_prompt(assembler)
        user_message = self._build_user_message(
            profile, start_date, end_date, days, existing_meals, pantry, base_list
        )

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        logger.warning(
            f'Grocery AI refinement — base list {len(base_list)} items, '
            f'{sum(1 for m in existing_meals["meals"] if m.get("ingredients"))}/'
            f'{len(existing_meals["meals"])} meals have ingredients'
        )

        for attempt in range(2):
            response = self.llm.invoke(messages)
            raw_content = response.content.strip()
            try:
                candidate = self._parse_response(raw_content)
            except json.JSONDecodeError as e:
                logger.error(f'Grocery JSON parse attempt {attempt + 1} failed: {e}')
                if attempt == 0:
                    messages.append(HumanMessage(
                        content="Your previous reply was not valid JSON. Return ONLY a JSON array, nothing else."
                    ))
                continue

            # Drop any staples the AI slipped back in despite the prompt rules.
            filtered = [
                item for item in candidate
                if isinstance(item, dict)
                and item.get('name')
                and not _is_pantry_staple(item['name'], item.get('category', ''))
            ]
            # Hard cap — if the AI went over 25, trim to the top items.
            if len(filtered) > MAX_GROCERY_ITEMS:
                filtered = filtered[:MAX_GROCERY_ITEMS]

            if len(filtered) < len(base_list) and attempt == 0:
                logger.warning(
                    f'Grocery AI returned {len(filtered)} items after staple-filter '
                    f'(base is {len(base_list)}) — asking to expand'
                )
                missing = len(base_list) - len(filtered)
                messages.append(HumanMessage(content=(
                    f"You dropped {missing} ingredient(s) from the required base list. "
                    f"Every item in '## Required base items' MUST appear in your response "
                    f"(you may rename for clarity but do not omit any). "
                    f"Do NOT add pantry staples like rice, flour, bread, lentils, or "
                    f"dried spices — those are already at home."
                )))
                continue

            return filtered

        return None

    def _base_list_to_items(self, base_list, family_size):
        """Convert the deterministic base list into saveable grocery items with
        reasonable default quantities. Used when Gemini refinement fails."""
        return [
            {
                'name': entry['name'],
                'quantity': _estimate_quantity(entry['name'], entry['category'], entry['meal_count'], family_size),
                'category': entry['category'],
            }
            for entry in base_list
        ]

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

    def _build_user_message(self, profile, start_date, end_date, days, existing_meals, pantry, base_list=None):
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

        base_text = ""
        if base_list:
            base_text = "\n## Required base items (EVERY one must appear in your response)\n"
            for entry in base_list:
                base_text += f"- {entry['name']}  (appears in {entry['meal_count']} meal(s), category: {entry['category']})\n"

        return (
            f"Build a WEEKLY fresh-shopping list for {days} days "
            f"({start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}).\n"
            f"Family size: {family} people\n"
            f"{meals_text}"
            f"{base_text}"
            f"{pantry_text}\n"
            "Rules:\n"
            f"- Return {len(base_list) if base_list else MAX_GROCERY_ITEMS} items exactly. Hard cap: {MAX_GROCERY_ITEMS} items.\n"
            "- EVERY item in '## Required base items' MUST appear in your response "
            "(you may rename for shopping clarity — e.g. 'Chicken breast' → 'Chicken' — but do not omit any).\n"
            "- DO NOT add always-stocked staples: no rice, no flour/atta, no dried "
            "lentils/dal/pulses, no dried spices (turmeric, cumin, mustard seed, etc.). "
            "The user buys those monthly, not weekly.\n"
            "- DO NOT add cooking essentials (oil, ghee, salt, sugar) — those are also staples.\n"
            "- Focus the list on fresh items the user buys weekly: produce (vegetables, fruits, herbs), "
            "meat/fish/chicken/eggs, dairy (milk, yoghurt, paneer, cheese), and any grains "
            "that run out weekly like bread/oats/pasta/noodles.\n"
            f"- Scale quantities for {family} people based on how many meals use each ingredient.\n"
            "- Use realistic local quantities: kg, g, litres, packets, pieces — NOT cups or tablespoons.\n"
            "- Do NOT include any item from the Pantry list above.\n"
            "- Categorise every item using one of: produce, dairy, protein, grains, other.\n"
            "- Short names: 1-3 words max per item.\n"
            "- Short quantities: '2 kg', '500 g', '1 L', '6 pcs', '2 pkt'.\n\n"
            "Return ONLY valid JSON array, each item on one line:\n"
            '[{"name":"Onion","quantity":"2 kg","category":"produce"},\n'
            '{"name":"Chicken","quantity":"1.5 kg","category":"protein"},\n'
            '{"name":"Milk","quantity":"2 L","category":"dairy"}]\n'
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


def _estimate_quantity(name, category, meal_count, family_size):
    """Rough fallback quantity when AI refinement didn't run. Values are
    deliberately conservative — the user can top up, and an overestimate is
    wasteful, but we avoid 'as needed' for anything we can put a number on."""
    n = name.lower()
    servings = max(1, meal_count * family_size)

    if category == 'dairy':
        if 'milk' in n:
            return f'{max(1, servings // 4)} L'
        if 'ghee' in n or 'butter' in n:
            return '250 g'
        return '500 g'
    if category == 'grains':
        if 'flour' in n or 'atta' in n:
            kg = max(0.5, round(servings * 0.08, 1))
            return f'{kg} kg'
        if 'rice' in n:
            kg = max(1, round(servings * 0.12, 1))
            return f'{kg} kg'
        return '500 g'
    if category == 'protein':
        if any(k in n for k in ('chicken', 'fish', 'meat', 'mutton', 'lamb')):
            kg = max(0.5, round(servings * 0.15, 1))
            return f'{kg} kg'
        if 'egg' in n:
            return f'{max(6, servings)} pcs'
        return '500 g'
    if category == 'produce':
        grams = max(250, servings * 100)
        return f'{grams // 1000} kg' if grams >= 1000 else f'{grams} g'
    if category == 'spices':
        return '1 pkt'
    return '1 pkt'
