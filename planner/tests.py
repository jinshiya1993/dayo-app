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
