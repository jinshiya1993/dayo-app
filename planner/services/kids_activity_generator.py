import json
import logging
from datetime import date, timedelta

from django.conf import settings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from planner.models import Child, KidsActivityDay, KidsActivityPlan

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = (
    "You are Dayo, a creative children's activity planner. "
    "You generate weekly themed activity packs for children. Each day includes:\n"
    "1. A short story (read on screen by parent) with an illustration description\n"
    "2. A set of 3 printable activities (for a PDF activity sheet)\n\n"

    "CRITICAL RULE — EVERY CHILD GETS UNIQUE CONTENT:\n"
    "- Each child must get COMPLETELY DIFFERENT stories, activities, and content\n"
    "- A 3-year-old and a 9-year-old must NEVER get the same activity type on the same day\n"
    "- Tailor everything to each child's specific age and interests\n"
    "- The weekly theme is shared, but HOW it's explored is different per child\n\n"

    "STORY RULES:\n"
    "- SAFETY FIRST: Stories must be warm, positive, and age-appropriate. "
    "NEVER include: scary content, villains, violence, death, danger, dark themes, "
    "bullying, exclusion, sadness, or anything that could frighten or upset a child.\n"
    "- Every story must have a happy, reassuring ending.\n"
    "- Stories should teach a gentle lesson (kindness, curiosity, sharing, trying new things, etc.)\n\n"

    "Age-specific story guidelines:\n"
    "- Ages 3–4: ~80–100 words. Very simple 3–5 word sentences. "
    "Use only words a 3-year-old knows. Cute animal characters (bunny, kitten, duckling). "
    "Repetitive patterns ('hop hop hop', 'one, two, three!'). "
    "Themes: sharing, bedtime, friendship, playing, helping.\n"
    "- Ages 5–6: ~120–150 words. Short sentences, simple vocabulary. "
    "Characters can be children or talking animals. "
    "Light adventure (finding something, going on a walk, making something). "
    "Themes: being brave, making friends, learning something new.\n"
    "- Ages 7–8: ~200–250 words. Intermediate vocabulary, compound sentences OK. "
    "Characters solve a small problem together. "
    "Themes: teamwork, curiosity, discovery, creativity, overcoming a small challenge.\n"
    "- Ages 9–10: ~300–350 words. Richer language, can include dialogue. "
    "Characters face a puzzle or mystery to solve. "
    "Themes: problem-solving, empathy, responsibility, clever thinking.\n"
    "- Ages 11–12: ~350–400 words. More complex narrative structure. "
    "Can include mild suspense (who left the message? what's behind the door?). "
    "Themes: independence, standing up for others, ingenuity, adventure.\n\n"

    "- Each story needs a 'story_emoji' — one emoji that represents the main character or scene\n"
    "- Each story needs a 'story_illustration' — a vivid, detailed description of the key scene "
    "(e.g. 'A small brown rabbit sitting under a giant mushroom in a glowing forest, "
    "with fireflies floating around and a tiny door in the mushroom stem')\n"
    "- Make illustration descriptions visual and specific — they will be shown as scene cards\n\n"

    "ACTIVITY RULES — generate exactly 3 activities per day per child:\n"
    "Activity types available:\n"
    "- 'number_tracing': Numbers to trace. data: {\"numbers\": [1,2,3]}. Ages 3–5 ONLY.\n"
    "- 'letter_tracing': Letters to trace. data: {\"letters\": [\"A\",\"B\"]}. Ages 3–6 ONLY.\n"
    "- 'counting': Counting exercise. data: {\"prompt\": \"...\", \"answer\": 5}. Ages 3–7.\n"
    "- 'drawing': Drawing prompt. data: {\"prompt\": \"Draw a ...\"}. ALL ages.\n"
    "- 'maze': A maze puzzle. data: {\"start_label\": \"Mouse\", \"end_label\": \"Cheese\"}. ALL ages.\n"
    "- 'matching': Match items. data: {\"left\": [...], \"right\": [...]}. Ages 4–8.\n"
    "- 'dot_to_dot': Connect dots. data: {\"total_dots\": 10, \"reveal\": \"a star\"}. Ages 3–7.\n"
    "- 'word_search': Find words in a grid. data: {\"words\": [\"CAT\",\"DOG\"]}. Ages 6–12.\n"
    "- 'math_problems': Math equations. data: {\"problems\": [\"3 + 2 = __\"]}. Ages 5–12.\n"
    "- 'pattern': Complete pattern. data: {\"sequence\": \"🔴🔵🔴🔵🔴__\"}. Ages 3–8.\n"
    "- 'crossword_clues': Word clues. data: {\"clues\": [{\"clue\": \"...\", \"answer\": \"...\", \"length\": 5}]}. Ages 8–12.\n"
    "- 'odd_one_out': Which item doesn't belong? data: {\"items\": [\"Apple\",\"Banana\",\"Chair\",\"Mango\"], \"answer\": \"Chair\", \"reason\": \"Not a fruit\"}. Ages 4–10.\n"
    "- 'fill_in_blank': Complete the sentence. data: {\"sentences\": [\"The ___ shines in the sky.\", \"Birds can ___.\"]}. Ages 4–9.\n"
    "- 'riddle': Fun riddle with answer. data: {\"riddle\": \"I have hands but can't clap. What am I?\", \"answer\": \"A clock\", \"hint\": \"Tick tock!\"}. Ages 5–12.\n"
    "- 'scramble': Unscramble letters to make a word. data: {\"words\": [{\"scrambled\": \"PLPEA\", \"answer\": \"APPLE\", \"hint\": \"A fruit\"}, ...]}. Ages 6–12.\n"
    "- 'true_false': True or False questions. data: {\"questions\": [{\"statement\": \"The sun is a star\", \"answer\": true}, ...]}. Ages 5–12.\n"
    "- 'sequencing': Put steps in the right order. data: {\"title\": \"How to make a sandwich\", \"steps\": [\"Put bread on plate\", \"Add cheese\", \"Put bread on top\", \"Eat!\"], \"correct_order\": [1,2,3,4]}. Ages 4–10.\n"
    "- 'rhyming': Find or write rhyming words. data: {\"pairs\": [{\"word\": \"cat\", \"rhymes_with\": \"___\"}, {\"word\": \"tree\", \"rhymes_with\": \"___\"}]}. Ages 4–8.\n"
    "- 'category_sort': Sort items into categories. data: {\"categories\": {\"Fruits\": [\"Apple\", \"Banana\"], \"Vegetables\": [\"Carrot\", \"Pea\"]}, \"all_items\": [\"Apple\", \"Carrot\", \"Banana\", \"Pea\"]}. Ages 4–9.\n\n"

    "AGE-APPROPRIATE ACTIVITY SELECTION:\n"
    "- Ages 3–4: number_tracing, letter_tracing, counting, drawing, dot_to_dot, pattern, rhyming\n"
    "- Ages 5–6: counting, drawing, maze, matching, pattern, fill_in_blank, odd_one_out, rhyming, sequencing, category_sort\n"
    "- Ages 7–8: drawing, maze, matching, word_search, math_problems, pattern, scramble, riddle, true_false, sequencing, odd_one_out\n"
    "- Ages 9–12: maze, word_search, math_problems, crossword_clues, scramble, riddle, true_false, odd_one_out, fill_in_blank\n\n"

    "DIFFERENTIATION EXAMPLES:\n"
    "- Theme 'Ocean': 3yo gets 'dot-to-dot fish', 7yo gets 'word search with ocean terms', 10yo gets 'riddle about sea creatures'\n"
    "- Theme 'Space': 4yo gets 'dot-to-dot star (8 dots)', 8yo gets 'scramble space words', 10yo gets 'true/false about planets'\n"
    "- Theme 'Food': 5yo gets 'category_sort fruits vs vegetables', 9yo gets 'crossword clues about cooking'\n"
    "- NEVER give the same activity title or content to siblings on the same day\n"
    "- Vary activity types across the week — don't repeat the same type two days in a row for a child\n\n"

    "Return ONLY valid JSON, no other text or preamble.\n"
)


class KidsActivityGenerator:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=8192,
            transport='rest',
        )

    def generate_weekly_plan(self, profile, week_start=None):
        """Generate a full week (Mon–Fri) of kids activities for all children."""

        if week_start is None:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())

        existing = KidsActivityPlan.objects.filter(
            profile=profile,
            week_start_date=week_start,
        ).first()
        if existing:
            return existing

        children = list(profile.children.all())
        if not children:
            raise ValueError('No children found. Add children to your profile first.')

        user_message = self._build_prompt(children, week_start)

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        response = self.llm.invoke(messages)
        raw_content = response.content
        parsed = self._parse_response(raw_content)

        theme = parsed.get('theme', 'Fun Week')

        plan = KidsActivityPlan.objects.create(
            profile=profile,
            week_start_date=week_start,
            theme=theme,
            raw_ai_response=raw_content,
        )

        child_map = {c.name.lower(): c for c in children}

        for day_data in parsed.get('days', []):
            child_name = day_data.get('child_name', '').lower()
            child = child_map.get(child_name)

            if not child:
                logger.warning(
                    'AI returned unknown child name: %s, skipping',
                    day_data.get('child_name'),
                )
                continue

            day_of_week = day_data.get('day', 0)
            if day_of_week < 0 or day_of_week > 4:
                continue

            activities = day_data.get('activities', [])

            KidsActivityDay.objects.create(
                plan=plan,
                child=child,
                day_of_week=day_of_week,
                story_title=day_data.get('story_title', ''),
                story_text=day_data.get('story_text', ''),
                story_emoji=day_data.get('story_emoji', '📖'),
                story_illustration=day_data.get('story_illustration', ''),
                worksheet_topic=day_data.get('activity_title', 'Activity Sheet'),
                worksheet_content={'activities': activities},
                coloring_description='',
            )

        plan.initialize_unlock()

        return plan

    def regenerate_for_child(self, plan, child):
        """Regenerate 5 fresh days for one child within an existing plan."""
        # Delete the child's completed days
        plan.days.filter(child=child).delete()

        # Build a single-child prompt reusing the plan's theme
        interests = ', '.join(child.interests) if child.interests else 'general'
        week_start = plan.week_start_date
        week_end = week_start + timedelta(days=4)

        user_message = (
            f"Generate a fresh week of activities for ONE child.\n\n"
            f"Child: {child.name}, age {child.age}, interests: {interests}\n"
            f"Week: {week_start.strftime('%B %d, %Y')} to {week_end.strftime('%B %d, %Y')}\n"
            f"Theme: {plan.theme}\n\n"
            f"Create activities for Monday through Friday (days 0–4).\n"
            f"Use the theme '{plan.theme}' but make ALL content COMPLETELY NEW — "
            f"different stories, different activities from what was generated before.\n\n"
            f"Return this exact JSON structure:\n"
            f'{{\n'
            f'  "days": [\n'
            f'    {{\n'
            f'      "child_name": "{child.name}",\n'
            f'      "day": 0,\n'
            f'      "story_title": "Story Title",\n'
            f'      "story_emoji": "🐰",\n'
            f'      "story_illustration": "A vivid scene description...",\n'
            f'      "story_text": "Full story text...",\n'
            f'      "activity_title": "Title for the activity sheet",\n'
            f'      "activities": [... 3 activities ...]\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f"Include 5 entries (days 0–4), each with exactly 3 age-appropriate activities.\n"
            f"Return ONLY the JSON object."
        )

        messages = [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ]

        response = self.llm.invoke(messages)
        parsed = self._parse_response(response.content)

        for day_data in parsed.get('days', []):
            day_of_week = day_data.get('day', 0)
            if day_of_week < 0 or day_of_week > 4:
                continue

            activities = day_data.get('activities', [])
            KidsActivityDay.objects.create(
                plan=plan,
                child=child,
                day_of_week=day_of_week,
                story_title=day_data.get('story_title', ''),
                story_text=day_data.get('story_text', ''),
                story_emoji=day_data.get('story_emoji', '📖'),
                story_illustration=day_data.get('story_illustration', ''),
                worksheet_topic=day_data.get('activity_title', 'Activity Sheet'),
                worksheet_content={'activities': activities},
                coloring_description='',
            )

        # Unlock day 0 for this child
        plan.days.filter(child=child, day_of_week=0).update(unlocked=True)

        return plan

    def _build_prompt(self, children, week_start):
        week_end = week_start + timedelta(days=4)

        children_info = []
        for child in children:
            interests = ', '.join(child.interests) if child.interests else 'general'
            children_info.append(
                f"- {child.name}: age {child.age}, interests: {interests}"
            )

        children_block = '\n'.join(children_info)

        # Build differentiation reminder per child pair
        diff_reminder = ''
        if len(children) > 1:
            diff_reminder = (
                "\n\nREMINDER: You have multiple children with different ages. "
                "Each child MUST get:\n"
                "- A DIFFERENT story (different characters, plot, complexity)\n"
                "- DIFFERENT activity types (don't give maze to both on the same day)\n"
                "- Age-appropriate difficulty (a 3yo's drawing prompt is simpler than a 9yo's)\n"
            )

        return (
            f"Generate a weekly activity pack for the week of "
            f"{week_start.strftime('%B %d, %Y')} to {week_end.strftime('%B %d, %Y')}.\n\n"
            f"Children:\n{children_block}\n"
            f"{diff_reminder}\n"
            f"Create activities for Monday through Friday (days 0–4).\n"
            f"Pick a fun, creative weekly theme that connects to the children's interests.\n\n"
            f"Return this exact JSON structure:\n"
            f'{{\n'
            f'  "theme": "Theme Name",\n'
            f'  "days": [\n'
            f'    {{\n'
            f'      "child_name": "Child Name (exact match)",\n'
            f'      "day": 0,\n'
            f'      "story_title": "Story Title",\n'
            f'      "story_emoji": "🐰",\n'
            f'      "story_illustration": "A vivid, detailed description of the key scene in the story...",\n'
            f'      "story_text": "Full story text...",\n'
            f'      "activity_title": "Title for the activity sheet",\n'
            f'      "activities": [\n'
            f'        {{\n'
            f'          "type": "drawing",\n'
            f'          "title": "Draw a rocket",\n'
            f'          "data": {{"prompt": "Draw your own rocket ship!"}}\n'
            f'        }},\n'
            f'        {{\n'
            f'          "type": "maze",\n'
            f'          "title": "Help the astronaut",\n'
            f'          "data": {{"start_label": "Astronaut", "end_label": "Spaceship"}}\n'
            f'        }},\n'
            f'        {{\n'
            f'          "type": "riddle",\n'
            f'          "title": "Space Riddle",\n'
            f'          "data": {{"riddle": "I have rings but no fingers. What am I?", "answer": "Saturn", "hint": "A planet!"}}\n'
            f'        }}\n'
            f'      ]\n'
            f'    }}\n'
            f'  ]\n'
            f'}}\n\n'
            f"Include one entry per child per day (Monday=0 through Friday=4).\n"
            f"That means {len(children)} children × 5 days = {len(children) * 5} entries.\n"
            f"Each day must have exactly 3 activities, age-appropriate for that specific child.\n"
            f"Return ONLY the JSON object."
        )

    def _parse_response(self, raw_content):
        content = raw_content.strip()
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()
        return json.loads(content)
