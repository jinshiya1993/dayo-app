"""Builds the ctx dict that every rule receives.

Rules need to know WHO a plan was generated for -- what's banned, which
cuisines were chosen -- without reaching into Django models themselves.
This keeps rules pure functions over plain data, so they can be unit-tested
with a fake profile and reused on plan_data pulled from anywhere.
"""


def build_context(profile):
    """Extract the facts rules care about from a UserProfile (or anything
    with the same attributes -- tests pass a fake).

    Returns:
        banned           : lowercased exclusion strings ("nuts", "shellfish")
        allowed_cuisines : lowercased union of primary + custom + secondary
                           cuisines; EMPTY means the user chose nothing and
                           no cuisine rule applies
        user_type        : "homemaker" | "parent" | "new_mom"
        family_size      : int, at least 1
    """
    banned = [str(e).strip().lower() for e in (profile.exclusions or []) if str(e).strip()]

    cuisines = list(profile.cuisine_preferences or [])
    custom = (profile.custom_cuisines or '').strip()
    if custom:
        # custom_cuisines is free text, possibly comma-separated
        cuisines.extend(c.strip() for c in custom.split(','))
    cuisines.extend(profile.secondary_cuisines or [])
    allowed = sorted({c.strip().lower() for c in cuisines if c and c.strip()})

    return {
        'banned': banned,
        'allowed_cuisines': allowed,
        'user_type': profile.user_type,
        'family_size': max(1, profile.family_size or 1),
    }
