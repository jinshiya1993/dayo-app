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
