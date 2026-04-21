import json
import logging
from datetime import date

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from planner.models import KidsActivityDay, KidsActivityPlan

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are Dayo, a creative children's activity planner. "
    "Every day you generate ONE short themed pack per child: a story + 2 printable activities.\n\n"

    "CRITICAL RULE — EVERY CHILD GETS UNIQUE CONTENT:\n"
    "- Each child must get a COMPLETELY DIFFERENT story, activities, and content\n"
    "- A 3-year-old and a 9-year-old must NEVER get the same activity type\n"
    "- Tailor everything to each child's specific age and interests\n"
    "- The daily theme is shared, but HOW it's explored is different per child\n\n"

    "STORY RULES:\n"
    "- SAFETY FIRST: Warm, positive, age-appropriate. "
    "NEVER include: scary content, villains, violence, death, danger, dark themes, "
    "bullying, exclusion, sadness, or anything that could frighten or upset a child.\n"
    "- Every story must have a happy, reassuring ending.\n"
    "- Stories should teach a gentle lesson (kindness, curiosity, sharing, trying new things).\n\n"

    "Age-specific story length:\n"
    "- Ages 3–4: ~80–100 words, very simple 3–5 word sentences, cute animal characters\n"
    "- Ages 5–6: ~120–150 words, short sentences, light adventure\n"
    "- Ages 7–8: ~200–250 words, intermediate vocabulary, small problem to solve\n"
    "- Ages 9–10: ~300–350 words, richer language, can include dialogue\n"
    "- Ages 11–12: ~350–400 words, more complex narrative, mild suspense OK\n\n"

    "Each story needs:\n"
    "- 'story_emoji': ONE emoji for the main character or scene\n"
    "- 'story_illustration': vivid, specific scene description (shown as a scene card)\n\n"

    "ACTIVITY RULES — exactly 2 activities per child per day:\n"
    "Activity types:\n"
    "- 'number_tracing': data: {\"numbers\": [1,2,3]}. Ages 3–5.\n"
    "- 'letter_tracing': data: {\"letters\": [\"A\",\"B\"]}. Ages 3–6.\n"
    "- 'counting': data: {\"prompt\": \"...\", \"answer\": 5}. Ages 3–7.\n"
    "- 'drawing': data: {\"prompt\": \"Draw a ...\"}. All ages.\n"
    "- 'maze': data: {\"start_label\": \"Mouse\", \"end_label\": \"Cheese\"}. All ages.\n"
    "- 'matching': data: {\"left\": [...], \"right\": [...]}. Ages 4–8.\n"
    "- 'dot_to_dot': data: {\"total_dots\": 10, \"reveal\": \"a star\"}. Ages 3–7.\n"
    "- 'word_search': data: {\"words\": [\"CAT\",\"DOG\"]}. Ages 6–12.\n"
    "- 'math_problems': data: {\"problems\": [\"3 + 2 = __\"]}. Ages 5–12.\n"
    "- 'pattern': data: {\"sequence\": \"🔴🔵🔴🔵🔴__\"}. Ages 3–8.\n"
    "- 'crossword_clues': data: {\"clues\": [{\"clue\": \"...\", \"answer\": \"...\", \"length\": 5}]}. Ages 8–12.\n"
    "- 'odd_one_out': data: {\"items\": [...], \"answer\": \"...\", \"reason\": \"...\"}. Ages 4–10.\n"
    "- 'fill_in_blank': data: {\"sentences\": [\"The ___ shines.\"]}. Ages 4–9.\n"
    "- 'riddle': data: {\"riddle\": \"...\", \"answer\": \"...\", \"hint\": \"...\"}. Ages 5–12.\n"
    "- 'scramble': data: {\"words\": [{\"scrambled\": \"...\", \"answer\": \"...\", \"hint\": \"...\"}]}. Ages 6–12.\n"
    "- 'true_false': data: {\"questions\": [{\"statement\": \"...\", \"answer\": true}]}. Ages 5–12.\n"
    "- 'sequencing': data: {\"title\": \"...\", \"steps\": [...], \"correct_order\": [1,2,3]}. Ages 4–10.\n"
    "- 'rhyming': data: {\"pairs\": [{\"word\": \"cat\", \"rhymes_with\": \"___\"}]}. Ages 4–8.\n"
    "- 'category_sort': data: {\"categories\": {...}, \"all_items\": [...]}. Ages 4–9.\n\n"

    "AGE-APPROPRIATE CHOICES:\n"
    "- Ages 3–4: number_tracing, letter_tracing, counting, drawing, dot_to_dot, pattern, rhyming\n"
    "- Ages 5–6: counting, drawing, maze, matching, pattern, fill_in_blank, odd_one_out, rhyming, sequencing, category_sort\n"
    "- Ages 7–8: drawing, maze, matching, word_search, math_problems, pattern, scramble, riddle, true_false, sequencing, odd_one_out\n"
    "- Ages 9–12: maze, word_search, math_problems, crossword_clues, scramble, riddle, true_false, odd_one_out, fill_in_blank\n\n"

    "Return ONLY valid JSON, no other text or preamble.\n"
)


class KidsActivityGenerator:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=4096,
            transport='rest',
        )

    def generate_daily_plan(self, profile, target_date=None):
        """Generate ONE day of content: a story + 2 activities per child."""
        if target_date is None:
            target_date = date.today()

        existing = KidsActivityPlan.objects.filter(
            profile=profile,
            week_start_date=target_date,
        ).first()
        if existing and existing.days.exists():
            return existing
        if existing:
            # Empty shell from a failed run — wipe and retry.
            existing.delete()

        # Only children 3 and older get activities — infants/toddlers can't use them.
        children = [c for c in profile.children.all() if c.age >= 3]
        if not children:
            raise ValueError('No children aged 3+ found. Activities are for ages 3 and up.')

        user_message = self._build_prompt(children, target_date)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        parsed = None
        raw_content = ''
        for attempt in range(2):
            response = self.llm.invoke(messages)
            raw_content = response.content
            try:
                parsed = self._parse_response(raw_content)
                break
            except json.JSONDecodeError as e:
                logger.error(f'Kids activities JSON parse attempt {attempt + 1} failed: {e}')
                if attempt == 0:
                    messages.append(HumanMessage(
                        content="Your response was not valid JSON. Return ONLY a complete, valid JSON object, nothing else."
                    ))

        if not parsed:
            raise ValueError('Kids activity generation returned invalid JSON after 2 attempts.')

        theme = parsed.get('theme', 'Today')

        plan = KidsActivityPlan.objects.create(
            profile=profile,
            week_start_date=target_date,
            theme=theme,
            raw_ai_response=raw_content,
        )

        child_map = {c.name.lower(): c for c in children}

        for child_data in parsed.get('children', []):
            child_name = child_data.get('child_name', '').lower()
            child = child_map.get(child_name)
            if not child:
                logger.warning(
                    'AI returned unknown child name: %s, skipping',
                    child_data.get('child_name'),
                )
                continue

            activities = child_data.get('activities', [])[:2]

            KidsActivityDay.objects.create(
                plan=plan,
                child=child,
                day_of_week=0,
                story_title=child_data.get('story_title', ''),
                story_text=child_data.get('story_text', ''),
                story_emoji=child_data.get('story_emoji', '📖'),
                story_illustration=child_data.get('story_illustration', ''),
                worksheet_topic=child_data.get('activity_title', 'Activity Sheet'),
                worksheet_content={'activities': activities},
                coloring_description='',
                unlocked=True,
            )

        return plan

    def _build_prompt(self, children, target_date):
        children_info = []
        for child in children:
            interests = ', '.join(child.interests) if child.interests else 'general'
            children_info.append(
                f"- {child.name}: age {child.age}, interests: {interests}"
            )
        children_block = '\n'.join(children_info)

        diff_reminder = ''
        if len(children) > 1:
            diff_reminder = (
                "\nREMINDER: Multiple children with different ages. Each MUST get:\n"
                "- A DIFFERENT story (different characters, plot, complexity)\n"
                "- DIFFERENT activity types from siblings\n"
                "- Age-appropriate difficulty\n"
            )

        return (
            f"Generate today's activity pack for {target_date.strftime('%A, %B %d, %Y')}.\n\n"
            f"Children:\n{children_block}\n{diff_reminder}\n"
            f"Pick a fun theme. For EACH child: one story + exactly 2 age-appropriate activities.\n\n"
            f"Return this exact JSON structure:\n"
            f'{{\n'
            f'  "theme": "Theme Name",\n'
            f'  "children": [\n'
            f'    {{\n'
            f'      "child_name": "Child Name (exact match)",\n'
            f'      "story_title": "Story Title",\n'
            f'      "story_emoji": "🐰",\n'
            f'      "story_illustration": "Vivid scene description...",\n'
            f'      "story_text": "Full story text...",\n'
            f'      "activity_title": "Title for the activity sheet",\n'
            f'      "activities": [\n'
            f'        {{"type": "drawing", "title": "...", "data": {{"prompt": "..."}}}},\n'
            f'        {{"type": "maze", "title": "...", "data": {{"start_label": "...", "end_label": "..."}}}}\n'
            f'      ]\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f"Include one entry per child ({len(children)} total). Exactly 2 activities each.\n"
            f"Return ONLY the JSON object."
        )

    def _parse_response(self, raw_content):
        content = raw_content.strip()
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        return json.loads(content)
