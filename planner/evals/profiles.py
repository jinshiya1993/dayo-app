"""Golden profiles -- the fixed test inputs every eval run uses.

Eight synthetic households spanning the matrix Dayo actually serves:
user type x cuisine choice x exclusions x family size. The inputs never
change between runs, so when a pass rate moves, the PROMPT moved it.

sync_profiles() get_or_creates these as real Django users (username prefix
"eval_") so the existing generators run unmodified. Meant for the local dev
database only -- never point DATABASE_URL at production while running evals.
"""

from datetime import date, timedelta

GOLDEN_PROFILES = [
    {
        # The MeenaKumar regression: North Indian only -- sambar or hummus
        # appearing here is the exact past failure the cuisine rule catches.
        'username': 'eval_north_indian_family',
        'display_name': 'Meera',
        'profile': {
            'cuisine_preferences': ['North Indian'],
            'family_size': 4,
            'exclusions': [],
        },
        'members': [
            {'role': 'partner', 'name': 'Arun', 'age_years': 36},
            {'role': 'child', 'name': 'Diya', 'age_years': 8},
            {'role': 'child', 'name': 'Kabir', 'age_years': 4},
        ],
    },
    {
        'username': 'eval_kerala_homemaker',
        'display_name': 'Lekshmi',
        'profile': {
            'cuisine_preferences': ['Kerala', 'South Indian'],
            'family_size': 2,
            'exclusions': [],
        },
        'members': [
            {'role': 'partner', 'name': 'Suresh', 'age_years': 40},
        ],
    },
    {
        # Exclusions under pressure: nut and dairy allergies in a cuisine
        # that loves both -- the forbidden_ingredients rule earns its keep.
        'username': 'eval_allergy_household',
        'display_name': 'Sana',
        'profile': {
            'cuisine_preferences': ['North Indian'],
            'secondary_cuisines': ['Continental'],
            'family_size': 3,
            'exclusions': ['nuts', 'peanut', 'cashew', 'dairy', 'milk', 'paneer'],
        },
        'members': [
            {'role': 'partner', 'name': 'Omar', 'age_years': 38},
            {'role': 'child', 'name': 'Zara', 'age_years': 6},
        ],
    },
    {
        # Halal + labelling: compliance must come from ingredient choice,
        # and the word "Halal" must never be written into a dish.
        'username': 'eval_halal_family',
        'display_name': 'Ayesha',
        'profile': {
            'cuisine_preferences': ['Arabic food', 'North Indian'],
            'dietary_restrictions': ['Halal'],
            'family_size': 5,
            'exclusions': ['pork'],
        },
        'members': [
            {'role': 'partner', 'name': 'Khalid', 'age_years': 41},
            {'role': 'child', 'name': 'Yusuf', 'age_years': 10},
            {'role': 'child', 'name': 'Maryam', 'age_years': 7},
            {'role': 'grandparent', 'name': 'Fatima', 'age_years': 66},
        ],
    },
    {
        'username': 'eval_mediterranean_single',
        'display_name': 'Elena',
        'profile': {
            'cuisine_preferences': ['Mediterranean'],
            'family_size': 1,
            'exclusions': [],
        },
        'members': [],
    },
    {
        # Mixed primary + secondary: Thai may appear 1-2x a week, nothing else
        # outside the set -- tests the "occasional cuisines" half of the rule.
        'username': 'eval_mixed_cuisines',
        'display_name': 'Nisha',
        'profile': {
            'cuisine_preferences': ['South Indian', 'North Indian'],
            'secondary_cuisines': ['Thai'],
            'family_size': 4,
            'exclusions': [],
        },
        'members': [
            {'role': 'partner', 'name': 'Vikram', 'age_years': 39},
            {'role': 'child', 'name': 'Anya', 'age_years': 9},
            {'role': 'child', 'name': 'Rohan', 'age_years': 5},
        ],
    },
    {
        # New mom: mom_meals plan_data path, infant member, postpartum rules.
        'username': 'eval_new_mom',
        'display_name': 'Priya',
        'profile': {
            'cuisine_preferences': ['Kerala'],
            'family_size': 3,
            'exclusions': [],
            'is_breastfeeding': True,
        },
        'members': [
            {'role': 'partner', 'name': 'Anoop', 'age_years': 34},
            {'role': 'child', 'name': 'Ammu', 'age_months': 4},
        ],
    },
    {
        # No cuisine chosen at all -- the cuisine rule must NOT fire, and
        # generation should still hold every other property.
        'username': 'eval_no_preferences',
        'display_name': 'Clara',
        'profile': {
            'cuisine_preferences': [],
            'family_size': 2,
            'exclusions': [],
        },
        'members': [
            {'role': 'roommate', 'name': 'Jo', 'age_years': 29},
        ],
    },
]

# Cheap default for `manage.py run_evals` with no --profiles flag: one
# cuisine-sensitive household and the allergy one -- the two highest-risk
# rule families for a single Gemini call each.
DEFAULT_PROFILE_NAMES = ['eval_north_indian_family', 'eval_allergy_household']


def sync_profiles(names=None):
    """get_or_create the golden users/profiles/members. Idempotent: existing
    eval users are updated in place so edits to this file take effect.
    Returns the list of UserProfile objects, in GOLDEN_PROFILES order."""
    from django.contrib.auth.models import User
    from ..models import HouseholdMember, UserProfile

    today = date.today()
    wanted = [
        g for g in GOLDEN_PROFILES
        if names is None or g['username'] in names
    ]
    profiles = []
    for g in wanted:
        user, _ = User.objects.get_or_create(
            username=g['username'],
            defaults={'email': '%s@eval.local' % g['username']},
        )
        profile, _ = UserProfile.objects.get_or_create(
            user=user, defaults={'display_name': g['display_name']},
        )
        profile.display_name = g['display_name']
        for field, value in g['profile'].items():
            setattr(profile, field, value)
        profile.onboarding_complete = True
        profile.save()

        # Rebuild members each sync so age edits here propagate.
        profile.members.all().delete()
        has_infant = False
        for m in g['members']:
            if 'age_months' in m:
                dob = today - timedelta(days=30 * m['age_months'])
                has_infant = m['age_months'] < 24
            else:
                dob = today - timedelta(days=365 * m['age_years'] + 180)
            HouseholdMember.objects.create(
                parent=profile, role=m['role'], name=m['name'],
                date_of_birth=dob,
            )

        has_kid = any(2 <= (m.get('age_years') or 0) < 13 for m in g['members'])
        profile.user_type = 'new_mom' if has_infant else ('parent' if has_kid else 'homemaker')
        profile.save()
        # A just-created profile holds TimeField defaults as raw strings
        # ('06:00'); the prompt builders call .strftime on them. Reload so
        # every field has its real Python type.
        profile.refresh_from_db()
        profiles.append(profile)
    return profiles
