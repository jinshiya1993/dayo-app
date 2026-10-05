"""Test suite for Dayo.

Run with:  python manage.py test

Grouped into:
  - Unit tests    -> pure logic, no DB/network (fast, reliable)
  - API tests     -> hit real endpoints via a throwaway test database
  - Security test -> a user must not see another user's data

The LLM (Gemini) is never called here. AI-generation flows are covered
separately by mocking Gemini so tests stay fast and deterministic.
"""

from datetime import date, timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from rest_framework.test import APITestCase

from planner.views import _derive_user_type
from planner.models import UserProfile


# ---------------------------------------------------------------------------
# Unit tests: _derive_user_type
# ---------------------------------------------------------------------------
class _FakeChild:
    """Minimal stand-in for a HouseholdMember.

    _derive_user_type only reads `.date_of_birth` and `.age`, so we can test
    its logic without touching the database at all -- this is what makes it a
    true *unit* test: fast and isolated.
    """

    def __init__(self, dob, age):
        self.date_of_birth = dob
        self.age = age


class DeriveUserTypeTests(TestCase):
    """The rule that decides which dashboard a user gets. Critical logic."""

    def _child_months_ago(self, months, age):
        dob = date.today() - timedelta(days=int(months * 30.4))
        return _FakeChild(dob, age)

    def test_no_children_is_homemaker(self):
        self.assertEqual(_derive_user_type([]), 'homemaker')

    def test_infant_is_new_mom(self):
        infant = self._child_months_ago(months=10, age=0)
        self.assertEqual(_derive_user_type([infant]), 'new_mom')

    def test_school_age_child_is_parent(self):
        kid = self._child_months_ago(months=60, age=5)
        self.assertEqual(_derive_user_type([kid]), 'parent')

    def test_infant_takes_precedence_over_older_kid(self):
        # A family with both an infant and an older kid should stay 'new_mom'
        # so postpartum tailoring is preserved.
        infant = self._child_months_ago(months=6, age=0)
        kid = self._child_months_ago(months=96, age=8)
        self.assertEqual(_derive_user_type([infant, kid]), 'new_mom')

    def test_teenager_is_homemaker(self):
        # Boundary check: age 13 is NOT counted as a young kid (2 <= age < 13).
        teen = self._child_months_ago(months=156, age=13)
        self.assertEqual(_derive_user_type([teen]), 'homemaker')


# ---------------------------------------------------------------------------
# API tests: auth + health
# ---------------------------------------------------------------------------
class AuthAPITests(APITestCase):

    def test_register_creates_user_and_profile(self):
        resp = self.client.post(
            '/api/v1/auth/register/',
            {'username': 'alice', 'email': 'alice@example.com', 'password': 'supersecret1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 201)
        self.assertTrue(User.objects.filter(username='alice').exists())
        # RegisterView must auto-create a profile for the new user.
        user = User.objects.get(username='alice')
        self.assertTrue(UserProfile.objects.filter(user=user).exists())

    def test_login_with_correct_password_succeeds(self):
        User.objects.create_user(username='bob', password='supersecret1')
        resp = self.client.post(
            '/api/v1/auth/login/',
            {'username': 'bob', 'password': 'supersecret1'},
            format='json',
        )
        self.assertEqual(resp.status_code, 200)

    def test_login_with_wrong_password_is_rejected(self):
        User.objects.create_user(username='carol', password='supersecret1')
        resp = self.client.post(
            '/api/v1/auth/login/',
            {'username': 'carol', 'password': 'WRONGpassword'},
            format='json',
        )
        # A healthy app returns 401 (bad credentials) -- NOT a 500 crash.
        self.assertEqual(resp.status_code, 401)


class HealthCheckTests(APITestCase):

    def test_health_reports_ok(self):
        resp = self.client.get('/api/v1/health/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['status'], 'ok')
        self.assertEqual(resp.data['database'], 'ok')


# ---------------------------------------------------------------------------
# Security: auth is required + users are isolated
# ---------------------------------------------------------------------------
class ProfileAccessTests(APITestCase):

    def test_profile_requires_authentication(self):
        resp = self.client.get('/api/v1/profile/')
        # DRF denies unauthenticated access with 401 or 403 depending on auth
        # class; either is correct -- what matters is it is NOT 200.
        self.assertIn(resp.status_code, (401, 403))

    def test_logged_in_user_gets_their_own_profile(self):
        user = User.objects.create_user(username='dave', password='supersecret1')
        UserProfile.objects.create(user=user, display_name='Dave')
        self.client.force_authenticate(user=user)

        resp = self.client.get('/api/v1/profile/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['username'], 'dave')


# ---------------------------------------------------------------------------
# Unit tests: grocery quantity logic (no DB, no network)
# ---------------------------------------------------------------------------
from planner.services.grocery_generator import _adult_equivalents, _retail_quantity


class _FakeMember:
    def __init__(self, age):
        self.age = age


class _FakeMembers:
    def __init__(self, ages):
        self._members = [_FakeMember(a) for a in ages]

    def all(self):
        return self._members


class _FakeProfile:
    def __init__(self, family_size, member_ages=()):
        self.family_size = family_size
        self.members = _FakeMembers(member_ages)


class AdultEquivalentsTests(TestCase):
    """2 adults + small kids should shop like fewer than a headcount of 4."""

    def test_infant_child_and_partner(self):
        # user (1.0) + infant (0.2) + 8yo (0.6) + partner (1.0) = 2.8
        profile = _FakeProfile(family_size=4, member_ages=[1, 8, 35])
        self.assertAlmostEqual(_adult_equivalents(profile), 2.8)

    def test_no_members_falls_back_to_family_size(self):
        # Nobody added in onboarding: unlisted people count as full adults.
        profile = _FakeProfile(family_size=4)
        self.assertAlmostEqual(_adult_equivalents(profile), 4.0)

    def test_partial_members_fills_gap_with_adults(self):
        # family_size 5 but only one child listed: user + child + 3 unlisted adults.
        profile = _FakeProfile(family_size=5, member_ages=[6])
        self.assertAlmostEqual(_adult_equivalents(profile), 1.0 + 0.6 + 3.0)

    def test_teenager_counts_as_adult(self):
        profile = _FakeProfile(family_size=2, member_ages=[15])
        self.assertAlmostEqual(_adult_equivalents(profile), 2.0)

    def test_never_below_one(self):
        profile = _FakeProfile(family_size=None)
        self.assertAlmostEqual(_adult_equivalents(profile), 1.0)


class RetailQuantityTests(TestCase):
    """Quantities must be supermarket-purchasable and scale with appetite."""

    def test_single_piece_fruit_scales_with_eaters(self):
        self.assertEqual(_retail_quantity('Apple', 'produce', '1 pc', 1), '250 g')
        self.assertEqual(_retail_quantity('Apple', 'produce', '1 pc', 2.8), '750 g')
        self.assertEqual(_retail_quantity('Apple', 'produce', '1 pc', 5), '1.5 kg')

    def test_fruit_quantity_is_capped(self):
        self.assertEqual(_retail_quantity('Apple', 'produce', '1 pc', 10), '2 kg')

    def test_small_fruit_weight_is_raised_to_household_floor(self):
        self.assertEqual(_retail_quantity('Apples', 'produce', '250 g', 5), '1.5 kg')

    def test_fruit_with_no_quantity_gets_a_derived_one(self):
        self.assertEqual(_retail_quantity('Mango', 'produce', '', 2), '500 g')

    def test_piece_vegetables_get_milder_floor(self):
        self.assertEqual(_retail_quantity('Cucumber', 'produce', '1 pc', 5), '500 g')

    def test_weight_based_vegetables_are_trusted(self):
        # Meal-driven weights aren't inflated by family size.
        self.assertEqual(_retail_quantity('Carrot', 'produce', '500 g', 5), '500 g')

    def test_recipe_units_convert_to_grams(self):
        self.assertEqual(_retail_quantity('Rolled oats', 'grains', '2 cups', 1), '500 g')

    def test_eggs_round_to_real_packs(self):
        self.assertEqual(_retail_quantity('Eggs', 'protein', '8 pcs', 1), '12 pcs')

    def test_herbs_are_always_a_bunch(self):
        self.assertEqual(_retail_quantity('Cilantro', 'produce', '50 g', 5), '1 bunch')

    def test_liquids_round_to_half_litre_steps(self):
        self.assertEqual(_retail_quantity('Milk', 'dairy', '1.3 L', 1), '1.5 L')

    def test_whole_fruits_without_piece_weight_stay_pieces(self):
        self.assertEqual(_retail_quantity('Watermelon', 'produce', '1 pc', 5), '1 pc')

    def test_pack_units_pass_through(self):
        self.assertEqual(_retail_quantity('Bread', 'grains', '1 pkt', 5), '1 pkt')

    def test_unparseable_quantity_left_alone(self):
        self.assertEqual(_retail_quantity('Paneer', 'dairy', 'as needed', 3), 'as needed')


# ---------------------------------------------------------------------------
# Unit tests: eval harness (planner/evals/) — no LLM calls, fixture data only
# ---------------------------------------------------------------------------
from planner.evals.context import build_context
from planner.evals.report import aggregate, prompt_version
from planner.evals.rules import (
    grocery_rule_no_leftover_items,
    grocery_rule_no_pantry_staples,
    grocery_rule_retail_quantities,
    rule_cuisine_adherence,
)


class _FakeEvalProfile:
    def __init__(self, exclusions=None, cuisines=None, custom='', secondary=None,
                 user_type='homemaker', family_size=2):
        self.exclusions = exclusions or []
        self.cuisine_preferences = cuisines or []
        self.custom_cuisines = custom
        self.secondary_cuisines = secondary or []
        self.user_type = user_type
        self.family_size = family_size


def _plan_with(name, slot='lunch'):
    return {'meals': {slot: {'name': name}}}


class BuildContextTests(TestCase):

    def test_exclusions_lowercased(self):
        ctx = build_context(_FakeEvalProfile(exclusions=['Nuts', ' Shellfish ']))
        self.assertEqual(ctx['banned'], ['nuts', 'shellfish'])

    def test_cuisines_are_a_union_of_all_three_fields(self):
        ctx = build_context(_FakeEvalProfile(
            cuisines=['North Indian'], custom='Parsi, Goan', secondary=['Thai']))
        self.assertEqual(ctx['allowed_cuisines'],
                         ['goan', 'north indian', 'parsi', 'thai'])

    def test_empty_profile_yields_empty_sets(self):
        ctx = build_context(_FakeEvalProfile(family_size=None))
        self.assertEqual(ctx['allowed_cuisines'], [])
        self.assertEqual(ctx['banned'], [])
        self.assertEqual(ctx['family_size'], 1)


class CuisineAdherenceRuleTests(TestCase):

    def test_sambar_flags_for_north_indian_only_home(self):
        ctx = {'allowed_cuisines': ['north indian']}
        violations = rule_cuisine_adherence(
            _plan_with('Sambar with Brown Rice'), ctx)
        self.assertEqual(len(violations), 1)
        self.assertIn('Sambar', violations[0])

    def test_sambar_passes_for_south_indian_home(self):
        ctx = {'allowed_cuisines': ['south indian', 'kerala']}
        self.assertEqual(
            rule_cuisine_adherence(_plan_with('Sambar with Brown Rice'), ctx), [])

    def test_hummus_snack_flags_without_middle_eastern(self):
        ctx = {'allowed_cuisines': ['north indian']}
        violations = rule_cuisine_adherence(
            _plan_with('Carrot Sticks with Hummus', slot='snack'), ctx)
        self.assertEqual(len(violations), 1)

    def test_no_chosen_cuisines_means_no_restriction(self):
        self.assertEqual(
            rule_cuisine_adherence(_plan_with('Sambar'), {'allowed_cuisines': []}), [])

    def test_broad_indian_label_covers_regional_dishes(self):
        ctx = {'allowed_cuisines': ['indian']}
        self.assertEqual(rule_cuisine_adherence(_plan_with('Masala Dosa'), ctx), [])

    def test_mom_meals_path_is_checked_too(self):
        ctx = {'allowed_cuisines': ['kerala']}
        plan = {'mom_meals': {'lunch': {'name': 'Falafel Wrap'}}}
        self.assertEqual(len(rule_cuisine_adherence(plan, ctx)), 1)


class GroceryRulesTests(TestCase):

    def test_recipe_units_flagged(self):
        items = [{'name': 'Rolled oats', 'quantity': '2 cups', 'category': 'grains'}]
        self.assertEqual(len(grocery_rule_retail_quantities(items, {})), 1)

    def test_single_piece_weighable_produce_flagged(self):
        items = [{'name': 'Apple', 'quantity': '1 pc', 'category': 'produce'}]
        violations = grocery_rule_retail_quantities(items, {})
        self.assertEqual(len(violations), 1)
        self.assertIn('weight', violations[0])

    def test_retail_quantities_pass(self):
        items = [
            {'name': 'Apples', 'quantity': '500 g', 'category': 'produce'},
            {'name': 'Chicken', 'quantity': '1.5 kg', 'category': 'protein'},
            {'name': 'Milk', 'quantity': '1 L', 'category': 'dairy'},
            {'name': 'Eggs', 'quantity': '12 pcs', 'category': 'protein'},
            {'name': 'Cilantro', 'quantity': '1 bunch', 'category': 'produce'},
            {'name': 'Bread', 'quantity': '1 pkt', 'category': 'grains'},
        ]
        self.assertEqual(grocery_rule_retail_quantities(items, {}), [])

    def test_odd_gram_amount_flagged(self):
        items = [{'name': 'Celery', 'quantity': '130 g', 'category': 'produce'}]
        self.assertEqual(len(grocery_rule_retail_quantities(items, {})), 1)

    def test_missing_quantity_flagged(self):
        items = [{'name': 'Paneer', 'quantity': '', 'category': 'dairy'}]
        self.assertEqual(len(grocery_rule_retail_quantities(items, {})), 1)

    def test_pantry_staple_flagged(self):
        items = [{'name': 'Basmati rice', 'quantity': '1 kg', 'category': 'grains'}]
        self.assertEqual(len(grocery_rule_no_pantry_staples(items, {})), 1)

    def test_fresh_items_not_staples(self):
        items = [{'name': 'Chicken breast', 'quantity': '1 kg', 'category': 'protein'}]
        self.assertEqual(grocery_rule_no_pantry_staples(items, {}), [])

    def test_leftover_item_flagged(self):
        items = [{'name': 'Leftover dal', 'quantity': '', 'category': 'other'}]
        self.assertEqual(len(grocery_rule_no_leftover_items(items, {})), 1)


class EvalReportTests(TestCase):

    def test_aggregate_counts_passes_and_collects_samples(self):
        results = [
            {'profile': 'p1', 'repeat': 0, 'rule': 'r', 'violations': []},
            {'profile': 'p1', 'repeat': 1, 'rule': 'r', 'violations': ['bad', 'worse']},
            {'profile': 'p2', 'repeat': 0, 'rule': 'r', 'violations': []},
        ]
        card = aggregate(results)
        self.assertEqual(card['r']['passed'], 2)
        self.assertEqual(card['r']['total'], 3)
        self.assertEqual(len(card['r']['samples']), 2)

    def test_sample_cap_is_three(self):
        results = [{'profile': 'p', 'repeat': 0, 'rule': 'r',
                    'violations': ['a', 'b', 'c', 'd', 'e']}]
        self.assertEqual(len(aggregate(results)['r']['samples']), 3)

    def test_prompt_version_is_stable_and_short(self):
        v1, v2 = prompt_version(), prompt_version()
        self.assertEqual(v1, v2)
        self.assertEqual(len(v1), 12)


# ---------------------------------------------------------------------------
# Unit tests: LLM-as-judge cuisine check (fake LLM, no network)
# ---------------------------------------------------------------------------
import json as _json

from planner.evals.judge import (
    build_judge_message, judge_cuisine_adherence, parse_judge_response,
)


class _FakeJudgeLLM:
    """Stands in for Gemini: returns a canned response, records the prompt."""

    def __init__(self, verdicts):
        self._content = _json.dumps(verdicts)
        self.messages = None

    def invoke(self, messages):
        self.messages = messages

        class _Resp:
            content = self._content
        return _Resp()


class CuisineJudgeTests(TestCase):

    def test_message_lists_cuisines_and_dishes(self):
        msg = build_judge_message(['Menemen', 'Sambar'], ['turkish'])
        self.assertIn('turkish', msg)
        self.assertIn('- Menemen', msg)
        self.assertIn('- Sambar', msg)

    def test_parse_accepts_fenced_json(self):
        raw = '```json\n[{"name": "Menemen", "allowed": true}]\n```'
        self.assertEqual(parse_judge_response(raw, 1)[0]['name'], 'Menemen')

    def test_parse_rejects_wrong_count(self):
        with self.assertRaises(ValueError):
            parse_judge_response('[{"name": "x", "allowed": true}]', 2)

    def test_disallowed_dish_becomes_violation(self):
        plans = [{'meals': {
            'breakfast': {'name': 'Menemen'},
            'lunch': {'name': 'Sambar with Rice'},
        }}]
        llm = _FakeJudgeLLM([
            {'name': 'Menemen', 'cuisine': 'Turkish', 'allowed': True, 'reason': 'classic Turkish'},
            {'name': 'Sambar with Rice', 'cuisine': 'South Indian', 'allowed': False, 'reason': 'South Indian staple'},
        ])
        violations = judge_cuisine_adherence(plans, {'allowed_cuisines': ['turkish']}, llm=llm)
        self.assertEqual(len(violations), 1)
        self.assertIn('Sambar', violations[0])

    def test_all_allowed_passes(self):
        plans = [{'meals': {'dinner': {'name': 'Imam Bayildi'}}}]
        llm = _FakeJudgeLLM([{'name': 'Imam Bayildi', 'cuisine': 'Turkish', 'allowed': True}])
        self.assertEqual(
            judge_cuisine_adherence(plans, {'allowed_cuisines': ['turkish']}, llm=llm), [])

    def test_no_cuisines_skips_judge_entirely(self):
        plans = [{'meals': {'dinner': {'name': 'Anything'}}}]
        self.assertEqual(judge_cuisine_adherence(plans, {'allowed_cuisines': []}, llm=None), [])

    def test_judge_failure_is_a_violation_not_a_pass(self):
        class _Broken:
            def invoke(self, messages):
                raise RuntimeError('boom')
        plans = [{'meals': {'dinner': {'name': 'Menemen'}}}]
        violations = judge_cuisine_adherence(plans, {'allowed_cuisines': ['turkish']}, llm=_Broken())
        self.assertEqual(len(violations), 1)
        self.assertIn('judge call failed', violations[0])


# ---------------------------------------------------------------------------
# Unit tests: LLM observability (logged_invoke → GenerationLog)
# ---------------------------------------------------------------------------
from planner.models import GenerationLog
from planner.services.llm_logging import logged_invoke


class _FakeLoggedLLM:
    model = 'gemini-test'

    def __init__(self, fail=False):
        self._fail = fail

    def invoke(self, messages):
        if self._fail:
            raise RuntimeError('quota exceeded')

        class _Resp:
            content = '{"ok": true}'
            usage_metadata = {'input_tokens': 120, 'output_tokens': 45}
        return _Resp()


class LoggedInvokeTests(TestCase):

    def test_successful_call_is_logged_with_tokens(self):
        response, log = logged_invoke(_FakeLoggedLLM(), ['msg'], 'grocery')
        self.assertEqual(response.content, '{"ok": true}')
        self.assertIsNotNone(log)
        self.assertTrue(log.ok)
        self.assertEqual(log.service, 'grocery')
        self.assertEqual(log.input_tokens, 120)
        self.assertEqual(log.output_tokens, 45)
        self.assertEqual(log.model_name, 'gemini-test')
        self.assertEqual(len(log.prompt_version), 12)

    def test_failed_call_is_logged_then_reraised(self):
        with self.assertRaises(RuntimeError):
            logged_invoke(_FakeLoggedLLM(fail=True), ['msg'], 'weekly_meals')
        log = GenerationLog.objects.get()
        self.assertFalse(log.ok)
        self.assertIn('quota exceeded', log.error)
        self.assertEqual(log.service, 'weekly_meals')

    def test_fallback_flag_roundtrip(self):
        _, log = logged_invoke(_FakeLoggedLLM(), ['msg'], 'grocery')
        log.fallback_used = True
        log.save(update_fields=['fallback_used'])
        self.assertTrue(GenerationLog.objects.get(pk=log.pk).fallback_used)


# ---------------------------------------------------------------------------
# Unit tests: behaviour-based personalisation (pure functions, no DB/network)
# ---------------------------------------------------------------------------
from planner.services.preferences import (
    MIN_ACTIONS, _decay_weight, aggregate_events, build_generation_context,
    render_context_section,
)


def _ev(kind, name='', cuisine='', days_ago=1):
    return {'kind': kind, 'name': name, 'cuisine': cuisine,
            'at': date(2026, 6, 1) - timedelta(days=days_ago)}


_TODAY = date(2026, 6, 1)


class DecayWeightTests(TestCase):

    def test_recent_actions_count_fully(self):
        self.assertEqual(_decay_weight(0), 1.0)
        self.assertEqual(_decay_weight(14), 1.0)

    def test_weight_steps_down_with_age(self):
        self.assertEqual(_decay_weight(15), 0.6)
        self.assertEqual(_decay_weight(28), 0.6)
        self.assertEqual(_decay_weight(29), 0.3)
        self.assertEqual(_decay_weight(56), 0.3)

    def test_beyond_eight_weeks_counts_for_nothing(self):
        self.assertEqual(_decay_weight(57), 0.0)
        self.assertEqual(_decay_weight(400), 0.0)


class AggregateEventsTests(TestCase):

    def test_empty_history(self):
        p = aggregate_events([], _TODAY)
        self.assertEqual(p['action_count'], 0)
        self.assertEqual(p['dishes_rejected'], [])
        self.assertEqual(p['candidate_secondary_cuisines'], [])

    def test_dish_needs_two_rejections_to_be_avoided(self):
        once = aggregate_events([_ev('swapped_out', 'Fish Curry')], _TODAY)
        self.assertEqual(once['dishes_rejected'], [])
        twice = aggregate_events(
            [_ev('swapped_out', 'Fish Curry'), _ev('swapped_out', 'Fish Curry')], _TODAY)
        self.assertEqual(twice['dishes_rejected'][0]['name'], 'Fish Curry')

    def test_stale_events_are_ignored(self):
        p = aggregate_events(
            [_ev('swapped_out', 'Old Dish', days_ago=100),
             _ev('swapped_out', 'Old Dish', days_ago=90)], _TODAY)
        self.assertEqual(p['action_count'], 0)
        self.assertEqual(p['dishes_rejected'], [])

    def test_accepted_meals_do_not_count_as_actions(self):
        # Silence is not evidence: passive acceptance must never push a
        # user over the threshold on its own.
        p = aggregate_events([_ev('accepted', 'Dal', 'north indian')] * 20, _TODAY)
        self.assertEqual(p['action_count'], 0)
        self.assertEqual(p['cuisine_accepted']['north indian'], 20.0)

    def test_typed_requests_promote_a_cuisine_after_three(self):
        events = [_ev('requested', 'Pad Thai', 'thai'),
                  _ev('requested', 'Green Curry', 'thai'),
                  _ev('requested', 'Tom Yum', 'thai')]
        p = aggregate_events(events, _TODAY, chosen_cuisines=['north indian'])
        self.assertEqual(p['candidate_secondary_cuisines'],
                         [{'cuisine': 'thai', 'requests': 3}])

    def test_two_requests_are_not_enough(self):
        events = [_ev('requested', 'Pad Thai', 'thai'),
                  _ev('requested', 'Tom Yum', 'thai')]
        p = aggregate_events(events, _TODAY, chosen_cuisines=['north indian'])
        self.assertEqual(p['candidate_secondary_cuisines'], [])

    def test_model_chosen_swaps_never_promote_a_cuisine(self):
        # The model replaces from her own cuisine, so swapped_in carries no
        # cuisine intent — only dishes she typed do.
        events = [_ev('swapped_in', 'Pad Thai', 'thai')] * 5
        p = aggregate_events(events, _TODAY, chosen_cuisines=['north indian'])
        self.assertEqual(p['candidate_secondary_cuisines'], [])

    def test_already_chosen_cuisine_is_never_a_candidate(self):
        events = [_ev('requested', 'Dosa', 'south indian')] * 4
        p = aggregate_events(events, _TODAY, chosen_cuisines=['south indian'])
        self.assertEqual(p['candidate_secondary_cuisines'], [])

    def test_dismissed_cuisine_is_never_relearned(self):
        events = [_ev('requested', 'Pad Thai', 'thai')] * 4
        p = aggregate_events(events, _TODAY, chosen_cuisines=['kerala'],
                             dismissed_cuisines=['thai'])
        self.assertEqual(p['candidate_secondary_cuisines'], [])

    def test_at_most_two_cuisines_are_learned(self):
        events = ([_ev('requested', 'A', 'thai')] * 3
                  + [_ev('requested', 'B', 'mexican')] * 3
                  + [_ev('requested', 'C', 'japanese')] * 3)
        p = aggregate_events(events, _TODAY, chosen_cuisines=['kerala'])
        self.assertEqual(len(p['candidate_secondary_cuisines']), 2)

    def test_swap_rate_is_per_week(self):
        events = [_ev('swapped_out', 'X', days_ago=1), _ev('swapped_out', 'Y', days_ago=7)]
        p = aggregate_events(events, _TODAY)
        self.assertEqual(p['weeks_observed'], 1.0)
        self.assertEqual(p['swap_rate_per_week'], 2.0)


class _FakePrefProfile:
    def __init__(self, cuisines=None, custom='', secondary=None, dismissed=None):
        self.cuisine_preferences = cuisines or []
        self.custom_cuisines = custom
        self.secondary_cuisines = secondary or []
        self.dismissed_learned_cuisines = dismissed or []
        self.updated_at = date(2026, 1, 1)


def _profile_with(action_count, **over):
    base = {
        'action_count': action_count, 'weeks_observed': 4.0,
        'swap_rate_per_week': 1.0, 'cuisine_accepted': {},
        'cuisine_swapped': {}, 'cuisine_requested': {},
        'dishes_rejected': [], 'dishes_favoured': [],
        'candidate_secondary_cuisines': [], 'as_of': '2026-06-01',
    }
    base.update(over)
    return base


class GenerationContextTests(TestCase):

    def test_below_threshold_uses_onboarding_only(self):
        ctx = build_generation_context(
            _FakePrefProfile(['north indian']),
            _profile_with(MIN_ACTIONS - 1,
                          dishes_rejected=[{'name': 'Fish Curry', 'count': 3}]))
        self.assertFalse(ctx['behaviour_applied'])
        self.assertEqual(ctx['avoid_dishes'], [])
        self.assertEqual(ctx['actions_needed'], 1)

    def test_above_threshold_applies_behaviour(self):
        ctx = build_generation_context(
            _FakePrefProfile(['north indian']),
            _profile_with(MIN_ACTIONS,
                          dishes_rejected=[{'name': 'Fish Curry', 'count': 3}],
                          dishes_favoured=[{'name': 'Rajma', 'count': 4}]))
        self.assertTrue(ctx['behaviour_applied'])
        self.assertEqual(ctx['avoid_dishes'], ['Fish Curry'])
        self.assertEqual(ctx['favour_dishes'], ['Rajma'])

    def test_learned_cuisine_is_added(self):
        ctx = build_generation_context(
            _FakePrefProfile(['north indian']),
            _profile_with(12, candidate_secondary_cuisines=[
                {'cuisine': 'thai', 'requests': 3}]))
        self.assertEqual(ctx['learned_cuisines'], ['thai'])

    def test_stated_cuisine_is_never_duplicated_as_learned(self):
        ctx = build_generation_context(
            _FakePrefProfile(['thai']),
            _profile_with(12, candidate_secondary_cuisines=[
                {'cuisine': 'thai', 'requests': 5}]))
        self.assertEqual(ctx['learned_cuisines'], [])

    def test_lists_are_capped(self):
        many = [{'name': 'D%d' % i, 'count': 3} for i in range(10)]
        ctx = build_generation_context(
            _FakePrefProfile(['kerala']),
            _profile_with(20, dishes_rejected=many, dishes_favoured=many))
        self.assertEqual(len(ctx['avoid_dishes']), 5)
        self.assertEqual(len(ctx['favour_dishes']), 5)


class RenderContextSectionTests(TestCase):

    def test_nothing_rendered_before_threshold(self):
        ctx = build_generation_context(
            _FakePrefProfile(['kerala']), _profile_with(2))
        self.assertIsNone(render_context_section(ctx))

    def test_section_names_dishes_and_cuisine(self):
        ctx = build_generation_context(
            _FakePrefProfile(['north indian']),
            _profile_with(12,
                          dishes_rejected=[{'name': 'Fish Curry', 'count': 3}],
                          candidate_secondary_cuisines=[{'cuisine': 'thai', 'requests': 3}]))
        text = render_context_section(ctx)
        self.assertIn('Fish Curry', text)
        self.assertIn('Thai', text)
        self.assertIn('2-3 of them per week', text)
        # Behaviour must never read as a hard constraint.
        self.assertIn('preferences, not constraints', text)


# ---------------------------------------------------------------------------
# Integration: collect_events, learned-cuisine sync, and the API
# ---------------------------------------------------------------------------
from planner.models import DayPlan, MealPlan, MealSwapLog
from planner.services.preferences import (
    build_behaviour_profile, collect_events, sync_learned_cuisines,
)


class CollectEventsTests(TestCase):

    def setUp(self):
        user = User.objects.create_user(username='pref', password='x')
        self.profile = UserProfile.objects.create(
            user=user, display_name='Pref', cuisine_preferences=['North Indian'])

    def test_typed_request_is_a_requested_event(self):
        MealSwapLog.objects.create(
            profile=self.profile, meal_type='dinner', rejected_meal='Dal',
            chosen_meal='Pad Thai', user_request='something thai',
            was_user_request=True, chosen_cuisine='Thai')
        kinds = {e['kind'] for e in collect_events(self.profile)}
        self.assertIn('requested', kinds)
        self.assertIn('swapped_out', kinds)

    def test_tap_swap_is_not_a_request(self):
        MealSwapLog.objects.create(
            profile=self.profile, meal_type='dinner', rejected_meal='Dal',
            chosen_meal='Rajma', was_user_request=False, chosen_cuisine='North Indian')
        kinds = {e['kind'] for e in collect_events(self.profile)}
        self.assertIn('swapped_in', kinds)
        self.assertNotIn('requested', kinds)

    def test_past_meals_become_accepted_events(self):
        plan = DayPlan.objects.create(
            profile=self.profile, date=date.today() - timedelta(days=2), status='ready')
        MealPlan.objects.create(day_plan=plan, meal_type='lunch',
                                name='Rajma Chawal', cuisine='North Indian')
        accepted = [e for e in collect_events(self.profile) if e['kind'] == 'accepted']
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0]['cuisine'], 'North Indian')


class LearnedCuisineSyncTests(TestCase):

    def setUp(self):
        user = User.objects.create_user(username='learner', password='x')
        self.profile = UserProfile.objects.create(
            user=user, display_name='L', cuisine_preferences=['North Indian'])

    def _request_thai(self, n):
        for i in range(n):
            MealSwapLog.objects.create(
                profile=self.profile, meal_type='dinner',
                rejected_meal='Dal %d' % i, chosen_meal='Thai dish %d' % i,
                user_request='thai please', was_user_request=True,
                chosen_cuisine='Thai')

    def test_three_requests_promote_thai(self):
        self._request_thai(3)
        self.assertEqual(sync_learned_cuisines(self.profile), ['thai'])
        self.profile.refresh_from_db()
        self.assertEqual(self.profile.learned_secondary_cuisines, ['thai'])

    def test_two_requests_do_not(self):
        self._request_thai(2)
        self.assertEqual(sync_learned_cuisines(self.profile), [])

    def test_sync_does_not_look_like_a_settings_edit(self):
        # updated_at drives "settings outrank behaviour" — learning must
        # not bump it, or behaviour would permanently suppress itself.
        self._request_thai(3)
        before = UserProfile.objects.get(pk=self.profile.pk).updated_at
        sync_learned_cuisines(self.profile)
        self.assertEqual(UserProfile.objects.get(pk=self.profile.pk).updated_at, before)


class LearnedPreferencesAPITests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='api', password='x')
        self.profile = UserProfile.objects.create(
            user=self.user, display_name='A', cuisine_preferences=['Kerala'])
        self.client.force_authenticate(user=self.user)

    def test_requires_authentication(self):
        self.client.force_authenticate(user=None)
        self.assertIn(self.client.get('/api/v1/preferences/learned/').status_code,
                      (401, 403))

    def test_empty_history_is_honest(self):
        resp = self.client.get('/api/v1/preferences/learned/')
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.data['applied'])
        self.assertEqual(resp.data['actions_needed'], MIN_ACTIONS)
        self.assertEqual(resp.data['learned_cuisines'], [])

    def test_dismiss_removes_and_remembers(self):
        self.profile.learned_secondary_cuisines = ['thai']
        self.profile.save()
        resp = self.client.post('/api/v1/preferences/learned/', {'cuisine': 'thai'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['learned_cuisines'], [])
        self.assertEqual(resp.data['dismissed_cuisines'], ['thai'])

    def test_dismissed_cuisine_is_not_relearned(self):
        self.profile.dismissed_learned_cuisines = ['thai']
        self.profile.save()
        for i in range(4):
            MealSwapLog.objects.create(
                profile=self.profile, meal_type='dinner', rejected_meal='x%d' % i,
                chosen_meal='Pad Thai', was_user_request=True, chosen_cuisine='Thai')
        self.assertEqual(sync_learned_cuisines(self.profile), [])

    def test_dismiss_requires_a_cuisine(self):
        self.assertEqual(
            self.client.post('/api/v1/preferences/learned/', {}).status_code, 400)


# ---------------------------------------------------------------------------
# Meal <-> grocery coupling: swap cooks from stock, her request adds to it
# ---------------------------------------------------------------------------
from planner.models import GroceryItem, GroceryList, UserPantryItem
from planner.services.grocery_generator import (
    add_missing_to_grocery, available_ingredients,
)


class MealGroceryCouplingTests(TestCase):

    def setUp(self):
        user = User.objects.create_user(username='coupling', password='x')
        self.profile = UserProfile.objects.create(
            user=user, display_name='C', family_size=2)
        self.glist = GroceryList.objects.create(
            profile=self.profile, week_start_date=date.today())
        for name, cat in (('Chicken', 'protein'), ('Onion', 'produce')):
            GroceryItem.objects.create(grocery_list=self.glist, name=name,
                                       quantity='500 g', category=cat)

    def test_available_lists_grocery_and_pantry(self):
        UserPantryItem.objects.create(profile=self.profile, name='Coconut milk')
        have = available_ingredients(self.profile)
        self.assertIn('Chicken', have)
        self.assertIn('Coconut milk', have)

    def test_available_dedupes_across_sources(self):
        UserPantryItem.objects.create(profile=self.profile, name='Onions')
        self.assertEqual(len([h for h in available_ingredients(self.profile)
                              if h.lower().startswith('onion')]), 1)

    def test_only_missing_items_are_added(self):
        added = add_missing_to_grocery(self.profile, ['Chicken', 'Lemongrass'])
        self.assertEqual(added, ['Lemongrass'])
        self.assertEqual(self.glist.items.filter(name='Chicken').count(), 1)

    def test_pantry_items_are_not_added_again(self):
        UserPantryItem.objects.create(profile=self.profile, name='Coconut milk')
        self.assertEqual(add_missing_to_grocery(self.profile, ['Coconut milk']), [])

    def test_staples_and_vague_items_are_skipped(self):
        self.assertEqual(
            add_missing_to_grocery(self.profile, ['Basmati rice', 'Salt', 'Water']), [])

    def test_added_items_are_user_added_and_retail_sized(self):
        add_missing_to_grocery(self.profile, ['Lemongrass'])
        item = self.glist.items.get(name='Lemongrass')
        self.assertTrue(item.is_user_added)
        self.assertRegex(item.quantity, r'^\d+(\.\d+)?\s*(g|kg|ml|L|pcs|pc|bunch|pkt)$')

    def test_duplicate_within_one_call_is_added_once(self):
        added = add_missing_to_grocery(self.profile, ['Lemongrass', 'lemongrass'])
        self.assertEqual(added, ['Lemongrass'])

    def test_no_active_list_means_nothing_added(self):
        self.glist.completed = True
        self.glist.save()
        self.assertEqual(add_missing_to_grocery(self.profile, ['Lemongrass']), [])
        self.assertEqual(available_ingredients(self.profile), [])


# ---------------------------------------------------------------------------
# Rename flow with Gemini mocked — the live "user types a dish" path.
# The view imports ChatGoogleGenerativeAI inside the method, so patching it
# at its source module intercepts the call without touching the network.
# ---------------------------------------------------------------------------
from types import SimpleNamespace
from unittest.mock import patch


class _FakeGeminiResponse(SimpleNamespace):
    pass


class RenameMealFlowTests(APITestCase):

    def setUp(self):
        self.user = User.objects.create_user(username='renamer', password='x')
        self.profile = UserProfile.objects.create(
            user=self.user, display_name='R', family_size=2,
            cuisine_preferences=['North Indian'])
        self.client.force_authenticate(user=self.user)
        self.day = date.today()
        self.plan = DayPlan.objects.create(
            profile=self.profile, date=self.day, status='ready',
            plan_data={'meals': {'dinner': {
                'name': 'Chana Masala', 'cuisine': 'North Indian',
                'ingredients': ['Chickpeas'], 'steps': ['Cook']}}})
        self.glist = GroceryList.objects.create(
            profile=self.profile, week_start_date=self.day)
        GroceryItem.objects.create(grocery_list=self.glist, name='Chicken',
                                   quantity='500 g', category='protein')

    def _rename(self, new_name='Thai Green Curry', payload=None):
        body = payload or {
            'prep_mins': 25, 'kcal': 480, 'description': 'Creamy Thai curry',
            'tags': ['Quick', 'High protein'], 'cuisine': 'Thai',
            'ingredients': ['Chicken', 'Lemongrass', 'Basmati rice'],
        }
        with patch('langchain_google_genai.ChatGoogleGenerativeAI') as cls:
            cls.return_value.invoke.return_value = _FakeGeminiResponse(
                content=_json.dumps(body))
            return self.client.post(
                '/api/v1/plans/%s/rename-meal/' % self.day,
                {'meal_type': 'dinner', 'name': new_name})

    def test_typed_dish_is_logged_as_a_user_request(self):
        resp = self._rename()
        self.assertEqual(resp.status_code, 200)
        log = MealSwapLog.objects.get()
        self.assertTrue(log.was_user_request)
        self.assertEqual(log.rejected_meal, 'Chana Masala')
        self.assertEqual(log.chosen_meal, 'Thai Green Curry')
        self.assertEqual(log.chosen_cuisine, 'Thai')
        self.assertEqual(log.rejected_cuisine, 'North Indian')

    def test_only_missing_ingredients_reach_the_grocery_list(self):
        resp = self._rename()
        # Chicken is already on the list; rice is a pantry staple.
        self.assertEqual(resp.data['added_to_grocery'], ['Lemongrass'])
        self.assertEqual(self.glist.items.filter(name='Chicken').count(), 1)
        self.assertFalse(self.glist.items.filter(name__icontains='rice').exists())

    def test_added_item_survives_regeneration(self):
        self._rename()
        self.assertTrue(self.glist.items.get(name='Lemongrass').is_user_added)

    def test_cuisine_and_ingredients_are_stored_on_the_meal(self):
        self._rename()
        self.plan.refresh_from_db()
        meal = self.plan.plan_data['meals']['dinner']
        self.assertEqual(meal['cuisine'], 'Thai')
        self.assertIn('Lemongrass', meal['ingredients'])
        self.assertEqual(self.plan.meals.get(meal_type='dinner').cuisine, 'Thai')

    def test_three_renames_teach_a_secondary_cuisine(self):
        # The whole point of the chain: typed dishes become a learned cuisine.
        for i in range(3):
            self.plan.plan_data = {'meals': {'dinner': {'name': 'Dish %d' % i}}}
            self.plan.save()
            self._rename('Thai Dish %d' % i)
        self.assertEqual(sync_learned_cuisines(self.profile), ['thai'])

    def test_grocery_failure_never_breaks_the_rename(self):
        with patch('planner.services.grocery_generator.add_missing_to_grocery',
                   side_effect=RuntimeError('boom')):
            resp = self._rename()
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data['added_to_grocery'], [])
