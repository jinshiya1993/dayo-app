"""LLM observability summary from GenerationLog rows.

    python manage.py llm_stats            # last 7 days
    python manage.py llm_stats --days 30

Per service: call count, success rate, grocery fallback rate, latency
(avg / p95), token totals, and estimated cost.
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from planner.models import GenerationLog

# Gemini 2.5 Flash list price per 1M tokens (USD). Update when pricing
# changes — these only feed the rough cost estimate below.
PRICE_IN_PER_M = 0.30
PRICE_OUT_PER_M = 2.50


def _p95(values):
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(round(0.95 * len(ordered))) )]


class Command(BaseCommand):
    help = 'Summarise GenerationLog: calls, success %, fallback rate, latency, cost.'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=7)

    def handle(self, *args, **opts):
        since = timezone.now() - timedelta(days=opts['days'])
        rows = list(GenerationLog.objects.filter(created_at__gte=since)
                    .values('service', 'ok', 'fallback_used',
                            'input_tokens', 'output_tokens', 'latency_ms'))
        if not rows:
            self.stdout.write('No LLM calls logged in the last %d day(s).' % opts['days'])
            return

        services = {}
        for r in rows:
            services.setdefault(r['service'], []).append(r)

        self.stdout.write('\nLast %d day(s) — %d LLM calls\n' % (opts['days'], len(rows)))
        header = '%-14s %6s %7s %9s %9s %9s %11s %8s' % (
            'service', 'calls', 'ok', 'fallback', 'avg ms', 'p95 ms', 'tokens', 'cost $')
        self.stdout.write(header)
        self.stdout.write('-' * len(header))

        total_cost = 0.0
        for service in sorted(services):
            calls = services[service]
            n = len(calls)
            ok = sum(1 for c in calls if c['ok'])
            fallbacks = sum(1 for c in calls if c['fallback_used'])
            latencies = [c['latency_ms'] for c in calls if c['latency_ms']]
            tokens_in = sum(c['input_tokens'] for c in calls)
            tokens_out = sum(c['output_tokens'] for c in calls)
            cost = (tokens_in * PRICE_IN_PER_M + tokens_out * PRICE_OUT_PER_M) / 1e6
            total_cost += cost
            self.stdout.write('%-14s %6d %6.0f%% %8s %9.0f %9.0f %11s %8.4f' % (
                service, n, 100.0 * ok / n,
                ('%.0f%%' % (100.0 * fallbacks / n)) if service == 'grocery' else '—',
                (sum(latencies) / len(latencies)) if latencies else 0,
                _p95(latencies),
                '{:,}'.format(tokens_in + tokens_out),
                cost,
            ))

        self.stdout.write('\nEstimated total cost: $%.4f  (Gemini 2.5 Flash list pricing)' % total_cost)
        errors = GenerationLog.objects.filter(
            created_at__gte=since, ok=False).order_by('-created_at')[:3]
        if errors:
            self.stdout.write('\nRecent failures:')
            for e in errors:
                self.stdout.write('  %s %s: %s' % (
                    e.created_at.strftime('%m-%d %H:%M'), e.service, e.error[:120]))
