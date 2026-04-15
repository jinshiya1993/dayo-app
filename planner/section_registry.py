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
    'meal_compact': {
        'label': 'Meals',
        'subtitle': 'Quick meal overview',
        'icon': 'meals',
        'emoji': '🍽',
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

    # ── Professional sections ────────────────────────────────────
    'deep_work': {
        'label': 'Deep work block',
        'subtitle': 'Protected focus time',
        'icon': 'focus',
        'emoji': '🎯',
        'lockable': False,
        'category': 'work',
    },
    'priorities': {
        'label': "Today's priorities",
        'subtitle': 'Top 3 tasks',
        'icon': 'priorities',
        'emoji': '📌',
        'lockable': False,
        'category': 'work',
    },
    'meetings': {
        'label': 'Meetings',
        'subtitle': "Today's calls and meetings",
        'icon': 'meetings',
        'emoji': '🤝',
        'lockable': False,
        'category': 'work',
    },
    'end_of_day': {
        'label': 'End of day',
        'subtitle': 'Stop work reminder',
        'icon': 'end',
        'emoji': '🌅',
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
    'professional': [
        {'key': 'schedule_alert', 'visible': True, 'locked': False},
        {'key': 'deep_work', 'visible': True, 'locked': False},
        {'key': 'priorities', 'visible': True, 'locked': False},
        {'key': 'meetings', 'visible': True, 'locked': False},
        {'key': 'meal_compact', 'visible': True, 'locked': False},
        {'key': 'grocery', 'visible': True, 'locked': False},
        {'key': 'exercise', 'visible': True, 'locked': False},
        {'key': 'end_of_day', 'visible': True, 'locked': False},
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
    'deep_work': 'deep_work',
    'priorities': 'priorities',
    'work': 'priorities',
    'meetings': 'meetings',
    'work_schedule': 'deep_work',
    'commute': 'end_of_day',
    'evening_routine': 'evening_routine',
}


def build_initial_layout(user_type, planning_modules=None):
    """
    Build the initial custom_layout for a new user.
    Layer 1: Start with user_type defaults
    Layer 2: Add/modify based on AI-extracted planning_modules
    Returns a list of {key, visible, locked, added_by_ai} dicts.
    """
    # Layer 1 — defaults
    layout = [item.copy() for item in DEFAULT_LAYOUTS.get(user_type, DEFAULT_LAYOUTS['homemaker'])]
    existing_keys = {item['key'] for item in layout}

    if not planning_modules:
        return layout

    # Layer 2 — add sections from AI-extracted modules
    for mod in planning_modules:
        mod_lower = mod.lower().replace(' ', '_')
        section_key = MODULE_TO_SECTION.get(mod_lower)

        if section_key and section_key not in existing_keys:
            # AI detected the user wants this — add it
            layout.append({
                'key': section_key,
                'visible': True,
                'locked': False,
                'added_by_ai': True,
            })
            existing_keys.add(section_key)

    return layout
