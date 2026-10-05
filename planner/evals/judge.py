"""LLM-as-judge: does every planned dish belong to the user's cuisines?

This is Dayo's core promise -- the plan matches the household's preferred
cuisine, whatever that cuisine is -- so it cannot be checked by a lookup
table of known dishes. A second model call classifies each generated dish
against the user's allowed set. Generic across every cuisine: Turkish,
Filipino, Ethiopian -- anything a future user picks.

Relationship to rules.rule_cuisine_adherence: the marker table is the free,
deterministic tripwire for famous failures (sambar in a North Indian home);
the judge is the general check. Both run; the judge is authoritative.

The judge is itself an LLM and can be wrong. Before trusting a surprising
score, read the per-dish reasons in the report samples -- and when the
verdicts disagree with your own judgment, fix THIS rubric, not your opinion.
"""

import json

from django.conf import settings


def _judge_llm():
    from langchain_google_genai import ChatGoogleGenerativeAI
    # temperature 0: a judge should be as deterministic as the API allows.
    return ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.0,
        max_output_tokens=2048,
        thinking_budget=0,
        transport='rest',
    )


JUDGE_SYSTEM = (
    'You are a strict culinary classifier. You will receive a list of dish '
    'names and a set of allowed cuisines. For EACH dish, decide whether the '
    'dish plausibly belongs to AT LEAST ONE of the allowed cuisines.\n'
    'Rules of judgment:\n'
    '- Judge the dish, not the ingredients: "Masala Dosa" is South Indian '
    'even if a North Indian household could buy the ingredients.\n'
    '- Shared/borderline dishes count as allowed when the overlap is real '
    '(hummus for a Turkish table: allowed; sushi for an Italian table: not).\n'
    '- Generic international basics (oat porridge, boiled eggs, fruit salad, '
    'green salad, plain rice) are cuisine-neutral: always allowed.\n'
    '- If the allowed set is empty, everything is allowed.\n'
    'Return ONLY a JSON array, one object per dish, same order:\n'
    '[{"name": "<dish>", "cuisine": "<your best label>", "allowed": true, '
    '"reason": "<five words max>"}]'
)


def build_judge_message(dish_names, allowed_cuisines):
    return (
        'Allowed cuisines: %s\n'
        'Dishes:\n%s'
    ) % (
        ', '.join(allowed_cuisines) if allowed_cuisines else '(none chosen — allow everything)',
        '\n'.join('- %s' % n for n in dish_names),
    )


def parse_judge_response(raw, expected_count):
    """Fenced-JSON tolerant parse; raises ValueError when unusable."""
    content = raw.strip()
    if '```' in content:
        content = content.split('```')[1]
        if content.startswith('json'):
            content = content[4:]
        content = content.strip()
    verdicts = json.loads(content)
    if not isinstance(verdicts, list) or len(verdicts) != expected_count:
        raise ValueError('judge returned %s verdicts for %d dishes'
                         % (len(verdicts) if isinstance(verdicts, list) else 'non-list', expected_count))
    return verdicts


def judge_cuisine_adherence(plan_datas, ctx, llm=None):
    """Judge every dish in a batch of day plans. Returns violation messages
    (empty = all dishes belong), judge failures reported as violations too --
    an unverifiable plan should not silently count as compliant."""
    from .rules import _meals

    allowed = ctx.get('allowed_cuisines') or []
    if not allowed:
        return []

    dishes = []
    for pd in plan_datas:
        for slot, meal in _meals(pd).items():
            if isinstance(meal, dict) and (meal.get('name') or '').strip():
                dishes.append(meal['name'].strip())
    if not dishes:
        return ['no dishes found to judge']

    from langchain_core.messages import HumanMessage, SystemMessage
    llm = llm or _judge_llm()
    messages = [
        SystemMessage(content=JUDGE_SYSTEM),
        HumanMessage(content=build_judge_message(dishes, allowed)),
    ]
    try:
        response = llm.invoke(messages)
        verdicts = parse_judge_response(response.content, len(dishes))
    except Exception as e:
        return ['judge call failed: %s' % e]

    out = []
    for v in verdicts:
        if not isinstance(v, dict) or v.get('allowed') is True:
            continue
        out.append('%r judged %s (%s), allowed: %s' % (
            v.get('name'), v.get('cuisine', '?'), v.get('reason', ''),
            ', '.join(allowed)))
    return out
