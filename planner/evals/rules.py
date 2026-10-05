"""One function per rule. Each restates a prompt instruction as a check.

Every rule has the same shape:

    def rule_xxx(plan_data, ctx) -> list[str]

  plan_data : one day's DayPlan.plan_data dict, straight from the DB
  ctx       : facts about the user this plan was generated for
              (see context.py -- banned ingredients, members, user_type)
  returns   : a list of violation messages; EMPTY LIST means the rule passed

Why return a list instead of raising or returning a bool:
  - raising stops at the first problem; we want to see all of them at once
  - a bool tells you something broke but not what, so you cannot act on it
  - a message names the offending value, which is what makes a report useful
"""

# From plan_generator.py:318 -- the prompt lists these and hopes. We check.
ALLOWED_TAGS = {
    'PCOS-friendly', 'Diabetic-friendly', 'Heart-healthy',
    'Anti-inflammatory', 'Low GI',
    'High protein', 'Iron-rich', 'Fiber-rich', 'Low carb', 'Healthy fats',
    'Family-friendly', 'Quick', 'One-pan', 'Make-ahead', 'Comfort',
    'Postpartum', 'Lactation support',
}

# From plan_generator.py:316.
KCAL_RANGES = {
    'breakfast': (250, 450),
    'lunch': (400, 650),
    'dinner': (400, 700),
    'snack': (80, 220),
}

MAIN_MEALS = ('breakfast', 'lunch', 'dinner')


def _meals(plan_data):
    """Meals live under 'meals', except for new mums where they are under
    'mom_meals' (plan_generator.py:183). Every rule needs this, so it lives
    in one place."""
    return plan_data.get('meals') or plan_data.get('mom_meals') or {}


def _text_of(meal):
    """Everything a human would read in one meal, lowercased -- so an
    ingredient check catches it wherever it hides: the name, the steps, a
    pairing side."""
    parts = [
        meal.get('name') or '',
        meal.get('description') or '',
        ' '.join(str(i) for i in (meal.get('ingredients') or [])),
        ' '.join(str(s) for s in (meal.get('steps') or [])),
    ]
    for p in meal.get('pairings') or []:
        if isinstance(p, dict):
            parts.append(str(p.get('with') or ''))
    return ' '.join(parts).lower()


# ---------------------------------------------------------------------------
# Structural rules -- is the output even shaped right?
# ---------------------------------------------------------------------------

def rule_meals_present(plan_data, ctx):
    """plan_generator.py:101 -- breakfast, lunch and dinner must each exist
    with a non-empty name. This is the ONLY rule Dayo enforces today."""
    out = []
    meals = _meals(plan_data)
    for slot in MAIN_MEALS:
        meal = meals.get(slot)
        if not isinstance(meal, dict):
            out.append('%s is missing entirely' % slot)
        elif not (meal.get('name') or '').strip():
            out.append('%s has no name' % slot)
    return out


def rule_steps_count(plan_data, ctx):
    """plan_generator.py:314 -- 'every meal MUST include a steps array of
    4-8 short imperative sentences'."""
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        steps = meal.get('steps') or []
        if not isinstance(steps, list):
            out.append('%s: steps is not a list' % slot)
        elif slot == 'snack':
            continue                      # the prompt allows a short snack
        elif not 4 <= len(steps) <= 8:
            out.append('%s: %d steps (expected 4-8)' % (slot, len(steps)))
    return out


def rule_tags_valid(plan_data, ctx):
    """plan_generator.py:318 -- 2-3 tags, drawn from the allowed list."""
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        tags = meal.get('tags') or []
        if not 2 <= len(tags) <= 3:
            out.append('%s: %d tags (expected 2-3)' % (slot, len(tags)))
        for t in tags:
            if t not in ALLOWED_TAGS:
                out.append('%s: invented tag %r' % (slot, t))
    return out


def rule_kcal_in_range(plan_data, ctx):
    """plan_generator.py:316 -- realistic calories per serving."""
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict) or slot not in KCAL_RANGES:
            continue
        kcal = meal.get('kcal')
        if not isinstance(kcal, int):
            out.append('%s: kcal missing or not an integer (%r)' % (slot, kcal))
            continue
        lo, hi = KCAL_RANGES[slot]
        if not lo <= kcal <= hi:
            out.append('%s: %d kcal (expected %d-%d)' % (slot, kcal, lo, hi))
    return out


def rule_snack_is_single_dish(plan_data, ctx):
    """plan_generator.py:317 -- 'emit exactly ONE snack ... NEVER a list,
    NEVER multiple items joined by a bullet or commas'."""
    snack = _meals(plan_data).get('snack')
    if not isinstance(snack, dict):
        return []
    name = snack.get('name') or ''
    # The prompt forbids bullets and commas only. It does NOT forbid "and" --
    # its own examples read "Roasted chana with peanuts". An earlier version
    # of this rule flagged "and" and produced false failures on legitimate
    # single dishes like "Carrot and Cucumber Sticks with Hummus".
    # A rule that is stricter than the prompt measures the rule, not the model.
    for marker in ('\u2022', ','):
        if marker in name:
            return ['snack name lists several items: %r' % name]
    return []


def rule_description_length(plan_data, ctx):
    """plan_generator.py:313 -- 'Keep ALL descriptions under 15 words'."""
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        words = len((meal.get('description') or '').split())
        if words > 15:
            out.append('%s: description is %d words (max 15)' % (slot, words))
    return out


# ---------------------------------------------------------------------------
# Semantic rules -- these need to know WHO the plan was for.
# No schema can express these; that is the whole point of the harness.
# ---------------------------------------------------------------------------

def rule_no_forbidden_ingredients(plan_data, ctx):
    """ai_context.py:270 -- the FORBIDDEN INGREDIENTS block, actually checked.

    This is the rule that matters most: it is the one where being wrong
    means serving someone food they must not eat.
    """
    banned = ctx.get('banned') or []
    if not banned:
        return []
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        haystack = _text_of(meal)
        hits = sorted({b for b in banned if b in haystack})
        if hits:
            out.append('%s %r contains forbidden: %s' % (
                slot, meal.get('name'), ', '.join(hits)))
    return out


def rule_no_compliance_labelling(plan_data, ctx):
    """ai_context.py:282 -- never write 'Halal' into a dish name or step.
    Compliance comes from which ingredients are chosen, not from labelling."""
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        if 'halal' in _text_of(meal):
            out.append("%s mentions 'Halal' in user-facing text" % slot)
    return out


def rule_cuisine_adherence(plan_data, ctx):
    """ai_context.py CUISINE RULE (commit 41c7303) -- every dish, snacks
    included, must come from the user's chosen cuisines.

    Deterministic approximation: a table of signature dishes that give a
    cuisine away. If a meal name contains a marker whose family is not in
    the user's allowed set, the model drifted. This catches blatant drift
    (sambar for a North-Indian-only home, a hummus snack nobody asked for --
    both real past failures); subtle authenticity judgments are left to a
    future LLM judge. An empty allowed set means the user chose nothing and
    the prompt imposes no restriction, so the rule passes.
    """
    allowed = set(ctx.get('allowed_cuisines') or [])
    if not allowed:
        return []
    out = []
    for slot, meal in _meals(plan_data).items():
        if not isinstance(meal, dict):
            continue
        name = (meal.get('name') or '').lower()
        for marker, families in _CUISINE_MARKERS.items():
            if marker in name and not (families & allowed):
                out.append('%s %r is %s cuisine, allowed: %s' % (
                    slot, meal.get('name'), '/'.join(sorted(families)),
                    ', '.join(sorted(allowed))))
                break
    return out


# Signature dishes that unambiguously belong to a cuisine family. Keys are
# matched as substrings of the lowercased meal name. Families use the same
# vocabulary users pick in onboarding (lowercased); broad families list every
# label that should count as a match ("indian" alone covers both).
_CUISINE_MARKERS = {
    'sambar': {'south indian', 'kerala', 'tamil', 'indian', 'indian (kerala style)'},
    'dosa': {'south indian', 'kerala', 'tamil', 'indian', 'indian (kerala style)'},
    'idli': {'south indian', 'kerala', 'tamil', 'indian', 'indian (kerala style)'},
    'uttapam': {'south indian', 'kerala', 'indian'},
    'puttu': {'south indian', 'kerala', 'indian', 'indian (kerala style)'},
    'appam': {'south indian', 'kerala', 'indian', 'indian (kerala style)'},
    'thoran': {'south indian', 'kerala', 'indian', 'indian (kerala style)'},
    'avial': {'south indian', 'kerala', 'indian', 'indian (kerala style)'},
    'hummus': {'middle eastern', 'arabic', 'arabic food', 'lebanese', 'mediterranean'},
    'falafel': {'middle eastern', 'arabic', 'arabic food', 'lebanese', 'mediterranean'},
    'shakshuka': {'middle eastern', 'arabic', 'arabic food', 'mediterranean', 'moroccan'},
    'tabbouleh': {'middle eastern', 'arabic', 'arabic food', 'lebanese', 'mediterranean'},
    'shawarma': {'middle eastern', 'arabic', 'arabic food', 'lebanese'},
    'pasta': {'italian', 'continental', 'mediterranean'},
    'risotto': {'italian', 'continental', 'mediterranean'},
    'pizza': {'italian', 'continental'},
    'taco': {'mexican'},
    'burrito': {'mexican'},
    'quesadilla': {'mexican'},
    'sushi': {'japanese'},
    'ramen': {'japanese'},
    'pad thai': {'thai'},
    'tom yum': {'thai'},
    'paratha': {'north indian', 'indian', 'punjabi'},
    'dal makhani': {'north indian', 'indian', 'punjabi'},
    'chole': {'north indian', 'indian', 'punjabi'},
    'rajma': {'north indian', 'indian', 'punjabi'},
    'tagine': {'moroccan'},
    'couscous': {'moroccan', 'middle eastern', 'mediterranean'},
}


# ---------------------------------------------------------------------------
# Grocery rules -- run against a generated grocery list, not a day plan.
# Input shape: list of {name, quantity, category} dicts. These reuse the
# generator's own tables (imported below) so the eval can never drift from
# what production enforces.
# ---------------------------------------------------------------------------

from ..services.grocery_generator import (  # noqa: E402
    _PIECE_WEIGHTS_G, _VAGUE_INGREDIENT_NAMES, _is_pantry_staple,
)

import re  # noqa: E402

# What a supermarket actually sells: weights in 250 g steps (kg in 0.5
# steps), liquids in 500 ml steps, packs/bunches/pieces as whole counts.
_QTY_FORMS = [
    (re.compile(r'^(\d+(?:\.\d+)?)\s*g$', re.I), lambda v: v % 250 == 0),
    (re.compile(r'^(\d+(?:\.\d+)?)\s*kg$', re.I), lambda v: (v * 1000) % 500 == 0),
    (re.compile(r'^(\d+(?:\.\d+)?)\s*ml$', re.I), lambda v: v % 500 == 0),
    (re.compile(r'^(\d+(?:\.\d+)?)\s*L$', re.I), lambda v: (v * 1000) % 500 == 0),
    (re.compile(r'^(\d+)\s*pcs?$', re.I), lambda v: v >= 1),
    (re.compile(r'^(\d+)\s*bunch(?:es)?$', re.I), lambda v: v >= 1),
    (re.compile(r'^(\d+)\s*(?:pkts?|packets?|packs?|cans?|tins?|jars?|bottles?)$', re.I), lambda v: v >= 1),
]

_RECIPE_UNITS = re.compile(r'\b(cups?|tbsp|tablespoons?|tsp|teaspoons?)\b', re.I)


def grocery_rule_retail_quantities(items, ctx):
    """grocery_generator.py quantity guidance + _retail_quantity normaliser --
    every saved quantity must be something a supermarket sells. Catches
    recipe-language units ('2 cups'), odd weights ('130 g'), and single
    pieces of weighable produce ('1 pc' apple)."""
    out = []
    for item in items:
        name = (item.get('name') or '').strip()
        qty = (item.get('quantity') or '').strip()
        if not qty:
            out.append('%s: missing quantity' % name)
            continue
        if _RECIPE_UNITS.search(qty):
            out.append('%s: recipe-language quantity %r' % (name, qty))
            continue
        matched = False
        for pattern, ok in _QTY_FORMS:
            m = pattern.match(qty)
            if m:
                matched = True
                if not ok(float(m.group(1))):
                    out.append('%s: non-retail amount %r' % (name, qty))
                break
        if not matched:
            out.append('%s: unrecognised quantity %r' % (name, qty))
            continue
        # Weighable produce must be sold by weight, never by the piece.
        if re.match(r'^\d+\s*pcs?$', qty, re.I) and 'egg' not in name.lower():
            lower = name.lower()
            if any(p in lower for p in _PIECE_WEIGHTS_G):
                out.append('%s: sold by weight, not %r' % (name, qty))
    return out


def grocery_rule_no_pantry_staples(items, ctx):
    """grocery_generator.py staple filter -- always-stocked items (rice,
    flour, dals, dried spices, oils) must never appear on the weekly list."""
    out = []
    for item in items:
        name = (item.get('name') or '').strip()
        if _is_pantry_staple(name, item.get('category', '')):
            out.append('%s is a pantry staple' % name)
        elif name.lower() in _VAGUE_INGREDIENT_NAMES:
            out.append('%s is too vague to shop for' % name)
    return out


def grocery_rule_no_leftover_items(items, ctx):
    """grocery_generator.py _normalise_ingredient -- 'leftover X' is a
    cooking note, not a purchase; nothing to buy."""
    return [
        '%s is a leftover reference' % item.get('name')
        for item in items
        if (item.get('name') or '').strip().lower().startswith('leftover')
    ]


# ---------------------------------------------------------------------------
# Week-level rule -- invisible from inside a single day.
# ---------------------------------------------------------------------------

def rule_no_repeats_across_week(plans, ctx):
    """plan_generator.py:303 -- 'VARIETY is critical -- different breakfast
    each day, different lunch each day, different dinner each day'.

    Takes a LIST of plan_data dicts, not one, because variety only exists
    across days. The runner calls week rules separately for this reason.
    """
    out = []
    for slot in MAIN_MEALS:
        names = []
        for pd in plans:
            meal = _meals(pd).get(slot)
            if isinstance(meal, dict) and meal.get('name'):
                names.append(meal['name'].strip().lower())
        dupes = sorted({n for n in names if names.count(n) > 1})
        if dupes:
            out.append('%s repeats: %s' % (slot, ', '.join(dupes)))
    return out


# Registry -- the runner iterates these, so adding a rule means adding one
# line here and nothing else.
DAY_RULES = [
    ('meals_present', rule_meals_present),
    ('forbidden_ingredients', rule_no_forbidden_ingredients),
    ('cuisine_adherence', rule_cuisine_adherence),
    ('compliance_labelling', rule_no_compliance_labelling),
    ('snack_single_dish', rule_snack_is_single_dish),
    ('kcal_in_range', rule_kcal_in_range),
    ('steps_count', rule_steps_count),
    ('tags_valid', rule_tags_valid),
    ('description_length', rule_description_length),
]

WEEK_RULES = [
    ('no_repeats', rule_no_repeats_across_week),
]

GROCERY_RULES = [
    ('retail_quantities', grocery_rule_retail_quantities),
    ('no_pantry_staples', grocery_rule_no_pantry_staples),
    ('no_leftover_items', grocery_rule_no_leftover_items),
]
