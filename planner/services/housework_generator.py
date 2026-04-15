import json
import logging
from datetime import date

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import HouseworkList, HouseworkTask, HouseworkTemplate
from .ai_context import AIContextAssembler

logger = logging.getLogger(__name__)

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


class HouseworkGenerator:

    def __init__(self):
        self.llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.6,
            max_output_tokens=2048,
        )

    def generate_housework_list(self, profile, target_date=None):
        """
        Generate a daily housework list.
        1. Add user's recurring template tasks scheduled for this day.
        2. Ask AI to fill in extra tasks (avoiding duplicates with templates).
        Returns existing list if one already exists for this date (idempotent).
        """
        if target_date is None:
            target_date = date.today()

        # Idempotent — return existing list if already generated
        existing = HouseworkList.objects.filter(
            profile=profile,
            date=target_date,
        ).first()
        if existing:
            return existing

        hw_list = HouseworkList.objects.create(
            profile=profile,
            date=target_date,
        )

        # Step 1: Add recurring template tasks for this day
        weekday = target_date.weekday()  # 0=Mon … 6=Sun
        template_names = self._add_template_tasks(hw_list, profile, weekday)

        # Step 2: Ask AI to generate additional tasks
        try:
            ai_tasks = self._generate_ai_tasks(profile, target_date, weekday, template_names)
            for task_name in ai_tasks:
                # Skip if it duplicates a template task
                if task_name.lower() not in [t.lower() for t in template_names]:
                    HouseworkTask.objects.create(
                        housework_list=hw_list,
                        name=task_name,
                    )
        except Exception as e:
            logger.error(f'Housework AI generation failed: {e}')
            # Still return the list — it has template tasks at least

        return hw_list

    def _add_template_tasks(self, hw_list, profile, weekday):
        """Add all active templates that match today's weekday. Returns list of names added."""
        templates = HouseworkTemplate.objects.filter(
            profile=profile,
            is_active=True,
        )

        names = []
        for t in templates:
            # Empty days list = every day
            if not t.days or weekday in t.days:
                HouseworkTask.objects.create(
                    housework_list=hw_list,
                    name=t.name,
                )
                names.append(t.name)
        return names

    def _generate_ai_tasks(self, profile, target_date, weekday, existing_task_names):
        """Call Gemini to generate extra housework tasks for the day."""
        assembler = AIContextAssembler(profile)
        system_prompt = self._build_system_prompt(assembler, profile)
        user_message = self._build_user_message(profile, target_date, weekday, existing_task_names)

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_message),
        ]

        # Try up to 2 times
        for attempt in range(2):
            response = self.llm.invoke(messages)
            raw = response.content.strip()
            try:
                tasks = self._parse_response(raw)
                return tasks
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f'Housework JSON parse attempt {attempt + 1} failed: {e}')
                if attempt == 0:
                    messages.append(HumanMessage(
                        content="Your response was not valid JSON. Return ONLY a valid JSON array of strings, nothing else."
                    ))

        return []

    def _build_system_prompt(self, assembler, profile):
        sections = [
            assembler._base_profile_section(),
        ]

        hw_history = assembler._housework_history_section()
        if hw_history:
            sections.append(hw_history)

        header = (
            "You are Dayo, a smart home management assistant. "
            "You generate practical, personalised daily housework task lists. "
            "You understand real households — what actually needs doing, "
            "how tasks rotate through the week, and what's realistic for one person.\n\n"
        )

        if profile.home_help_type == 'partial_help':
            header += (
                "IMPORTANT: This user has part-time domestic help. "
                "Frame tasks as clear instructions for a helper/maid — "
                "be specific about what to do (e.g. 'Mop all rooms' not just 'Clean floors').\n\n"
            )

        return header + '\n'.join(sections)

    def _build_user_message(self, profile, target_date, weekday, existing_task_names):
        day_name = DAY_NAMES[weekday]
        family = profile.family_size or 1
        is_weekend = weekday >= 5

        # Determine how many AI tasks to add
        template_count = len(existing_task_names)
        if profile.user_type in ('working_mom', 'professional'):
            target_total = 4 if not is_weekend else 6
        else:
            target_total = 6 if not is_weekend else 8

        ai_count = max(2, target_total - template_count)

        existing_text = ""
        if existing_task_names:
            existing_text = (
                f"\n## Already scheduled for today\n"
                f"The user has these recurring tasks set: {', '.join(existing_task_names)}\n"
                f"Do NOT repeat any of these. Generate DIFFERENT tasks.\n"
            )

        return (
            f"Generate {ai_count} housework tasks for {day_name}.\n"
            f"Family size: {family} people\n"
            f"User type: {profile.get_user_type_display()}\n"
            f"{'Weekend — can include deeper cleaning tasks.' if is_weekend else 'Weekday — keep it manageable.'}\n"
            f"{existing_text}\n"
            "Rules:\n"
            "- Short task names (2-4 words)\n"
            "- Use simple action-based tasks like: 'Vacuum and mop', 'Do laundry', 'Wash dishes', 'Dust furniture', 'Take out trash', 'Iron clothes', 'Organise wardrobe', 'Clean mirrors'\n"
            "- Do NOT specify rooms or areas. Say 'Vacuum and mop' NOT 'Vacuum living room'. Say 'Dust furniture' NOT 'Dust bedroom shelves'\n"
            "- Keep it how a real person thinks about chores — simple and direct\n"
            "- Vary tasks day to day\n"
            f"- Return EXACTLY {ai_count} tasks\n\n"
            'Return ONLY a valid JSON array of strings:\n'
            '["Vacuum and mop", "Do laundry", "Wash dishes", "Dust furniture"]\n'
        )

    def _parse_response(self, raw_content):
        content = raw_content
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        parsed = json.loads(content)
        if not isinstance(parsed, list):
            raise ValueError('Expected a JSON array')
        # Ensure all items are strings
        return [str(item).strip() for item in parsed if str(item).strip()]
