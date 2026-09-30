# Data migration: purge stale MealPlan rows.
#
# Plan regeneration used to APPEND MealPlan rows instead of replacing them,
# and meal swap/rename only updated plan_data — so a day could accumulate
# many meal rows per slot (locally we found days with 9 breakfasts). The
# grocery generator reads MealPlan rows, so users were getting grocery items
# for meals that were long gone from their visible plan.
#
# For every day plan, keep at most one row per meal slot: the row whose name
# matches the current plan_data meal (the one the user actually sees), or
# the newest row when plan_data has no name for that slot. Everything else
# is stale and gets deleted.

from django.db import migrations


def cleanup_stale_meal_rows(apps, schema_editor):
    DayPlan = apps.get_model('planner', 'DayPlan')
    MealPlan = apps.get_model('planner', 'MealPlan')

    deleted_total = 0
    for day_plan in DayPlan.objects.all().iterator():
        plan_data = day_plan.plan_data or {}
        meals_data = plan_data.get('meals') or plan_data.get('mom_meals') or {}

        rows_by_slot = {}
        for row in MealPlan.objects.filter(day_plan=day_plan).order_by('-id'):
            rows_by_slot.setdefault(row.meal_type, []).append(row)

        for meal_type, rows in rows_by_slot.items():
            if len(rows) == 1 and not meals_data:
                continue

            current = meals_data.get(meal_type) if isinstance(meals_data, dict) else None
            current_name = (current or {}).get('name', '').strip().lower() if isinstance(current, dict) else ''

            keeper = None
            if current_name:
                for row in rows:  # newest first
                    if (row.name or '').strip().lower() == current_name:
                        keeper = row
                        break
            if keeper is None:
                # No match against plan_data (meal renamed slightly, or no
                # plan_data name) — keep the newest row rather than none.
                keeper = rows[0]

            stale_ids = [r.id for r in rows if r.id != keeper.id]
            if stale_ids:
                deleted_total += len(stale_ids)
                MealPlan.objects.filter(id__in=stale_ids).delete()

    if deleted_total:
        print(f'  Deleted {deleted_total} stale MealPlan rows')


class Migration(migrations.Migration):

    dependencies = [
        ('planner', '0038_remove_working_mom_type'),
    ]

    operations = [
        # No reverse: the stale rows are junk data, nothing to restore.
        migrations.RunPython(cleanup_stale_meal_rows, migrations.RunPython.noop),
    ]
