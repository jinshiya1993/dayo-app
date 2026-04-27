import json
import logging
import re

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import CuisineMealSuggestions

logger = logging.getLogger(__name__)

EMPTY = {'breakfast': [], 'lunch': [], 'dinner': []}


def get_suggestions(cuisine):
    """Return {breakfast, lunch, dinner} suggestion lists for a cuisine.

    Cached in CuisineMealSuggestions keyed by lowercased name so the same
    cuisine across users only hits Gemini once.
    """
    key = (cuisine or '').strip().lower()
    if not key:
        return EMPTY

    cached = CuisineMealSuggestions.objects.filter(cuisine=key).first()
    if cached:
        return {
            'breakfast': cached.breakfast,
            'lunch': cached.lunch,
            'dinner': cached.dinner,
        }

    parsed = _generate(cuisine.strip())
    if not parsed:
        # Don't cache failures — let the next request retry.
        return EMPTY

    CuisineMealSuggestions.objects.create(
        cuisine=key,
        display_cuisine=cuisine.strip()[:80],
        breakfast=parsed['breakfast'],
        lunch=parsed['lunch'],
        dinner=parsed['dinner'],
    )
    return parsed


def _generate(cuisine):
    llm = ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.4,
        max_output_tokens=1024,
        transport='rest',
    )

    system = SystemMessage(content=(
        'You suggest common everyday dishes for a given cuisine. '
        'Return ONLY a JSON object with keys "breakfast", "lunch", "dinner" — '
        'each a list of 6 short dish names (2-4 words each). No prose, no markdown.'
    ))
    human = HumanMessage(content=(
        f'Cuisine: {cuisine}\n'
        'Give 6 typical breakfast dishes, 6 typical lunch dishes, and 6 typical '
        'dinner dishes that home cooks of this cuisine actually eat. '
        'Use widely-recognised names.'
    ))

    try:
        response = llm.invoke([system, human])
    except Exception as e:
        logger.warning(f'Meal suggestions Gemini call failed for {cuisine!r}: {e}')
        return None

    raw = (response.content or '').strip()
    data = _parse_json(raw)
    if not data:
        logger.warning(f'Meal suggestions JSON parse failed for {cuisine!r}: {raw[:200]}')
        return None

    return {
        'breakfast': _clean_list(data.get('breakfast')),
        'lunch': _clean_list(data.get('lunch')),
        'dinner': _clean_list(data.get('dinner')),
    }


def _parse_json(raw):
    # Gemini sometimes wraps in ```json fences.
    fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
    if fenced:
        raw = fenced.group(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None


def _clean_list(items):
    if not isinstance(items, list):
        return []
    out = []
    seen = set()
    for item in items:
        if not isinstance(item, str):
            continue
        name = item.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(name)
    return out[:8]
