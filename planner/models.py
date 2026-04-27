from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone


# -------------------------------------------------------------------
# 1. UserProfile
# -------------------------------------------------------------------
class UserProfile(models.Model):
    class UserType(models.TextChoices):
        HOMEMAKER = 'homemaker', 'Homemaker'
        PARENT = 'parent', 'Homemaker with Kids'
        NEW_MOM = 'new_mom', 'New Mom (Infant)'
        WORKING_MOM = 'working_mom', 'Working Mom'

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='profile',
    )
    user_type = models.CharField(
        max_length=20,
        choices=UserType.choices,
        default=UserType.PARENT,
    )
    display_name = models.CharField(max_length=100)
    timezone = models.CharField(max_length=50, default='Asia/Kolkata')
    wake_time = models.TimeField(default='06:00')
    sleep_time = models.TimeField(default='22:00')
    dietary_restrictions = models.JSONField(default=list, blank=True)
    cuisine_preferences = models.JSONField(default=list, blank=True)
    custom_cuisines = models.TextField(
        blank=True,
        help_text='Free text for specific cuisines not in the list',
    )

    # Meal-specific preferences
    class MealWeight(models.TextChoices):
        LIGHT = 'light', 'Light'
        MEDIUM = 'medium', 'Medium'
        HEAVY = 'heavy', 'Heavy'

    breakfast_weight = models.CharField(
        max_length=10, choices=MealWeight.choices,
        default=MealWeight.LIGHT,
    )
    breakfast_types = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["South Indian", "English", "Continental"]',
    )
    lunch_weight = models.CharField(
        max_length=10, choices=MealWeight.choices,
        default=MealWeight.HEAVY,
    )
    lunch_types = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["Rice based", "Roti based", "One pot"]',
    )
    dinner_weight = models.CharField(
        max_length=10, choices=MealWeight.choices,
        default=MealWeight.LIGHT,
    )
    dinner_types = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["Soup & bread", "Salad", "Light curry"]',
    )
    snack_preferences = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["Fruits", "Homemade", "Baked"]',
    )

    # Planning modules — what sections to show on dashboard / include in AI plans
    planning_modules = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["meals", "grocery", "exercise", "kids_activities"]',
    )
    module_preferences = models.JSONField(
        default=dict, blank=True,
        help_text='Per-module preferences: {"exercise": {"types": ["Gym"], "time": "morning"}}',
    )
    custom_layout = models.JSONField(
        default=list, blank=True,
        help_text='User-customised dashboard layout: [{"key": "meal_cards", "visible": true, "locked": false}]',
    )

    # Grocery & exclusions
    grocery_day = models.CharField(max_length=10, default='', blank=True)

    class GroceryFrequency(models.TextChoices):
        WEEKLY = 'weekly', 'Weekly'
        BIWEEKLY = 'biweekly', 'Every 2 weeks'
        MONTHLY = 'monthly', 'Monthly'

    grocery_frequency = models.CharField(
        max_length=10,
        choices=GroceryFrequency.choices,
        default=GroceryFrequency.WEEKLY,
    )
    exclusions = models.JSONField(
        default=list, blank=True,
        help_text='Things to exclude from day plan',
    )

    # Health & family
    health_conditions = models.JSONField(
        default=list, blank=True,
        help_text='e.g. ["PCOS", "thyroid", "high protein diet", "iron deficiency"]',
    )
    family_size = models.PositiveIntegerField(
        default=1,
        help_text='Number of people she cooks for (including herself)',
    )

    # Housework / home help
    class HomeHelpType(models.TextChoices):
        SELF = 'self', 'I do everything myself'
        PARTIAL = 'partial_help', 'I have part-time help'
        FULL = 'full_maid', 'I have full-time help'

    home_help_type = models.CharField(
        max_length=15,
        choices=HomeHelpType.choices,
        default=HomeHelpType.SELF,
    )

    # New mom specific
    baby_name = models.CharField(max_length=50, blank=True)
    baby_date_of_birth = models.DateField(null=True, blank=True)
    is_breastfeeding = models.BooleanField(default=False)
    had_csection = models.BooleanField(default=False)

    class SupportType(models.TextChoices):
        PARTNER_ALL_DAY = 'partner_all_day', 'Partner home all day'
        PARTNER_AFTER_6 = 'partner_after_6', 'Partner home after 6pm'
        FAMILY_VISITING = 'family_visiting', 'Family visiting'
        HEALTH_VISITOR = 'health_visitor', 'Health visitor'
        FLYING_SOLO = 'flying_solo', 'Mostly on my own'

    support_type = models.CharField(
        max_length=20,
        choices=SupportType.choices,
        blank=True,
        default='',
    )

    location_city = models.CharField(max_length=100, blank=True)
    # Primary life-situation flag. Drives work-related dashboard sections
    # (priorities / evening_routine). All other personalisation is
    # derived from children ages in Child rows.
    works_outside_home = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    onboarding_complete = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.display_name} ({self.get_user_type_display()})'


# -------------------------------------------------------------------
# 2. Child
# -------------------------------------------------------------------
class Child(models.Model):
    class ActivityDifficulty(models.TextChoices):
        EASY = 'easy', 'Easy'
        STANDARD = 'standard', 'Standard'
        ADVANCED = 'advanced', 'Advanced'
        OLYMPIAD = 'olympiad', 'Olympiad'

    parent = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='children',
    )
    name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    interests = models.JSONField(default=list, blank=True)
    school_name = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)
    activity_difficulty = models.CharField(
        max_length=20,
        choices=ActivityDifficulty.choices,
        default=ActivityDifficulty.STANDARD,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def __str__(self):
        return f'{self.name} (age {self.age})'


# -------------------------------------------------------------------
# 3. ScheduleEvent
# -------------------------------------------------------------------
class ScheduleEvent(models.Model):
    class EventType(models.TextChoices):
        # Universal
        PERSONAL = 'personal', 'Personal'
        APPOINTMENT = 'appointment', 'Appointment'
        # Parent
        SCHOOL_DROP = 'school_drop', 'School Drop-off'
        SCHOOL_PICK = 'school_pick', 'School Pick-up'
        CHILD_ACTIVITY = 'child_activity', 'Child Activity/Class'
        # Student
        CLASS = 'class', 'Class/Lecture'
        STUDY = 'study', 'Study Session'
        EXAM = 'exam', 'Exam'
        ASSIGNMENT_DUE = 'assignment_due', 'Assignment Due'
        # Professional
        WORK_SHIFT = 'work_shift', 'Work Shift'
        MEETING = 'meeting', 'Meeting'

    class RecurrenceRule(models.TextChoices):
        NONE = 'none', 'One-time'
        DAILY = 'daily', 'Daily'
        WEEKDAYS = 'weekdays', 'Weekdays (Mon–Fri)'
        WEEKLY = 'weekly', 'Weekly'
        CUSTOM = 'custom', 'Custom Days'

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='schedule_events',
    )
    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='events',
    )
    event_type = models.CharField(max_length=20, choices=EventType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=300, blank=True)
    travel_time_minutes = models.PositiveIntegerField(default=0)
    recurrence = models.CharField(
        max_length=10,
        choices=RecurrenceRule.choices,
        default=RecurrenceRule.NONE,
    )
    recurrence_days = models.JSONField(
        default=list,
        blank=True,
        help_text='For custom recurrence: [0,2,4] = Mon,Wed,Fri',
    )
    event_date = models.DateField(
        null=True, blank=True,
        help_text='For one-off events: the specific date this event occurs on',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.title} ({self.get_event_type_display()})'


# -------------------------------------------------------------------
# 4. DayPlan
# -------------------------------------------------------------------
class DayPlan(models.Model):
    class Status(models.TextChoices):
        GENERATING = 'generating', 'Generating'
        READY = 'ready', 'Ready'
        MODIFIED = 'modified', 'User Modified'
        FAILED = 'failed', 'Generation Failed'

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='day_plans',
    )
    date = models.DateField()
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.GENERATING,
    )
    raw_ai_response = models.TextField(blank=True)
    plan_data = models.JSONField(
        default=dict, blank=True,
        help_text='User-type-specific structured plan JSON',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ['profile', 'date']
        ordering = ['-date']

    def __str__(self):
        return f'Plan for {self.profile.display_name} on {self.date}'


# -------------------------------------------------------------------
# 5. PlanBlock
# -------------------------------------------------------------------
class PlanBlock(models.Model):
    class BlockType(models.TextChoices):
        WAKE_UP = 'wake_up', 'Wake Up'
        MEAL = 'meal', 'Meal'
        ACTIVITY = 'activity', 'Activity'
        CHILD_CARE = 'child_care', 'Child Care'
        TRAVEL = 'travel', 'Travel/Commute'
        WORK = 'work', 'Work'
        STUDY = 'study', 'Study'
        EXERCISE = 'exercise', 'Exercise'
        FREE_TIME = 'free_time', 'Free Time'
        ERRAND = 'errand', 'Errand'
        SLEEP = 'sleep', 'Wind Down / Sleep'

    day_plan = models.ForeignKey(
        DayPlan,
        on_delete=models.CASCADE,
        related_name='blocks',
    )
    block_type = models.CharField(max_length=20, choices=BlockType.choices)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    order = models.PositiveIntegerField()
    is_fixed = models.BooleanField(default=False)
    linked_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    child = models.ForeignKey(
        Child,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    completed = models.BooleanField(default=False)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f'{self.start_time} – {self.title}'


# -------------------------------------------------------------------
# 6. MealPlan
# -------------------------------------------------------------------
class MealPlan(models.Model):
    class MealType(models.TextChoices):
        BREAKFAST = 'breakfast', 'Breakfast'
        LUNCH = 'lunch', 'Lunch'
        SNACK = 'snack', 'Snack'
        DINNER = 'dinner', 'Dinner'

    day_plan = models.ForeignKey(
        DayPlan,
        on_delete=models.CASCADE,
        related_name='meals',
    )
    meal_type = models.CharField(max_length=10, choices=MealType.choices)
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    prep_time_minutes = models.PositiveIntegerField(default=0)
    ingredients = models.JSONField(default=list, blank=True)

    class Meta:
        ordering = ['meal_type']

    def __str__(self):
        return f'{self.get_meal_type_display()}: {self.name}'


# -------------------------------------------------------------------
# 7. GroceryList + GroceryItem
# -------------------------------------------------------------------
class GroceryList(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='grocery_lists',
    )
    week_start_date = models.DateField()
    completed = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at']

    def __str__(self):
        return f'Groceries for week of {self.week_start_date}'


class GroceryItem(models.Model):
    class Category(models.TextChoices):
        PRODUCE = 'produce', 'Fruits & Vegetables'
        DAIRY = 'dairy', 'Dairy'
        GRAINS = 'grains', 'Grains & Cereals'
        PROTEIN = 'protein', 'Protein'
        SPICES = 'spices', 'Spices & Condiments'
        SNACKS = 'snacks', 'Snacks'
        OTHER = 'other', 'Other'

    grocery_list = models.ForeignKey(
        GroceryList,
        on_delete=models.CASCADE,
        related_name='items',
    )
    name = models.CharField(max_length=200)
    quantity = models.CharField(max_length=50, blank=True)
    category = models.CharField(
        max_length=10,
        choices=Category.choices,
        default=Category.OTHER,
    )
    checked = models.BooleanField(default=False)
    is_user_added = models.BooleanField(default=False)

    class Meta:
        ordering = ['category', 'name']

    def __str__(self):
        return f'{self.name} ({self.quantity})'


# -------------------------------------------------------------------
# 8. HouseworkList + HouseworkTask
# -------------------------------------------------------------------
class HouseworkList(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='housework_lists',
    )
    date = models.DateField()
    completed = models.BooleanField(default=False)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['profile', 'date']
        ordering = ['-date']

    def __str__(self):
        return f'Housework for {self.date}'


class HouseworkTask(models.Model):
    housework_list = models.ForeignKey(
        HouseworkList,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    name = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
    is_user_added = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class HouseworkTemplate(models.Model):
    """Recurring housework task set by the user.
    e.g. 'Clean bathroom' on [1, 4] (Monday, Thursday).
    Days use Python weekday(): 0=Monday … 6=Sunday.
    An empty list means every day.
    """
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='housework_templates',
    )
    name = models.CharField(max_length=200)
    days = models.JSONField(
        default=list, blank=True,
        help_text='Weekdays: 0=Mon,1=Tue,2=Wed,3=Thu,4=Fri,5=Sat,6=Sun. Empty=every day.',
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.name} ({self.profile.display_name})'


class HouseworkTaskDeletionLog(models.Model):
    """Tracks housework tasks the user explicitly removed — used by AI to avoid suggesting disliked tasks."""
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='housework_deletion_logs',
    )
    task_name = models.CharField(max_length=200)
    was_ai_generated = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deleted_at']

    def __str__(self):
        return f'{self.task_name} (deleted)'


# -------------------------------------------------------------------
# 8b. CustomSectionList + CustomSectionTask
# -------------------------------------------------------------------
class CustomSectionList(models.Model):
    """Daily checklist for a user-created custom section (e.g. Garden Care, Pet Care)."""
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='custom_section_lists',
    )
    section_key = models.CharField(max_length=100)
    date = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['profile', 'section_key', 'date']
        ordering = ['-date']

    def __str__(self):
        return f'{self.section_key} for {self.date}'


class CustomSectionTask(models.Model):
    section_list = models.ForeignKey(
        CustomSectionList,
        on_delete=models.CASCADE,
        related_name='tasks',
    )
    name = models.CharField(max_length=200)
    completed = models.BooleanField(default=False)
    is_user_added = models.BooleanField(default=False)

    class Meta:
        ordering = ['id']

    def __str__(self):
        return self.name


class CustomSectionDeletionLog(models.Model):
    """Tracks custom section tasks the user removed — used by AI to learn preferences."""
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='custom_section_deletion_logs',
    )
    section_key = models.CharField(max_length=100)
    task_name = models.CharField(max_length=200)
    was_ai_generated = models.BooleanField(default=True)
    deleted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-deleted_at']

    def __str__(self):
        return f'{self.task_name} (deleted from {self.section_key})'


# -------------------------------------------------------------------
# 8c. EssentialsCheck — persisted daily checklist for new moms
# -------------------------------------------------------------------
class EssentialsCheck(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='essentials_checks',
    )
    date = models.DateField()
    item = models.CharField(max_length=100)
    is_checked = models.BooleanField(default=False)
    checked_at = models.DateTimeField(null=True, blank=True)
    added_to_grocery = models.BooleanField(default=False)

    class Meta:
        unique_together = ['profile', 'date', 'item']
        ordering = ['id']

    def __str__(self):
        status = 'checked' if self.is_checked else 'unchecked'
        return f'{self.item} ({status}) on {self.date}'


# -------------------------------------------------------------------
# 9. ChatConversation + ChatMessage
# -------------------------------------------------------------------
class ChatConversation(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='conversations',
    )
    title = models.CharField(max_length=200, default='New Chat')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-updated_at']

    def __str__(self):
        return f'{self.title} – {self.profile.display_name}'


class ChatMessage(models.Model):
    class Role(models.TextChoices):
        USER = 'user', 'User'
        ASSISTANT = 'assistant', 'Assistant'
        SYSTEM = 'system', 'System'

    class ActionStatus(models.TextChoices):
        NONE = 'none', 'None'
        PENDING = 'pending', 'Pending'
        CONFIRMED = 'confirmed', 'Confirmed'
        CANCELLED = 'cancelled', 'Cancelled'

    conversation = models.ForeignKey(
        ChatConversation,
        on_delete=models.CASCADE,
        related_name='messages',
    )
    role = models.CharField(max_length=10, choices=Role.choices)
    content = models.TextField()
    pending_action = models.JSONField(null=True, blank=True)
    action_status = models.CharField(
        max_length=10,
        choices=ActionStatus.choices,
        default=ActionStatus.NONE,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at']

    def __str__(self):
        return f'{self.get_role_display()}: {self.content[:50]}'


# -------------------------------------------------------------------
# 9. Reminder
# -------------------------------------------------------------------
class Reminder(models.Model):
    class ReminderType(models.TextChoices):
        LEAVE_TIME = 'leave_time', 'Time to Leave'
        PREP_MEAL = 'prep_meal', 'Start Meal Prep'
        GENERAL = 'general', 'General Reminder'
        PICKUP = 'pickup', 'School Pickup'
        ASSIGNMENT = 'assignment', 'Assignment Due'
        MEETING = 'meeting', 'Meeting Prep'
        EXERCISE = 'exercise', 'Exercise Time'
        CLASS = 'class', 'Class Starting'
        STUDY = 'study', 'Study Session'

    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='reminders',
    )
    linked_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    linked_block = models.ForeignKey(
        PlanBlock,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    reminder_type = models.CharField(max_length=15, choices=ReminderType.choices)
    title = models.CharField(max_length=200)
    remind_at = models.DateTimeField()
    is_sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['remind_at']

    def __str__(self):
        return f'{self.title} at {self.remind_at}'


# -------------------------------------------------------------------
# 10. FavouriteMeal
# -------------------------------------------------------------------
class FavouriteMeal(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='favourite_meals',
    )
    meal_name = models.CharField(max_length=200)
    meal_type = models.CharField(
        max_length=10,
        choices=[
            ('breakfast', 'Breakfast'),
            ('lunch', 'Lunch'),
            ('dinner', 'Dinner'),
            ('snack', 'Snack'),
        ],
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['profile', 'meal_name']
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.meal_name} ({self.meal_type})'


# -------------------------------------------------------------------
# 11. UserPantryItem
# -------------------------------------------------------------------
class UserPantryItem(models.Model):
    """Items the user always has at home — excluded from grocery lists."""
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='pantry_items',
    )
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['profile', 'name']
        ordering = ['name']

    def __str__(self):
        return self.name


# -------------------------------------------------------------------
# 12. MealSwapLog
# -------------------------------------------------------------------
class MealSwapLog(models.Model):
    """Tracks what meals were rejected and what the user chose instead."""
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='meal_swap_logs',
    )
    meal_type = models.CharField(max_length=10)  # breakfast, lunch, dinner
    rejected_meal = models.CharField(max_length=200)
    chosen_meal = models.CharField(max_length=200)
    user_request = models.CharField(
        max_length=300, blank=True,
        help_text='What the user typed for change requests, empty for swaps',
    )
    day_of_week = models.CharField(max_length=10, blank=True)  # Monday, Tuesday, etc.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.rejected_meal} → {self.chosen_meal}'


# -------------------------------------------------------------------
# 13. KidsActivityPlan
# -------------------------------------------------------------------
class KidsActivityPlan(models.Model):
    profile = models.ForeignKey(
        UserProfile,
        on_delete=models.CASCADE,
        related_name='kids_activity_plans',
    )
    week_start_date = models.DateField()
    theme = models.CharField(max_length=200)
    generated_at = models.DateTimeField(auto_now_add=True)
    raw_ai_response = models.TextField(blank=True)

    class Meta:
        unique_together = ['profile', 'week_start_date']
        ordering = ['-week_start_date']

    def __str__(self):
        return f'{self.theme} – week of {self.week_start_date}'

    def initialize_unlock(self):
        """Unlock Monday (day_of_week=0) for every child in this plan."""
        self.days.filter(day_of_week=0).update(unlocked=True)


# -------------------------------------------------------------------
# 14. KidsActivityDay
# -------------------------------------------------------------------
class KidsActivityDay(models.Model):
    plan = models.ForeignKey(
        KidsActivityPlan,
        on_delete=models.CASCADE,
        related_name='days',
    )
    child = models.ForeignKey(
        Child,
        on_delete=models.CASCADE,
        related_name='activity_days',
    )
    day_of_week = models.IntegerField(
        help_text='0=Monday, 1=Tuesday … 4=Friday',
    )
    story_title = models.CharField(max_length=300)
    story_text = models.TextField()
    story_emoji = models.CharField(max_length=10, default='📖')
    story_illustration = models.TextField(
        blank=True,
        help_text='AI-generated illustration description for the story',
    )
    worksheet_topic = models.CharField(max_length=300)
    worksheet_content = models.JSONField(
        default=dict,
        help_text='{"activities": [...]}',
    )
    coloring_description = models.TextField(blank=True)
    is_downloaded = models.BooleanField(default=False)
    is_read = models.BooleanField(default=False)
    downloaded_at = models.DateTimeField(null=True, blank=True)
    unlocked = models.BooleanField(default=False)

    class Meta:
        unique_together = ['plan', 'child', 'day_of_week']
        ordering = ['day_of_week']

    def __str__(self):
        day_names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
        day = day_names[self.day_of_week] if self.day_of_week < 5 else '?'
        return f'{self.child.name} – {day}: {self.story_title}'

    def mark_read(self):
        self.is_read = True
        self.save(update_fields=['is_read'])
        self._unlock_next()

    def mark_downloaded(self):
        self.is_downloaded = True
        self.downloaded_at = timezone.now()
        self.save(update_fields=['is_downloaded', 'downloaded_at'])
        self._unlock_next()

    def _unlock_next(self):
        """Unlock the next day for the same child in this plan."""
        next_day = self.plan.days.filter(
            child=self.child,
            day_of_week=self.day_of_week + 1,
        ).first()
        if next_day and not next_day.unlocked:
            next_day.unlocked = True
            next_day.save(update_fields=['unlocked'])


class CuisineMealSuggestions(models.Model):
    """AI-generated breakfast/lunch/dinner ideas for a cuisine, cached per
    normalized cuisine name so we hit Gemini at most once per unique cuisine."""

    cuisine = models.CharField(max_length=80, unique=True)
    display_cuisine = models.CharField(max_length=80)
    breakfast = models.JSONField(default=list)
    lunch = models.JSONField(default=list)
    dinner = models.JSONField(default=list)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.display_cuisine
