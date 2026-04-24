# ─── Section Registry ─────────────────────────────────────────────
# Every dashboard section that exists in the app.
# Used by:
#   - DynamicDashboard.jsx to render sections
#   - CustomiseDashboard.jsx to show available sections
#   - Onboarding to build the initial custom_layout
#   - GET /api/v1/sections/ endpoint

SECTION_REGISTRY = {
    # ── Shared sections (any user type) ──────────────────────────
    'meal_cards': {
        'label': "Today's meals",
        'subtitle': 'Breakfast, lunch and dinner',
        'icon': 'meals',
        'emoji': '🍳',
        'lockable': False,
        'category': 'essentials',
    },
    'grocery': {
        'label': 'Grocery list',
        'subtitle': "This week's shopping",
        'icon': 'grocery',
        'emoji': '🛒',
        'lockable': False,
        'category': 'essentials',
    },
    'exercise': {
        'label': 'Fitness today',
        'subtitle': 'Gym, yoga or workout',
        'icon': 'exercise',
        'emoji': '🏋️',
        'lockable': False,
        'category': 'wellness',
    },
    'me_time': {
        'label': 'Your time tonight',
        'subtitle': 'Protected personal time',
        'icon': 'me_time',
        'emoji': '🧘',
        'lockable': False,
        'category': 'wellness',
    },
    'selfcare_list': {
        'label': 'Your wellbeing',
        'subtitle': 'Self care activities',
        'icon': 'selfcare',
        'emoji': '💆',
        'lockable': False,
        'category': 'wellness',
    },
    'housework': {
        'label': 'Housework',
        'subtitle': 'Daily tasks',
        'icon': 'housework',
        'emoji': '🧹',
        'lockable': False,
        'category': 'tasks',
    },
    'errands': {
        'label': 'Errands',
        'subtitle': 'Things to do outside',
        'icon': 'errands',
        'emoji': '📋',
        'lockable': False,
        'category': 'tasks',
    },
    'notes': {
        'label': 'Daily note',
        'subtitle': 'AI tip for today',
        'icon': 'notes',
        'emoji': '💡',
        'lockable': False,
        'category': 'other',
    },

    # ── Schedule section (all user types) ───────────────────────
    'schedule_alert': {
        'label': "Today's schedule",
        'subtitle': 'Appointments, drop-offs, and events',
        'icon': 'schedule',
        'emoji': '📅',
        'lockable': False,
        'category': 'essentials',
    },
    'class_alert': {
        'label': 'Class alerts',
        'subtitle': 'Pickup and drop-off times',
        'icon': 'class',
        'emoji': '🎒',
        'lockable': False,
        'category': 'kids',
    },
    'kids_activities': {
        'label': 'Kids activities',
        'subtitle': 'Age-appropriate activities',
        'icon': 'kids',
        'emoji': '🎨',
        'lockable': False,
        'category': 'kids',
    },
    'evening_routine': {
        'label': 'Evening routine',
        'subtitle': 'After-work checklist',
        'icon': 'evening',
        'emoji': '🌙',
        'lockable': False,
        'category': 'routine',
    },

    # ── New mom sections ─────────────────────────────────────────
    'baby_schedule': {
        'label': "Baby's day",
        'subtitle': 'Feed, sleep, nappy cycle',
        'icon': 'baby',
        'emoji': '👶',
        'lockable': False,
        'category': 'baby',
    },
    'mom_rest': {
        'label': 'Your rest windows',
        'subtitle': 'Sleep when baby sleeps',
        'icon': 'rest',
        'emoji': '😴',
        'lockable': False,
        'category': 'baby',
    },
    'mom_meals': {
        'label': 'Your meals',
        'subtitle': 'Quick one-hand friendly meals',
        'icon': 'meals',
        'emoji': '🥗',
        'lockable': False,
        'category': 'baby',
    },
    'recovery_exercise': {
        'label': 'Recovery exercise',
        'subtitle': 'Gentle walks and postpartum yoga',
        'icon': 'recovery',
        'emoji': '🚶‍♀️',
        'lockable': False,
        'category': 'wellness',
    },
    'milestones': {
        'label': 'Baby milestones',
        'subtitle': 'What to expect this month',
        'icon': 'milestones',
        'emoji': '🌟',
        'lockable': False,
        'category': 'baby',
    },
    'essentials': {
        'label': 'Essentials check',
        'subtitle': 'Nappies, wipes, formula',
        'icon': 'essentials',
        'emoji': '✅',
        'lockable': False,
        'category': 'baby',
    },

    # ── Work sections (working parents) ──────────────────────────
    'priorities': {
        'label': "Today's priorities",
        'subtitle': 'Top 3 tasks',
        'icon': 'priorities',
        'emoji': '📌',
        'lockable': False,
        'category': 'work',
    },
}

# ─── Default layouts per user type ────────────────────────────────
# These are used to build the INITIAL custom_layout when a user
# completes onboarding and has no custom_layout yet.
DEFAULT_LAYOUTS = {
    'parent': [
        {'key': 'schedule_alert', 'visible': True, 'locked': False},
        {'key': 'meal_cards', 'visible': True, 'locked': False},
        {'key': 'grocery', 'visible': True, 'locked': False},
        {'key': 'kids_activities', 'visible': True, 'locked': False},
        {'key': 'housework', 'visible': True, 'locked': False},
        {'key': 'me_time', 'visible': True, 'locked': False},
        {'key': 'notes', 'visible': True, 'locked': False},
    ],
    'new_mom': [
        {'key': 'schedule_alert', 'visible': True, 'locked': False},
        {'key': 'meal_cards', 'visible': True, 'locked': False},
        {'key': 'essentials', 'visible': True, 'locked': False},
        {'key': 'grocery', 'visible': True, 'locked': False},
        {'key': 'exercise', 'visible': True, 'locked': False},
        {'key': 'selfcare_list', 'visible': True, 'locked': False},
        {'key': 'housework', 'visible': True, 'locked': False},
        {'key': 'me_time', 'visible': True, 'locked': False},
        {'key': 'notes', 'visible': True, 'locked': False},
    ],
    'homemaker': [
        {'key': 'schedule_alert', 'visible': True, 'locked': False},
        {'key': 'meal_cards', 'visible': True, 'locked': False},
        {'key': 'grocery', 'visible': True, 'locked': False},
        {'key': 'housework', 'visible': True, 'locked': False},
        {'key': 'me_time', 'visible': True, 'locked': False},
        {'key': 'notes', 'visible': True, 'locked': False},
    ],
    'working_mom': [
        {'key': 'schedule_alert', 'visible': True, 'locked': False},
        {'key': 'meal_cards', 'visible': True, 'locked': False},
        {'key': 'grocery', 'visible': True, 'locked': False},
        {'key': 'priorities', 'visible': True, 'locked': False},
        {'key': 'kids_activities', 'visible': True, 'locked': False},
        {'key': 'evening_routine', 'visible': True, 'locked': False},
        {'key': 'me_time', 'visible': True, 'locked': False},
        {'key': 'notes', 'visible': True, 'locked': False},
    ],
}

# ─── Module → section key mapping ─────────────────────────────────
# When the AI extracts "exercise" from onboarding, this maps it to
# the correct section key to add to custom_layout.
MODULE_TO_SECTION = {
    'meals': 'meal_cards',
    'meal': 'meal_cards',
    'cooking': 'meal_cards',
    'grocery': 'grocery',
    'exercise': 'exercise',
    'gym': 'exercise',
    'yoga': 'exercise',
    'walk': 'recovery_exercise',
    'selfcare': 'selfcare_list',
    'self_care': 'selfcare_list',
    'self care': 'selfcare_list',
    'me_time': 'me_time',
    'kids_activities': 'kids_activities',
    'kids': 'kids_activities',
    'kids_classes': 'schedule_alert',
    'school': 'schedule_alert',
    'schedule': 'schedule_alert',
    'appointments': 'schedule_alert',
    'events': 'schedule_alert',
    'housework': 'housework',
    'cleaning': 'housework',
    'errands': 'errands',
    'baby_schedule': 'baby_schedule',
    'baby_care': 'baby_schedule',
    'baby': 'baby_schedule',
    'mom_rest': 'mom_rest',
    'recovery': 'recovery_exercise',
    'milestones': 'milestones',
    'essentials': 'essentials',
    'priorities': 'priorities',
    'work': 'priorities',
    'evening_routine': 'evening_routine',
}


def build_initial_layout(profile):
    """Derive a dashboard layout from the user's actual life data.

    Gates each section on profile.works_outside_home plus the set of
    children age bands (postpartum <3mo, infant <24mo, kid 2-12yr). There
    is no single user_type label driving the layout anymore — a working
    mom with a newborn and a 5-year-old gets the union of all the
    relevant sections.
    """
    from datetime import date

    children = list(profile.children.all()) if profile.pk else []
    works = bool(profile.works_outside_home)

    today = date.today()

    def months_old(child):
        dob = child.date_of_birth
        return (today.year - dob.year) * 12 + (today.month - dob.month)

    has_postpartum = any(months_old(c) < 3 for c in children)
    has_infant = any(months_old(c) < 24 for c in children)
    # has_kid covers 2y through 12y — the 2-3y band is story-only, the
    # generator handles that. class_alert rides along with kids_activities.
    has_kid = any(2 <= c.age < 13 for c in children)

    ordered = []
    ordered.append('schedule_alert')

    if works:
        ordered.append('priorities')

    # Exactly ONE meal section per dashboard. mom_meals is the one-hand
    # friendly variant saved to plan_data.mom_meals for user_type='new_mom';
    # everyone else reads from plan_data.meals via meal_cards.
    ordered.append('mom_meals' if has_infant else 'meal_cards')

    if has_infant:
        ordered += ['baby_schedule', 'essentials', 'milestones']

    if has_postpartum:
        ordered += ['mom_rest', 'recovery_exercise', 'selfcare_list']

    if has_kid:
        ordered += ['kids_activities', 'class_alert']

    ordered.append('grocery')
    ordered.append('housework')

    if works and (has_infant or has_kid):
        ordered.append('evening_routine')

    ordered += ['me_time', 'notes']

    # De-dupe while preserving order — easy way to tolerate the overlap
    # between has_postpartum and has_infant (postpartum is a strict subset).
    seen = set()
    layout = []
    for key in ordered:
        if key in seen or key not in SECTION_REGISTRY:
            continue
        seen.add(key)
        layout.append({'key': key, 'visible': True, 'locked': False})
    return layout
