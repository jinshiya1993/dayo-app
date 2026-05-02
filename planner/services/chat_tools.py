import json
import logging
from datetime import date

from django.conf import settings
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage, SystemMessage

from ..models import (
    DayPlan, GroceryItem, GroceryList, HouseworkList, HouseworkTask,
    ScheduleEvent,
)

logger = logging.getLogger(__name__)


# ===================================================================
# Tool definitions — schema only, used by bind_tools()
# These are never called directly; executors below do the real work.
# ===================================================================

@tool
def add_grocery_item(name: str, quantity: str = "", category: str = "other") -> str:
    """Add an item to the user's current grocery list.
    Categories: produce, dairy, grains, protein, spices, snacks, other."""
    return ""


@tool
def remove_grocery_item(name: str) -> str:
    """Remove an item from the user's current grocery list by name."""
    return ""


@tool
def swap_meal(meal_type: str, preference: str = "", target_date: str = "") -> str:
    """Swap a meal in the user's plan. meal_type must be breakfast, lunch, or dinner.
    Optionally specify a preference like 'something lighter' or 'South Indian'.
    target_date is YYYY-MM-DD — defaults to today. Pass tomorrow's date to swap
    tomorrow's meal."""
    return ""


@tool
def add_housework_task(name: str) -> str:
    """Add a task to today's housework list."""
    return ""


@tool
def mark_housework_done(task_name: str) -> str:
    """Mark a housework task as completed by name."""
    return ""


@tool
def cancel_schedule_event(title: str) -> str:
    """Cancel a schedule event by its title."""
    return ""


@tool
def add_schedule_event(title: str, event_type: str, start_time: str, event_date: str = "", description: str = "") -> str:
    """Add a new schedule event.
    event_type: personal, appointment, school_drop, child_activity, work_shift, meeting.
    start_time as HH:MM. event_date as YYYY-MM-DD (required for one-off events like 'tomorrow')."""
    return ""


@tool
def add_metime_activity(activity: str, duration_minutes: int = 30) -> str:
    """Add a me-time or self-care activity to today's plan."""
    return ""


@tool
def add_errand(title: str, description: str = "") -> str:
    """Add an errand to today's plan."""
    return ""


@tool
def regenerate_kids_activities(level: str, child_name: str = "") -> str:
    """Set the difficulty level for kids activities and regenerate today's pack.
    level must be one of: easy, standard, advanced, olympiad.
    child_name (optional, case-insensitive) targets a specific child; leave
    empty to apply to all children. Use this when the user asks to make the
    activities harder, easier, olympiad-level, or competition-grade."""
    return ""


@tool
def web_search(query: str) -> str:
    """Search the web for information."""
    return ""


def get_all_tools():
    """Return all tool definitions for bind_tools()."""
    return [
        add_grocery_item,
        remove_grocery_item,
        swap_meal,
        add_housework_task,
        mark_housework_done,
        cancel_schedule_event,
        add_schedule_event,
        add_metime_activity,
        add_errand,
        regenerate_kids_activities,
    ]


# ===================================================================
# Action description — human-readable summary for pending_action
# ===================================================================

def describe_action(tool_name, tool_args):
    """Generate a user-friendly description of a tool call."""
    a = tool_args or {}
    if tool_name == 'add_grocery_item':
        qty = a.get('quantity', '')
        suffix = ' (%s)' % qty if qty else ''
        return 'Add %s%s to your grocery list' % (a.get('name', '?'), suffix)
    if tool_name == 'remove_grocery_item':
        return 'Remove %s from your grocery list' % a.get('name', '?')
    if tool_name == 'swap_meal':
        pref = a.get('preference', '')
        suffix = ' to %s' % pref if pref else ''
        td = a.get('target_date', '')
        if td and td != date.today().strftime('%Y-%m-%d'):
            day_part = '%s\'s ' % td
        else:
            day_part = ''
        return 'Swap %s%s%s' % (day_part, a.get('meal_type', '?'), suffix)
    if tool_name == 'add_housework_task':
        return 'Add "%s" to today\'s housework' % a.get('name', '?')
    if tool_name == 'mark_housework_done':
        return 'Mark "%s" as done' % a.get('task_name', '?')
    if tool_name == 'cancel_schedule_event':
        return 'Cancel the event "%s"' % a.get('title', '?')
    if tool_name == 'add_schedule_event':
        date_part = ' on %s' % a['event_date'] if a.get('event_date') else ''
        return 'Add event "%s" at %s%s' % (a.get('title', '?'), a.get('start_time', '?'), date_part)
    if tool_name == 'add_metime_activity':
        return 'Add me-time: %s (%s mins)' % (a.get('activity', '?'), a.get('duration_minutes', 30))
    if tool_name == 'add_errand':
        return 'Add errand: %s' % a.get('title', '?')
    if tool_name == 'regenerate_kids_activities':
        who = a.get('child_name') or 'all kids'
        return 'Set %s\'s activities to %s level and regenerate today\'s pack' % (
            who, a.get('level', '?')
        )
    if tool_name == 'web_search':
        return 'Search the web for "%s"' % a.get('query', '?')
    return 'Run %s' % tool_name


# ===================================================================
# Executors — actual DB writes, called on confirm
# ===================================================================

def execute_tool(tool_name, args, profile):
    """Route a confirmed action to its executor."""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return {"success": False, "message": f"Unknown action: {tool_name}"}
    try:
        return executor(profile, args)
    except Exception as e:
        logger.error(f"Tool execution error ({tool_name}): {e}")
        return {"success": False, "message": "Something went wrong. Please try again."}


def _execute_add_grocery_item(profile, args):
    grocery_list = GroceryList.objects.filter(
        profile=profile, completed=False
    ).order_by('-generated_at').first()
    if not grocery_list:
        return {"success": False, "message": "No active grocery list. Generate one first from the grocery section."}

    name = args.get('name', '').strip()
    if not name:
        return {"success": False, "message": "Item name is required."}

    existing = GroceryItem.objects.filter(grocery_list=grocery_list, name__iexact=name).first()
    if existing:
        return {"success": False, "message": f"{name} is already in your grocery list."}

    category = args.get('category', 'other')
    valid_categories = [c[0] for c in GroceryItem.Category.choices]
    if category not in valid_categories:
        category = 'other'

    GroceryItem.objects.create(
        grocery_list=grocery_list,
        name=name,
        quantity=args.get('quantity', ''),
        category=category,
    )
    return {"success": True, "message": f"Added {name} to your grocery list."}


def _execute_remove_grocery_item(profile, args):
    grocery_list = GroceryList.objects.filter(
        profile=profile, completed=False
    ).order_by('-generated_at').first()
    if not grocery_list:
        return {"success": False, "message": "No active grocery list."}

    name = args.get('name', '').strip()
    item = GroceryItem.objects.filter(grocery_list=grocery_list, name__iexact=name).first()
    if not item:
        return {"success": False, "message": f"Couldn't find \"{name}\" in your grocery list."}

    item.delete()
    return {"success": True, "message": f"Removed {name} from your grocery list."}


def _execute_swap_meal(profile, args):
    from datetime import datetime as dt
    from .ai_context import AIContextAssembler

    meal_type = args.get('meal_type', '')
    preference = args.get('preference', '')
    target_date_str = args.get('target_date', '')

    if meal_type not in ('breakfast', 'lunch', 'dinner'):
        return {"success": False, "message": "meal_type must be breakfast, lunch, or dinner."}

    if target_date_str:
        try:
            target_date = dt.strptime(target_date_str, '%Y-%m-%d').date()
        except ValueError:
            return {"success": False, "message": f"Invalid date '{target_date_str}'. Use YYYY-MM-DD."}
    else:
        target_date = date.today()

    day_label = "today" if target_date == date.today() else target_date.strftime('%A %b %d')
    try:
        day_plan = DayPlan.objects.get(profile=profile, date=target_date)
    except DayPlan.DoesNotExist:
        return {"success": False, "message": f"No plan for {day_label}. Generate one first."}

    plan_data = day_plan.plan_data or {}
    meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
    meals = plan_data.get(meals_key, {})
    current_name = meals.get(meal_type, {}).get('name', 'unknown')

    assembler = AIContextAssembler(profile)
    context = assembler.build_plan_generation_context(target_date)
    favourites = list(profile.favourite_meals.values_list('meal_name', flat=True)[:10])
    fav_text = f"\nFavourite meals: {', '.join(favourites)}" if favourites else ""

    pref_text = f"\nUser preference: {preference}" if preference else ""

    llm = ChatGoogleGenerativeAI(
        model='gemini-2.5-flash',
        google_api_key=settings.GEMINI_API_KEY,
        temperature=0.8,
        max_output_tokens=2048,
        transport='rest',
    )

    messages = [
        SystemMessage(content=context['system_prompt']),
        HumanMessage(content=(
            f"Swap the user's {meal_type}. Current: '{current_name}' — suggest something DIFFERENT.\n"
            f"Must be balanced and respect dietary preferences.{fav_text}{pref_text}\n\n"
            f"Always include `steps`: 4-8 short imperative cooking instructions, "
            f"and `kcal`: integer calories per single-adult serving.\n"
            f"If the household has differing dietary needs, include an OPTIONAL `pairings` "
            f"array of simple per-person sides (rice, chappathi, salad — never a full recipe). "
            f"Omit pairings entirely when one meal works for everyone.\n\n"
            f"Return ONLY a JSON object:\n"
            f'{{"name": "Meal name", "prep_mins": 20, "kcal": 480, "description": "Brief recipe", "ingredients": ["..."], '
            f'"steps": ["Step 1", "Step 2", "Step 3"], '
            f'"pairings": [{{"for": "Names", "with": "Simple side", "why": "one-line reason"}}]}}\n'
        )),
    ]

    response = llm.invoke(messages)
    content = response.content.strip()
    if '```json' in content:
        content = content.split('```json')[1].split('```')[0].strip()
    elif '```' in content:
        content = content.split('```')[1].split('```')[0].strip()

    new_meal = json.loads(content)
    meals[meal_type] = new_meal
    plan_data[meals_key] = meals
    day_plan.plan_data = plan_data
    day_plan.save()

    prefix = "" if target_date == date.today() else f"{day_label}'s "
    return {"success": True, "message": f"Swapped {prefix}{meal_type} to {new_meal.get('name', 'a new meal')}."}


def _execute_add_housework_task(profile, args):
    today = date.today()
    hw_list = HouseworkList.objects.filter(profile=profile, date=today).first()
    if not hw_list:
        hw_list = HouseworkList.objects.create(profile=profile, date=today)

    name = args.get('name', '').strip()
    if not name:
        return {"success": False, "message": "Task name is required."}

    existing = HouseworkTask.objects.filter(housework_list=hw_list, name__iexact=name).first()
    if existing:
        return {"success": False, "message": f"\"{name}\" is already on today's list."}

    HouseworkTask.objects.create(housework_list=hw_list, name=name, is_user_added=True)
    return {"success": True, "message": f"Added \"{name}\" to today's housework."}


def _execute_mark_housework_done(profile, args):
    today = date.today()
    task_name = args.get('task_name', '').strip()

    task = HouseworkTask.objects.filter(
        housework_list__profile=profile,
        housework_list__date=today,
        name__iexact=task_name,
    ).first()
    if not task:
        return {"success": False, "message": f"Couldn't find \"{task_name}\" in today's housework."}

    task.completed = True
    task.save()
    return {"success": True, "message": f"Marked \"{task_name}\" as done."}


def _execute_cancel_schedule_event(profile, args):
    title = args.get('title', '').strip()
    event = ScheduleEvent.objects.filter(
        profile=profile, is_active=True, title__icontains=title
    ).first()
    if not event:
        return {"success": False, "message": f"Couldn't find an active event matching \"{title}\"."}

    event.is_active = False
    event.save()
    return {"success": True, "message": f"Cancelled \"{event.title}\"."}


def _execute_add_schedule_event(profile, args):
    from datetime import datetime as dt

    title = args.get('title', '').strip()
    event_type = args.get('event_type', 'personal')
    start_time = args.get('start_time', '09:00')
    description = args.get('description', '')
    event_date_str = args.get('event_date', '')

    valid_types = [c[0] for c in ScheduleEvent.EventType.choices]
    if event_type not in valid_types:
        event_type = 'personal'

    # Parse event_date if provided
    event_date = None
    if event_date_str:
        try:
            event_date = dt.strptime(event_date_str, '%Y-%m-%d').date()
        except ValueError:
            event_date = date.today()

    ScheduleEvent.objects.create(
        profile=profile,
        title=title,
        event_type=event_type,
        start_time=start_time,
        description=description,
        recurrence='none',
        event_date=event_date,
    )

    date_label = event_date.strftime('%B %d') if event_date else 'your schedule'
    return {"success": True, "message": f"Added \"{title}\" at {start_time} on {date_label}."}


def _execute_add_metime_activity(profile, args):
    today = date.today()
    try:
        day_plan = DayPlan.objects.get(profile=profile, date=today)
    except DayPlan.DoesNotExist:
        return {"success": False, "message": "No plan for today. Generate one first."}

    plan_data = day_plan.plan_data or {}
    activity = args.get('activity', '')
    duration = args.get('duration_minutes', 30)

    selfcare = plan_data.get('selfcare')
    new_entry = {"activity": activity, "duration": f"{duration} mins"}

    if isinstance(selfcare, list):
        selfcare.append(new_entry)
    elif isinstance(selfcare, dict):
        plan_data['selfcare'] = [selfcare, new_entry]
    else:
        plan_data['selfcare'] = [new_entry]

    day_plan.plan_data = plan_data
    day_plan.save()
    return {"success": True, "message": f"Added \"{activity}\" ({duration} mins) to your me-time."}


def _execute_add_errand(profile, args):
    today = date.today()
    try:
        day_plan = DayPlan.objects.get(profile=profile, date=today)
    except DayPlan.DoesNotExist:
        return {"success": False, "message": "No plan for today. Generate one first."}

    plan_data = day_plan.plan_data or {}
    title = args.get('title', '')
    description = args.get('description', '')

    errands = plan_data.get('errands', [])
    if not isinstance(errands, list):
        errands = []

    errands.append({"title": title, "description": description, "done": False})
    plan_data['errands'] = errands
    day_plan.plan_data = plan_data
    day_plan.save()
    return {"success": True, "message": f"Added errand: \"{title}\"."}


def _execute_regenerate_kids_activities(profile, args):
    from ..models import HouseholdMember, KidsActivityPlan
    from .kids_activity_generator import KidsActivityGenerator

    level = (args.get('level') or '').strip().lower()
    valid = [c[0] for c in HouseholdMember.ActivityDifficulty.choices]
    if level not in valid:
        return {"success": False, "message": f"Level must be one of: {', '.join(valid)}."}

    child_name = (args.get('child_name') or '').strip()
    children_qs = HouseholdMember.objects.filter(parent=profile, role='child')
    if child_name:
        target = children_qs.filter(name__iexact=child_name)
        if not target.exists():
            return {"success": False, "message": f"No child named '{child_name}'."}
    else:
        target = children_qs

    if not target.exists():
        return {"success": False, "message": "You don't have any children on your profile."}

    target.update(activity_difficulty=level)

    today = date.today()
    KidsActivityPlan.objects.filter(profile=profile, week_start_date=today).delete()

    try:
        KidsActivityGenerator().generate_daily_plan(profile, target_date=today)
    except ValueError as e:
        return {"success": False, "message": str(e)}
    except Exception as e:
        logger.error(f"Kids activity regeneration failed: {e}")
        return {"success": False, "message": "Couldn't regenerate the activities. Please try again."}

    who = child_name if child_name else "all kids"
    return {"success": True, "message": f"Set {who}'s activities to {level} level and regenerated today's pack."}


def _execute_web_search(profile, args):
    return {"success": False, "message": "Web search is coming soon."}


# ===================================================================
# Registry
# ===================================================================

TOOL_EXECUTORS = {
    'add_grocery_item': _execute_add_grocery_item,
    'remove_grocery_item': _execute_remove_grocery_item,
    'swap_meal': _execute_swap_meal,
    'add_housework_task': _execute_add_housework_task,
    'mark_housework_done': _execute_mark_housework_done,
    'cancel_schedule_event': _execute_cancel_schedule_event,
    'add_schedule_event': _execute_add_schedule_event,
    'add_metime_activity': _execute_add_metime_activity,
    'add_errand': _execute_add_errand,
    'regenerate_kids_activities': _execute_regenerate_kids_activities,
    'web_search': _execute_web_search,
}
