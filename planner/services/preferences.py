"""Behaviour-based personalisation — a deterministic pipeline, not an agent.

    collect_events(profile, today)    DB layer     -> list of plain events
    aggregate_events(events, today)   PURE         -> behaviour profile dict
    build_generation_context(...)     PURE         -> what the prompt renders

No LLM call anywhere in this module. Cuisines are labelled at write time by
calls that already happen (meal generation, change-meal, rename-meal), so
aggregation here is counting, never inference.

Two rules decide what we are willing to learn:

1. Silence is not evidence. Users do not tap to confirm every meal they
   cook, so a meal with no check-off tells us nothing. Only deliberate
   actions count: swaps, typed requests, favourites, and meals that
   survived in a past plan.

2. A signal must be unambiguous. Tapping Swap means "not this dish" and
   typing a dish means "this one instead". Both are clear. Deleting a
   grocery item is NOT - it could equally mean "I already have okra" -
   so grocery deletions are deliberately not a signal here.

Where a signal is only mildly ambiguous (she may have swapped Monday's
fish simply because she wasn't in the mood), repetition is the defence:
thresholds below act on patterns, never on one occurrence.
"""

from datetime import date, timedelta

# Window and decay. Anything older than 8 weeks carries no weight at all.
WINDOW_DAYS = 56
MIN_ACTIONS = 10              # below this, onboarding preferences only
MIN_DISH_REJECTIONS = 2       # a dish must be rejected twice to be avoided
MIN_CUISINE_REQUESTS = 3      # typed requests before a cuisine is learned
MAX_LEARNED_CUISINES = 2
MAX_LIST = 5                  # cap per avoid/favour list, keeps prompts bounded

EVENT_KINDS = (
    'swapped_out',        # dish she rejected
    'swapped_in',         # replacement the MODEL chose (dish-level positive)
    'requested',          # dish she TYPED (cuisine-level intent)
    'favourited',
    'accepted',           # survived in a past plan (weak, cuisine-level only)
)


def _decay_weight(age_days):
    """Recent actions count more; nothing older than the window counts.

    Deliberately a step function rather than a curve — it is easier to
    reason about, easier to test, and the precision of an exponential
    would be false given how sparse these signals are."""
    if age_days < 0 or age_days > WINDOW_DAYS:
        return 0.0
    if age_days <= 14:
        return 1.0
    if age_days <= 28:
        return 0.6
    return 0.3


def _age_days(at, today):
    value = at.date() if hasattr(at, 'date') else at
    return (today - value).days


def _top(counter, limit=MAX_LIST):
    """Weighted counter -> list of {name, count}, heaviest first."""
    return [
        {'name': name, 'count': round(weight, 1)}
        for name, weight in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
        if weight > 0
    ][:limit]


def aggregate_events(events, today=None, chosen_cuisines=(), dismissed_cuisines=()):
    """PURE. Takes plain event dicts, returns the behaviour profile.

    Every number here is displayable — this dict is exactly what the
    "what Dayo has learned" screen renders. Nothing is inferred that we
    could not show the user.
    """
    today = today or date.today()
    chosen = {c.strip().lower() for c in chosen_cuisines if c and c.strip()}
    dismissed = {c.strip().lower() for c in dismissed_cuisines if c and c.strip()}

    rejected, favoured, requested_dishes = {}, {}, {}
    cuisine_accepted, cuisine_swapped, cuisine_requested = {}, {}, {}
    request_counts = {}           # unweighted, for the promotion threshold
    action_count = 0
    oldest = newest = None

    for e in events:
        weight = _decay_weight(_age_days(e['at'], today))
        if weight <= 0:
            continue
        kind = e.get('kind')
        name = (e.get('name') or '').strip()
        cuisine = (e.get('cuisine') or '').strip().lower()

        # 'accepted' is passive — it never counts as a user action, so it
        # cannot push someone over the MIN_ACTIONS threshold on its own.
        if kind != 'accepted':
            action_count += 1
            at = e['at'].date() if hasattr(e['at'], 'date') else e['at']
            oldest = at if oldest is None or at < oldest else oldest
            newest = at if newest is None or at > newest else newest

        if kind == 'swapped_out' and name:
            rejected[name] = rejected.get(name, 0) + weight
            if cuisine:
                cuisine_swapped[cuisine] = cuisine_swapped.get(cuisine, 0) + weight
        elif kind in ('swapped_in', 'favourited') and name:
            favoured[name] = favoured.get(name, 0) + weight
        elif kind == 'requested' and name:
            favoured[name] = favoured.get(name, 0) + weight
            requested_dishes[name] = requested_dishes.get(name, 0) + weight
            if cuisine:
                cuisine_requested[cuisine] = cuisine_requested.get(cuisine, 0) + weight
                request_counts[cuisine] = request_counts.get(cuisine, 0) + 1
        elif kind == 'accepted' and cuisine:
            cuisine_accepted[cuisine] = cuisine_accepted.get(cuisine, 0) + weight

    weeks = max(1.0, ((newest - oldest).days + 1) / 7.0) if oldest and newest else 1.0
    swaps = sum(1 for e in events
                if e.get('kind') == 'swapped_out'
                and _decay_weight(_age_days(e['at'], today)) > 0)

    # A cuisine is learned only when she TYPED dishes from it repeatedly,
    # it is not one she already chose, and she has not dismissed it.
    candidates = [
        {'cuisine': c, 'requests': n}
        for c, n in sorted(request_counts.items(), key=lambda kv: (-kv[1], kv[0]))
        if n >= MIN_CUISINE_REQUESTS and c not in chosen and c not in dismissed
    ][:MAX_LEARNED_CUISINES]

    return {
        'action_count': action_count,
        'weeks_observed': round(weeks, 1),
        'swap_rate_per_week': round(swaps / weeks, 1),
        'cuisine_accepted': {k: round(v, 1) for k, v in cuisine_accepted.items()},
        'cuisine_swapped': {k: round(v, 1) for k, v in cuisine_swapped.items()},
        'cuisine_requested': {k: round(v, 1) for k, v in cuisine_requested.items()},
        'dishes_rejected': [d for d in _top(rejected) if d['count'] >= MIN_DISH_REJECTIONS],
        'dishes_favoured': _top(favoured),
        'candidate_secondary_cuisines': candidates,
        'as_of': today.isoformat(),
    }


def collect_events(profile, today=None):
    """DB layer. Returns plain event dicts for the last WINDOW_DAYS."""
    from ..models import MealPlan

    today = today or date.today()
    since = today - timedelta(days=WINDOW_DAYS)
    events = []

    for log in profile.meal_swap_logs.filter(created_at__date__gte=since):
        events.append({
            'kind': 'swapped_out', 'name': log.rejected_meal,
            'cuisine': log.rejected_cuisine, 'at': log.created_at,
        })
        if log.chosen_meal:
            events.append({
                # Typed requests carry cuisine intent; model-chosen swaps
                # do not, because the model picks from her own cuisine.
                'kind': 'requested' if log.was_user_request else 'swapped_in',
                'name': log.chosen_meal, 'cuisine': log.chosen_cuisine,
                'at': log.created_at,
            })

    for fav in profile.favourite_meals.filter(created_at__date__gte=since):
        events.append({'kind': 'favourited', 'name': fav.meal_name,
                       'cuisine': '', 'at': fav.created_at})

    # Meals that survived in past plans — swaps rewrite the MealPlan row,
    # so what remains is what she accepted.
    for meal in MealPlan.objects.filter(
        day_plan__profile=profile,
        day_plan__date__gte=since,
        day_plan__date__lt=today,
    ).exclude(cuisine=''):
        events.append({'kind': 'accepted', 'name': meal.name,
                       'cuisine': meal.cuisine, 'at': meal.day_plan.date})

    return events


def build_behaviour_profile(profile, today=None):
    """collect + aggregate, with the profile's own cuisines for context."""
    today = today or date.today()
    chosen = _stated_cuisines(profile)
    return aggregate_events(
        collect_events(profile, today), today,
        chosen_cuisines=chosen,
        dismissed_cuisines=profile.dismissed_learned_cuisines or [],
    )


def sync_learned_cuisines(profile, today=None):
    """Promote qualifying candidates onto the profile. Call before generating.

    Note the two thresholds are deliberately independent. MIN_ACTIONS gates
    the fuzzy signals (which dishes to favour or avoid), which only mean
    something in aggregate. Cuisine promotion needs just MIN_CUISINE_REQUESTS
    because typing three dishes from the same cuisine is specific and
    unambiguous on its own — waiting for ten actions would ignore what she
    plainly asked for.

    Writes with a queryset update rather than save() on purpose: save()
    would bump updated_at, and the weighting policy reads updated_at to mean
    "the user edited her settings". Learning something must not look like
    the user restating her preferences.
    """
    from ..models import UserProfile

    behaviour = build_behaviour_profile(profile, today)
    learned = [c['cuisine'] for c in behaviour['candidate_secondary_cuisines']][:MAX_LEARNED_CUISINES]
    if sorted(learned) != sorted(profile.learned_secondary_cuisines or []):
        UserProfile.objects.filter(pk=profile.pk).update(learned_secondary_cuisines=learned)
        profile.learned_secondary_cuisines = learned
    return learned


def _stated_cuisines(profile):
    """Everything the user explicitly chose — never includes learned ones."""
    out = list(profile.cuisine_preferences or [])
    custom = (profile.custom_cuisines or '').strip()
    if custom:
        out.extend(c.strip() for c in custom.split(','))
    out.extend(profile.secondary_cuisines or [])
    return [c.strip().lower() for c in out if c and c.strip()]


def build_generation_context(profile, behaviour, now=None):
    """THE weighting policy — the one place behaviour meets onboarding.

    PURE with respect to the model: no LLM, no generation. Returns the
    structured context the prompt renders.

    Onboarding constrains, behaviour informs. Behaviour may avoid dishes,
    favour dishes and add a learned secondary cuisine — it can never relax
    an exclusion, drop a dietary restriction, or demote a stated cuisine.
    """
    stated = _stated_cuisines(profile)
    base = {
        'behaviour_applied': False,
        'actions_needed': max(0, MIN_ACTIONS - behaviour['action_count']),
        'avoid_dishes': [],
        'favour_dishes': [],
        'learned_cuisines': [],
        'swap_rate_per_week': behaviour['swap_rate_per_week'],
    }

    # Not enough deliberate actions yet — onboarding only. Most users sit
    # here for weeks, and that is the correct conservative default.
    if behaviour['action_count'] < MIN_ACTIONS:
        return base

    # Re-stating preferences in settings outranks behaviour: if she edited
    # her profile more recently than the newest signal, drop the negative
    # half (she just told us what she wants) and keep the positive half.
    suppress = True
    if now and getattr(profile, 'updated_at', None):
        updated = profile.updated_at.date() if hasattr(profile.updated_at, 'date') else profile.updated_at
        suppress = updated <= _newest_signal_date(behaviour, now)

    learned = [
        c['cuisine'] for c in behaviour['candidate_secondary_cuisines']
        if c['cuisine'] not in stated
    ][:MAX_LEARNED_CUISINES]

    base.update({
        'behaviour_applied': True,
        'actions_needed': 0,
        'avoid_dishes': [d['name'] for d in behaviour['dishes_rejected']][:MAX_LIST] if suppress else [],
        'favour_dishes': [d['name'] for d in behaviour['dishes_favoured']][:MAX_LIST],
        'learned_cuisines': learned,
    })
    return base


def _newest_signal_date(behaviour, now):
    """as_of is the aggregation date; signals cannot be newer than it."""
    return now.date() if hasattr(now, 'date') else now


def render_context_section(context):
    """The one prompt section this feature adds. Returns None when there is
    nothing learned, so the prompt stays unchanged for new users."""
    if not context.get('behaviour_applied'):
        return None
    lines = ['## What this household has actually chosen (learned from use)']
    if context['avoid_dishes']:
        lines.append('- Repeatedly swapped away — do NOT plan these: %s'
                     % ', '.join(context['avoid_dishes']))
    if context['favour_dishes']:
        lines.append('- Asked for or kept — lean towards these and similar: %s'
                     % ', '.join(context['favour_dishes']))
    if context['learned_cuisines']:
        lines.append(
            '- She repeatedly asks for %s dishes, so include 2-3 of them per '
            'week alongside her stated cuisines (never instead of them).'
            % ', '.join(c.title() for c in context['learned_cuisines'])
        )
    if len(lines) == 1:
        return None
    lines.append('These are preferences, not constraints: dietary '
                 'restrictions and forbidden ingredients still override them.')
    return '\n'.join(lines) + '\n'
