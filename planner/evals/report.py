"""Scorecard: turn raw rule results into pass rates, print them, save them.

A "result" is one application of one rule to one generated artifact:

    {'profile': 'eval_north_indian_family', 'repeat': 0,
     'rule': 'cuisine_adherence', 'violations': []}

Aggregation is per rule: how many applications passed out of how many ran.
Every saved report carries a prompt-version hash so a future run can answer
"did my prompt edit move these numbers?" with --compare.
"""

import hashlib
import inspect
import json
from datetime import datetime
from pathlib import Path

REPORTS_DIR = Path(__file__).resolve().parent / 'reports'


def prompt_version():
    """Short fingerprint of the prompt-building code. Changes whenever
    plan_generator / ai_context / grocery_generator change, so a report is
    attributable to the exact prompts that produced it."""
    from ..services import ai_context, grocery_generator, plan_generator
    blob = ''.join(
        inspect.getsource(m)
        for m in (plan_generator, ai_context, grocery_generator)
    )
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def aggregate(results):
    """results -> {rule: {'passed': n, 'total': n, 'samples': [msg, ...]}}"""
    card = {}
    for r in results:
        entry = card.setdefault(r['rule'], {'passed': 0, 'total': 0, 'samples': []})
        entry['total'] += 1
        if r['violations']:
            for v in r['violations']:
                if len(entry['samples']) < 3:
                    entry['samples'].append('%s: %s' % (r['profile'], v))
        else:
            entry['passed'] += 1
    return card


def render(card):
    """Aligned console table, worst rules first."""
    if not card:
        return 'No results.'
    rows = sorted(
        card.items(),
        key=lambda kv: (kv[1]['passed'] / kv[1]['total'], kv[0]),
    )
    width = max(len(name) for name in card) + 2
    lines = ['', '%-*s %8s   %s' % (width, 'rule', 'passed', 'rate'),
             '-' * (width + 24)]
    for name, e in rows:
        rate = e['passed'] / e['total']
        lines.append('%-*s %5d/%-3d  %5.0f%%' % (width, name, e['passed'], e['total'], rate * 100))
        for s in e['samples']:
            lines.append('    ! %s' % s)
    return '\n'.join(lines)


def save(card, meta):
    """Write the report JSON; returns the path."""
    REPORTS_DIR.mkdir(exist_ok=True)
    path = REPORTS_DIR / ('%s.json' % datetime.now().strftime('%Y%m%d-%H%M%S'))
    path.write_text(json.dumps({'meta': meta, 'scorecard': card}, indent=2))
    return path


def compare(card, old_path):
    """Per-rule pass-rate deltas against a previous report file."""
    old = json.loads(Path(old_path).read_text())
    old_card = old.get('scorecard', {})
    lines = ['', 'vs %s (prompt %s -> now):' % (old_path, old.get('meta', {}).get('prompt_version', '?'))]
    for name in sorted(set(card) | set(old_card)):
        new_e, old_e = card.get(name), old_card.get(name)
        if not new_e or not old_e:
            lines.append('  %-28s %s' % (name, 'new rule' if not old_e else 'removed'))
            continue
        new_rate = new_e['passed'] / new_e['total']
        old_rate = old_e['passed'] / old_e['total']
        delta = (new_rate - old_rate) * 100
        marker = '=' if abs(delta) < 0.5 else ('+' if delta > 0 else '-')
        lines.append('  %-28s %5.0f%% -> %5.0f%%  (%s%.0f%%)' % (
            name, old_rate * 100, new_rate * 100, marker if marker != '=' else '', abs(delta)))
    return '\n'.join(lines)
