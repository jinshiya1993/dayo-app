"""Run the LLM eval harness: generate real plans for the golden profiles,
check every rule, print a scorecard, save a JSON report.

    python manage.py run_evals                         # cheap default: 2 profiles, 1 repeat
    python manage.py run_evals --profiles all --repeats 3 --grocery
    python manage.py run_evals --compare planner/evals/reports/<old>.json

Costs real Gemini calls: one per profile-repeat for meals, plus one each
when --grocery is set. Local dev database only.
"""

import socket
from datetime import date, timedelta

from django.core.management.base import BaseCommand

# Force IPv4 for this command. The Gemini key's IP allowlist holds our
# stable IPv4; macOS IPv6 privacy extensions rotate the v6 suffix, which
# keeps tripping the key's restriction. Dev-only process, so patching the
# resolver here is safe and keeps eval runs deterministic.
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only

from planner.evals import report as report_mod
from planner.evals.context import build_context
from planner.evals.profiles import DEFAULT_PROFILE_NAMES, GOLDEN_PROFILES, sync_profiles
from planner.evals.rules import DAY_RULES, GROCERY_RULES, WEEK_RULES


class Command(BaseCommand):
    help = 'Run LLM evals against the golden profiles and print a scorecard.'

    def add_arguments(self, parser):
        parser.add_argument('--profiles', default=None,
                            help='Comma-separated eval usernames, or "all". Default: %s'
                                 % ', '.join(DEFAULT_PROFILE_NAMES))
        parser.add_argument('--repeats', type=int, default=1,
                            help='Generations per profile — compliance is a rate, not a bool.')
        parser.add_argument('--days', type=int, default=3,
                            help='Days per generation (one Gemini call regardless).')
        parser.add_argument('--grocery', action='store_true',
                            help='Also generate and evaluate a grocery list per profile.')
        parser.add_argument('--no-judge', action='store_true',
                            help='Skip the LLM-as-judge cuisine check (one extra '
                                 'Gemini call per profile-repeat; on by default '
                                 'because cuisine match is Dayo\'s core promise).')
        parser.add_argument('--compare', default=None,
                            help='Path to a previous report JSON to diff against.')

    def handle(self, *args, **opts):
        if opts['profiles'] == 'all':
            names = [g['username'] for g in GOLDEN_PROFILES]
        elif opts['profiles']:
            names = [n.strip() for n in opts['profiles'].split(',') if n.strip()]
        else:
            names = DEFAULT_PROFILE_NAMES

        profiles = sync_profiles(names)
        if not profiles:
            self.stderr.write('No matching golden profiles: %s' % names)
            return

        version = report_mod.prompt_version()
        self.stdout.write('Prompt version %s — %d profile(s) x %d repeat(s), %d days%s' % (
            version, len(profiles), opts['repeats'], opts['days'],
            ', +grocery' if opts['grocery'] else ''))

        results = []
        for profile in profiles:
            ctx = build_context(profile)
            for repeat in range(opts['repeats']):
                self.stdout.write('  %s repeat %d — generating meals...' % (
                    profile.user.username, repeat + 1))
                results.extend(self._eval_meals(
                    profile, ctx, repeat, opts['days'], judge=not opts['no_judge']))
                if opts['grocery']:
                    self.stdout.write('  %s repeat %d — generating grocery...' % (
                        profile.user.username, repeat + 1))
                    results.extend(self._eval_grocery(profile, ctx, repeat))

        card = report_mod.aggregate(results)
        self.stdout.write(report_mod.render(card))

        meta = {
            'prompt_version': version,
            'profiles': [p.user.username for p in profiles],
            'repeats': opts['repeats'],
            'days': opts['days'],
            'grocery': opts['grocery'],
            'run_at': date.today().isoformat(),
        }
        path = report_mod.save(card, meta)
        self.stdout.write('\nReport saved: %s' % path)

        if opts['compare']:
            self.stdout.write(report_mod.compare(card, opts['compare']))

    def _eval_meals(self, profile, ctx, repeat, num_days, judge=True):
        from planner.evals.judge import judge_cuisine_adherence
        from planner.services.plan_generator import PlanGenerator

        username = profile.user.username
        try:
            plans = PlanGenerator().generate_weekly_meals(
                profile, start_date=date.today(), num_days=num_days)
        except Exception as e:
            return [self._error(username, repeat, 'meal generation raised: %s' % e)]
        if not plans:
            return [self._error(username, repeat, 'meal generation returned no days')]

        results = []
        plan_datas = [p.plan_data or {} for p in plans]
        for pd in plan_datas:
            for rule_name, rule in DAY_RULES:
                results.append({
                    'profile': username, 'repeat': repeat, 'rule': rule_name,
                    'violations': rule(pd, ctx),
                })
        for rule_name, rule in WEEK_RULES:
            results.append({
                'profile': username, 'repeat': repeat, 'rule': rule_name,
                'violations': rule(plan_datas, ctx),
            })
        # Dayo's core promise, checked generically for ANY cuisine the user
        # picked -- the marker rule above only trips on famous dishes.
        if judge and ctx.get('allowed_cuisines'):
            results.append({
                'profile': username, 'repeat': repeat, 'rule': 'cuisine_judge',
                'violations': judge_cuisine_adherence(plan_datas, ctx),
            })
        return results

    def _eval_grocery(self, profile, ctx, repeat):
        from planner.services.grocery_generator import (
            FREQUENCY_DAYS, GroceryGenerator, _dedup_key,
        )

        username = profile.user.username
        gen = GroceryGenerator()
        try:
            grocery_list = gen.generate_grocery_list(profile, week_start=date.today())
        except Exception as e:
            return [self._error(username, repeat, 'grocery generation raised: %s' % e)]
        if grocery_list is None:
            return [self._error(username, repeat, 'grocery generation returned None')]

        items = list(grocery_list.items.values('name', 'quantity', 'category'))
        results = [
            {'profile': username, 'repeat': repeat, 'rule': rule_name,
             'violations': rule(items, ctx)}
            for rule_name, rule in GROCERY_RULES
        ]

        # Coverage: every deterministic base-list ingredient must survive
        # into the saved list (the completeness floor, checked end to end).
        days = FREQUENCY_DAYS.get(profile.grocery_frequency, 7)
        end = date.today() + timedelta(days=days - 1)
        existing = gen._collect_existing_meals(profile, date.today(), end)
        pantry = {p.strip().lower() for p in
                  profile.pantry_items.values_list('name', flat=True) if p.strip()}
        base = gen._build_base_list(existing, pantry)
        saved_keys = {_dedup_key(i['name']) for i in items}
        missing = [b['name'] for b in base if _dedup_key(b['name']) not in saved_keys]
        results.append({
            'profile': username, 'repeat': repeat, 'rule': 'base_list_coverage',
            'violations': ['missing from list: %s' % m for m in missing],
        })
        return results

    @staticmethod
    def _error(username, repeat, message):
        return {'profile': username, 'repeat': repeat,
                'rule': 'generation_error', 'violations': [message]}
