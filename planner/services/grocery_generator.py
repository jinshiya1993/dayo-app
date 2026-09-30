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
    # Spice powders that are always stocked
    'black pepper', 'white pepper', 'pepper powder',
    'garlic powder', 'onion powder', 'chilli powder', 'chili powder', 'paprika',
    # Cooking fats — pantry monthly, not weekly fresh-shopping
    'coconut oil', 'olive oil', 'mustard oil', 'sesame oil',
    'vegetable oil', 'sunflower oil', 'canola oil', 'peanut oil',
    'avocado oil', 'palm oil', 'cooking oil', 'ghee',
    # Sweeteners and pantry liquids that the AI sometimes lists as ingredients
    'sugar', 'broth', 'stock',
    # Bottled sauces and condiments — pantry purchases, not weekly fresh shopping
    'soy sauce', 'soya sauce', 'fish sauce', 'oyster sauce', 'hoisin sauce',
    'hot sauce', 'sriracha', 'tomato sauce', 'tomato paste', 'tomato puree',
    'vinegar', 'worcestershire',
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


_LEADING_QTY = re.compile(
    r'^\s*'
    r'\d+[\d/\.\s]*\s*'   # leading number, fraction, decimal, possibly mixed (e.g. "1 1/2")
    r'(?:cup|cups|tbsp|tablespoons?|tsp|teaspoons?|'
    r'g|grams?|kg|kilograms?|ml|millilit(?:er|re)s?|l|lit(?:er|re)s?|'
    r'oz|ounces?|lb|pounds?|inch|inches|'
    r'pieces?|pcs?|small|medium|large|'
    r'cans?|tins?|packets?|pkt|jars?|bottles?|'
    r'bunch(?:es)?|cloves?|sprigs?|heads?|stalks?'
    r')?\s+',
    re.IGNORECASE,
)


def _normalise_ingredient(raw):
    """Return a cleaned ingredient name, or None if it's too vague to shop for."""
    if not raw:
        return None
    # Strip parentheticals: "Chicken breast (or chickpeas)" → "Chicken breast"
    cleaned = re.sub(r'\s*\([^)]*\)', '', str(raw)).strip()
    # Drop trailing qualifiers like "low sodium", "dairy-free", etc that are
    # useful for cooking but noisy for the grocery list.
    cleaned = re.sub(r',\s*.*$', '', cleaned).strip()
    # Strip leading recipe-language quantity prefixes so "1/2 cup rolled oats"
    # → "rolled oats", "200g chicken" → "chicken", "2 medium potatoes" →
    # "potatoes". The grocery-list quantity is set separately and shown next
    # to the name in the UI; duplicating it in the name is just noise.
    cleaned = _LEADING_QTY.sub('', cleaned, count=1).strip()
    # Reduce "X or Y" alternations to X so "Water or vegetable broth" → "Water"
    # (then dropped by the vague filter) and "Oil or ghee" → "Oil" (then
    # dropped by the staple filter).
    cleaned = re.sub(r'\s+or\s+.*$', '', cleaned, flags=re.IGNORECASE).strip()
    if not cleaned:
        return None
    # Reject leftover references — the AI tags reused dishes as ingredients
    # ("leftover grilled chicken") so the cook knows to use what's already
    # made. The original meal's real ingredients are already in the list, so
    # the leftover entry has nothing to buy.
    if cleaned.lower().startswith('leftover '):
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


# --- Retail quantity normalisation -----------------------------------------
# Supermarkets (Lulu, Carrefour, Noon) sell in standard pack and weight sizes.
# "1 pc apple" or "2 cups oats" isn't something you can put in a basket, so
# every quantity we save is converted up to the smallest realistic purchasable
# unit: weights in 250 g steps, liquids in 500 ml steps, eggs in packs.

# Average weight of one piece, used to convert "3 pcs" into grams.
_PIECE_WEIGHTS_G = {
    'apple': 180, 'banana': 120, 'orange': 200, 'tomato': 100,
    'onion': 150, 'potato': 150, 'cucumber': 200, 'carrot': 80,
    'lemon': 80, 'lime': 50, 'zucchini': 200, 'eggplant': 250,
    'aubergine': 250, 'capsicum': 150, 'bell pepper': 150, 'avocado': 200,
    'sweet potato': 200, 'beetroot': 150, 'mango': 300, 'pear': 180,
    'peach': 150, 'kiwi': 80, 'pomegranate': 300,
}

# Rough gram equivalents for recipe-language units the AI sometimes emits
# despite the prompt telling it not to.
_CUP_G = 150
_TBSP_G = 15
_TSP_G = 5

# Fruits are snacking produce — they scale with how many people are in the
# house, not with how many recipes mention them. A meal plan that says
# "1 apple" still means a family of 5 buys apples by the kilo.
_FRUIT_KEYWORDS = (
    'apple', 'banana', 'orange', 'mango', 'grape', 'pear', 'peach',
    'kiwi', 'pomegranate', 'berry', 'berries', 'melon', 'watermelon',
    'papaya', 'plum', 'apricot', 'guava', 'chikoo', 'sapota', 'date',
    'fruit',
)

# Per-person weekly fruit baseline. family of 5 → 1.25 kg → rounds to 1.5 kg,
# which is how families actually buy fruit.
_FRUIT_G_PER_PERSON = 250
_FRUIT_MAX_G = 2000

# Piece-converted vegetables (cucumber "1 pc") get a milder per-person floor —
# most vegetable quantity is already driven by how many meals use them.
_VEG_G_PER_PERSON = 100


def _is_fruit(name):
    n = name.lower()
    return any(f in n for f in _FRUIT_KEYWORDS)


def _adult_equivalents(profile):
    """How many 'adult appetites' this household feeds.

    A toddler doesn't eat an adult's share, so 2 adults + 2 toddlers should
    shop like ~2.4 people, not 4. Weights: infant (<2y) 0.2, child (2-12y)
    0.6, everyone 13+ counts as a full adult.

    family_size can exceed the members actually added during onboarding —
    those unlisted people still eat, so they count as full adults. The result
    is therefore never lower than what raw family_size implies for the
    members we know nothing about.
    """
    members = list(profile.members.all())
    aeu = 1.0  # the user themselves
    for m in members:
        age = m.age
        if age < 2:
            aeu += 0.2
        elif age < 13:
            aeu += 0.6
        else:
            aeu += 1.0
    unlisted = (profile.family_size or 1) - 1 - len(members)
    if unlisted > 0:
        aeu += unlisted
    return max(1.0, aeu)

_QTY_PATTERN = re.compile(
    r'(?P<num>\d+(?:\.\d+)?(?:\s*/\s*\d+)?)\s*'
    r'(?P<unit>kg|kilograms?|g|grams?|l|litres?|liters?|ml|millilitres?|'
    r'cups?|tbsp|tablespoons?|tsp|teaspoons?|'
    r'pcs?|pieces?|bunch(?:es)?|pkts?|packets?|packs?|'
    r'cans?|tins?|jars?|bottles?|dozens?)?',
    re.IGNORECASE,
)


def _parse_number(raw):
    """'1.5' → 1.5, '1/2' → 0.5. Returns None if unparseable."""
    raw = raw.strip()
    if '/' in raw:
        try:
            num, den = raw.split('/')
            return float(num) / float(den)
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(raw)
    except ValueError:
        return None


def _round_grams_up(grams):
    """Round up to the nearest 250 g step, shown in kg from 1 kg upward."""
    steps = max(1, -(-int(grams) // 250))  # ceil division
    total = steps * 250
    if total >= 1000:
        kg = total / 1000
        # kg in 0.5 steps for display sanity (1 kg, 1.5 kg, 2 kg ...)
        kg = -(-kg // 0.5) * 0.5
        return f'{kg:g} kg'
    return f'{total} g'


def _round_ml_up(ml):
    """Round up to 500 ml steps, shown in litres from 1 L upward."""
    steps = max(1, -(-int(ml) // 500))
    total = steps * 500
    if total >= 1000:
        litres = total / 1000
        return f'{litres:g} L'
    return f'{total} ml'


def _egg_pack(count):
    """Round an egg count up to the nearest real pack size."""
    for pack in (6, 12, 15, 30):
        if count <= pack:
            return f'{pack} pcs'
    return '30 pcs'


def _piece_weight_for(name):
    lower = name.lower()
    for item, grams in _PIECE_WEIGHTS_G.items():
        if item in lower:
            return grams
    return None


def _apply_family_floor(grams, name, family_size, from_pieces=False):
    """Scale small quantities up to what a household actually buys.

    Fruit always gets a per-person weekly floor (5 people → 1.25 kg → 1.5 kg).
    Vegetables only get a floor when the amount came from a piece count
    ("1 pc cucumber") — weight-based veg amounts are meal-driven and trusted.
    """
    if _is_fruit(name):
        return min(max(grams, round(family_size * _FRUIT_G_PER_PERSON)), _FRUIT_MAX_G)
    if from_pieces:
        return max(grams, round(family_size * _VEG_G_PER_PERSON))
    return grams


def _retail_quantity(name, category, quantity, family_size=1):
    """Convert any quantity string to a supermarket-purchasable one,
    scaled to household appetite for per-person items like fruit.

    family_size accepts adult-equivalents (a float, see _adult_equivalents)
    as well as a plain headcount.

    Falls back to the original string when it can't be parsed — better to
    show what the AI said than to invent a number.
    """
    n = name.lower()
    qty = (quantity or '').strip()
    family_size = max(1.0, family_size or 1)

    # Fresh herbs are the one thing genuinely sold by the bunch.
    if any(h in n for h in _HERB_NAMES):
        return '1 bunch'

    match = _QTY_PATTERN.match(qty)
    if not match or not match.group('num'):
        # No usable quantity at all — for fruit we can still derive one
        # from household appetite; everything else stays as-is.
        if _is_fruit(n):
            return _round_grams_up(
                min(round(family_size * _FRUIT_G_PER_PERSON), _FRUIT_MAX_G)
            )
        return qty
    amount = _parse_number(match.group('num'))
    if amount is None or amount <= 0:
        return qty
    unit = (match.group('unit') or '').lower().rstrip('.')

    # Normalise unit synonyms to a canonical short form.
    if unit.startswith('kilogram'):
        unit = 'kg'
    elif unit.startswith('gram'):
        unit = 'g'
    elif unit.startswith(('litre', 'liter')) or unit == 'l':
        unit = 'l'
    elif unit.startswith('millilitre'):
        unit = 'ml'
    elif unit.startswith(('piece', 'pc')):
        unit = 'pcs'
    elif unit.startswith('dozen'):
        amount *= 12
        unit = 'pcs'
    elif unit.startswith('cup'):
        amount *= _CUP_G
        unit = 'g'
    elif unit.startswith(('tbsp', 'tablespoon')):
        amount *= _TBSP_G
        unit = 'g'
    elif unit.startswith(('tsp', 'teaspoon')):
        amount *= _TSP_G
        unit = 'g'
    elif unit.startswith('bunch'):
        return '1 bunch' if amount <= 1 else f'{int(amount)} bunches'
    elif unit.startswith(('pkt', 'packet', 'pack', 'can', 'tin', 'jar', 'bottle')):
        return qty  # already a purchasable pack unit

    if unit == 'pcs':
        if 'egg' in n:
            return _egg_pack(int(amount))
        per_piece = _piece_weight_for(n)
        if per_piece:
            grams = _apply_family_floor(amount * per_piece, n, family_size, from_pieces=True)
            return _round_grams_up(grams)
        return '1 pc' if int(amount) == 1 else f'{int(amount)} pcs'

    if unit == 'kg':
        return _round_grams_up(_apply_family_floor(amount * 1000, n, family_size))
    if unit == 'g':
        return _round_grams_up(_apply_family_floor(amount, n, family_size))
    if unit == 'l':
        return _round_ml_up(amount * 1000)
    if unit == 'ml':
        return _round_ml_up(amount)

    # Bare number with no unit — treat weighable produce as pieces,
    # otherwise leave untouched.
    if not unit:
        if 'egg' in n:
            return _egg_pack(int(amount))
        per_piece = _piece_weight_for(n)
        if per_piece:
            grams = _apply_family_floor(amount * per_piece, n, family_size, from_pieces=True)
            return _round_grams_up(grams)
    return qty


class GroceryGenerator:

    def __init__(self):
        # Gemini 2.5 Flash spends reasoning tokens from the output budget by
        # default — for grocery generation it was eating ~7.8K of 8K, leaving
        # only enough room for ~half the JSON before truncation. Grocery list
        # is structured extraction, not reasoning, so disable thinking.
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.5,
            max_output_tokens=4096,
            thinking_budget=0,
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
        # completeness floor — every fresh ingredient that appeared in a planned
        # meal (after the staple/leftover/vague filters) ends up here, so the
        # final list can never silently drop chicken, fish, paneer, etc. The
        # AI refinement step then scales quantities, expands the list, and
        # renames for shopping clarity.
        pantry_set = {p.strip().lower() for p in pantry if p and p.strip()}
        base_list = self._build_base_list(existing_meals, pantry_set)
        # Household appetite in adult-equivalents — kids eat less than adults,
        # so quantities scale to this rather than raw family_size.
        eaters = _adult_equivalents(profile)
        logger.warning(
            f'Grocery base list: {len(base_list)} unique ingredients from '
            f'{len(existing_meals["meals"])} meals'
        )

        parsed_items = None
        try:
            refined = self._refine_with_ai(
                profile, week_start, end_date, days, existing_meals, pantry, base_list, eaters
            )
            # AI must at least cover the deterministic floor — a shorter
            # response means it dropped real ingredients.
            if refined and len(refined) >= len(base_list):
                parsed_items = refined
            elif refined:
                logger.warning(
                    f'Grocery AI returned {len(refined)} items but base list has '
                    f'{len(base_list)} — falling back to deterministic list'
                )
        except Exception as e:
            logger.error(f'Grocery AI refinement failed, using deterministic fallback: {e}')

        if parsed_items is None:
            parsed_items = self._base_list_to_items(base_list, eaters)

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

        self._save_items(grocery_list, parsed_items, eaters)

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

    def _refine_with_ai(self, profile, start_date, end_date, days, existing_meals, pantry, base_list, eaters=None):
        """Ask Gemini to build the weekly grocery list from the planned meals.

        Returns a list of {name, quantity, category} dicts, or None on failure.
        """
        assembler = AIContextAssembler(profile)
        system_prompt = self._build_system_prompt(assembler)
        user_message = self._build_user_message(
            profile, start_date, end_date, days, existing_meals, pantry, base_list, eaters
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

            # Defensive cleanup of every AI-returned item:
            # 1. Strip recipe-language prefixes ("1/2 cup rolled oats" → "Rolled oats")
            #    and "X or Y" alternations ("Oil or ghee" → "Oil") from the name.
            # 2. Drop pantry staples or leftover references that slipped past
            #    the prompt rules — the base list is already staple-filtered,
            #    so anything matching here is the AI hallucinating a staple
            #    back in.
            filtered = []
            for item in candidate:
                if not isinstance(item, dict) or not item.get('name'):
                    continue
                cleaned_name = _normalise_ingredient(item['name'])
                if not cleaned_name:
                    continue
                if cleaned_name.lower().strip() in _VAGUE_INGREDIENT_NAMES:
                    continue
                if _is_pantry_staple(cleaned_name, item.get('category', '')):
                    continue
                # Preserve the AI's casing on the first letter (it knows better
                # than upper-on-first), only replace the name with the cleaned
                # form when stripping actually changed something.
                if cleaned_name != item['name']:
                    item = {**item, 'name': cleaned_name}
                filtered.append(item)
            if len(filtered) > MAX_GROCERY_ITEMS:
                filtered = filtered[:MAX_GROCERY_ITEMS]

            if len(filtered) < len(base_list) and attempt == 0:
                logger.warning(
                    f'Grocery AI returned {len(filtered)} items after defensive filter '
                    f'(base is {len(base_list)}) — asking to expand'
                )
                missing = len(base_list) - len(filtered)
                messages.append(HumanMessage(content=(
                    f"You dropped {missing} ingredient(s) from the required base list. "
                    f"Every item in '## Required base items' MUST appear in your response "
                    f"(you may rename for shopping clarity but do not omit any). "
                    f"Apply the quantity rules in the prompt — herbs in bunches, "
                    f"aromatics in 100-200 g, no kg of pepper."
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

    def _build_user_message(self, profile, start_date, end_date, days, existing_meals, pantry, base_list=None, eaters=None):
        family = profile.family_size or 1
        eaters = eaters or float(family)
        freq = profile.grocery_frequency or 'weekly'

        # Format planned meals — grouped by day with ingredients when known.
        # Passing ingredients is critical: without them Gemini guesses from the
        # dish name alone and under-reports (just produce), missing the grains,
        # proteins, dairy, and dairy/aromatics the meals actually need.
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
            base_text = (
                "\n## Required base items (EVERY one MUST appear in your response)\n"
                "These are the fresh ingredients the planned meals actually need, "
                "already filtered for pantry staples. You MUST include every one, "
                "but you may rename for shopping clarity (e.g. 'Chicken breast' → "
                "'Chicken') and apply the quantity rules below.\n"
            )
            for entry in base_list:
                base_text += f"- {entry['name']}  (appears in {entry['meal_count']} meal(s), category: {entry['category']})\n"

        return (
            f"Build a {freq} fresh-shopping list for {days} days "
            f"({start_date.strftime('%B %d')} to {end_date.strftime('%B %d')}).\n"
            f"Family size: {family} people (about {eaters:g} adult appetites — "
            f"children eat smaller portions, so scale quantities to feed "
            f"{eaters:g} adults)\n"
            f"{meals_text}"
            f"{base_text}"
            f"{pantry_text}\n"
            "## What to INCLUDE (only fresh items the user actually buys this period)\n"
            "- Fresh produce: vegetables, fruits, fresh herbs (cilantro, basil, mint, parsley)\n"
            "- Fresh proteins: chicken, fish, mutton, eggs, paneer, tofu\n"
            "- Dairy: milk, yoghurt/curd, cheese, fresh cream\n"
            "- Grains that run out weekly: bread, oats, pasta, noodles, fresh poha\n"
            "- Specialty items called for in the meals that the user wouldn't normally stock\n"
            "\n"
            "## What to EXCLUDE (the user already keeps these stocked)\n"
            "- Pantry staples: rice, flour/atta, dried lentils/dal/pulses, sugar, salt\n"
            "- Dried spices and powders: turmeric, cumin, coriander powder, garam masala, "
            "black/white pepper, paprika, garlic powder, onion powder, chilli powder, mustard seed, etc.\n"
            "- Cooking oils and fats: any oil (coconut, olive, mustard, sesame, vegetable), ghee, butter for cooking\n"
            "- Water, broth, stock — never put these on a shopping list\n"
            "- Already-cooked dishes / leftovers — anything starting with 'leftover'\n"
            "- Recipe-language items: write 'lemons' (pieces), not 'lemon juice'; "
            "write 'garlic', not 'garlic paste'; write 'tomatoes', not 'tomato puree'\n"
            "\n"
            f"## Quantity guidance for {eaters:g} adult appetites over {days} days\n"
            "Every quantity MUST be something you can actually buy at a supermarket "
            "(Lulu, Carrefour, Noon) — standard pack and weight sizes only:\n"
            "- Weights in 250 g steps: 250 g, 500 g, 750 g, 1 kg, 1.5 kg — NEVER cups, tablespoons, or odd grams like 130 g\n"
            "- Fruits and vegetables by weight, NEVER single pieces: 'Apples 500 g', not 'Apple 1 pc'; "
            "'Cucumbers 500 g', not 'Cucumber 1 pc'\n"
            f"- Fruit is bought per person, not per recipe: roughly {_FRUIT_G_PER_PERSON} g "
            f"per adult appetite per week of each fruit — for this household, that means about "
            f"{_round_grams_up(min(max(round(eaters * _FRUIT_G_PER_PERSON), _FRUIT_G_PER_PERSON), _FRUIT_MAX_G))} "
            f"of apples or bananas, never '1 pc'\n"
            "- Liquids in 500 ml steps: 500 ml, 1 L, 1.5 L, 2 L\n"
            "- Eggs in real pack sizes: 6, 12, 15, or 30 pcs\n"
            "- Fresh herbs (cilantro, basil, mint, parsley, dill, curry leaves): '1 bunch' — NEVER kg\n"
            "- Aromatics (ginger, garlic, green chilli): 100–250 g — NEVER kg\n"
            "- Onions, tomatoes, potatoes scale with meals: typically 1–4 kg total for a family\n"
            "- Meat/fish/chicken: typically 0.5–2 kg total based on how many meals call for it\n"
            "- Milk: scale to ~1 L per 4 days for a family\n"
            "\n"
            "## Output format\n"
            f"- Return up to {MAX_GROCERY_ITEMS} items. Be thorough but never include excluded items above.\n"
            "- Categorise every item: produce, dairy, protein, grains, other\n"
            "- Short names (1–3 words). Short quantities ('2 kg', '500 g', '1 L', '6 pcs', '1 bunch')\n"
            "- NEVER put measurements in the name. Write 'Rolled oats' (name) + '500 g' (quantity), "
            "NOT '1/2 cup rolled oats' as the name. Same for '2 cups millet' → name 'Millet', quantity '500 g'.\n"
            "- NEVER use 'X or Y' alternations in the name. Pick one. 'Plant milk', not 'Water or plant milk'.\n"
            "- Do NOT include anything from the Pantry list above\n"
            "\n"
            "Return ONLY a valid JSON array, each item on one line:\n"
            '[{"name":"Onion","quantity":"2 kg","category":"produce"},\n'
            '{"name":"Chicken","quantity":"1.5 kg","category":"protein"},\n'
            '{"name":"Cilantro","quantity":"1 bunch","category":"produce"},\n'
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

    def _save_items(self, grocery_list, items, family_size=1):
        for item in items:
            category = item.get('category', 'other')
            valid_categories = [c[0] for c in GroceryItem.Category.choices]
            if category not in valid_categories:
                category = 'other'

            name = item.get('name', '')
            GroceryItem.objects.create(
                grocery_list=grocery_list,
                name=name,
                quantity=_retail_quantity(name, category, item.get('quantity', ''), family_size),
                category=category,
            )


_HERB_NAMES = ('cilantro', 'coriander leaves', 'basil', 'mint', 'parsley', 'dill', 'curry leaves')
_AROMATIC_NAMES = ('ginger', 'garlic', 'green chilli', 'green chili')
_CITRUS_NAMES = ('lemon', 'lime')


def _estimate_quantity(name, category, meal_count, family_size):
    """Rough fallback quantity when AI refinement didn't run. Values are
    deliberately conservative — the user can top up, and an overestimate is
    wasteful, but we avoid 'as needed' for anything we can put a number on."""
    n = name.lower()
    # family_size may be adult-equivalents (float) — keep the maths in float
    # and round only where a count or piece is displayed.
    servings = max(1.0, meal_count * family_size)

    # Per-name caps that override category scaling. Fresh herbs and aromatics
    # are always small quantities no matter how many meals they appear in,
    # and citrus is bought by the piece. Mirrors the AI prompt rules.
    if any(h in n for h in _HERB_NAMES):
        return '50 g'
    if any(a in n for a in _AROMATIC_NAMES):
        return '200 g'
    if any(c in n for c in _CITRUS_NAMES):
        return f'{max(2, min(8, round(servings / 2)))} pcs'

    if category == 'dairy':
        if 'milk' in n:
            return f'{max(1, int(servings // 4))} L'
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
            return f'{max(6, round(servings))} pcs'
        return '500 g'
    if category == 'produce':
        grams = max(250, round(servings * 100))
        return f'{grams // 1000} kg' if grams >= 1000 else f'{grams} g'
    if category == 'spices':
        return '1 pkt'
    return '1 pkt'
