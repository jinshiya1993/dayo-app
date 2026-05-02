from django.contrib import admin

from .models import (
    ChatConversation,
    ChatMessage,
    DayPlan,
    FavouriteMeal,
    HouseholdMember,
    GroceryItem,
    GroceryList,
    HouseworkList,
    HouseworkTask,
    HouseworkTemplate,
    KidsActivityDay,
    KidsActivityPlan,
    MealPlan,
    MealSwapLog,
    PlanBlock,
    Reminder,
    ScheduleEvent,
    UserPantryItem,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['display_name', 'user_type', 'timezone', 'onboarding_complete']
    list_filter = ['user_type', 'onboarding_complete']


@admin.register(HouseholdMember)
class HouseholdMemberAdmin(admin.ModelAdmin):
    list_display = ['name', 'role', 'parent', 'date_of_birth', 'age']
    list_filter = ['role', 'parent']


@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ['title', 'event_type', 'profile', 'start_time', 'recurrence', 'is_active']
    list_filter = ['event_type', 'recurrence', 'is_active']


@admin.register(DayPlan)
class DayPlanAdmin(admin.ModelAdmin):
    list_display = ['profile', 'date', 'status']
    list_filter = ['status', 'date']


@admin.register(PlanBlock)
class PlanBlockAdmin(admin.ModelAdmin):
    list_display = ['title', 'block_type', 'start_time', 'end_time', 'is_fixed', 'completed']
    list_filter = ['block_type', 'is_fixed', 'completed']


@admin.register(MealPlan)
class MealPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'meal_type', 'day_plan', 'prep_time_minutes']
    list_filter = ['meal_type']


@admin.register(GroceryList)
class GroceryListAdmin(admin.ModelAdmin):
    list_display = ['profile', 'week_start_date', 'generated_at']


@admin.register(GroceryItem)
class GroceryItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'quantity', 'category', 'checked']
    list_filter = ['category', 'checked']


@admin.register(HouseworkList)
class HouseworkListAdmin(admin.ModelAdmin):
    list_display = ['profile', 'date', 'completed', 'generated_at']
    list_filter = ['completed', 'date']


@admin.register(HouseworkTask)
class HouseworkTaskAdmin(admin.ModelAdmin):
    list_display = ['name', 'housework_list', 'completed', 'is_user_added']
    list_filter = ['completed', 'is_user_added']


@admin.register(HouseworkTemplate)
class HouseworkTemplateAdmin(admin.ModelAdmin):
    list_display = ['name', 'profile', 'days', 'is_active']
    list_filter = ['is_active']


@admin.register(ChatConversation)
class ChatConversationAdmin(admin.ModelAdmin):
    list_display = ['title', 'profile', 'is_active', 'updated_at']
    list_filter = ['is_active']


@admin.register(ChatMessage)
class ChatMessageAdmin(admin.ModelAdmin):
    list_display = ['conversation', 'role', 'content_preview', 'created_at']
    list_filter = ['role']

    def content_preview(self, obj):
        return obj.content[:80]


@admin.register(MealSwapLog)
class MealSwapLogAdmin(admin.ModelAdmin):
    list_display = ['profile', 'meal_type', 'rejected_meal', 'chosen_meal', 'user_request', 'day_of_week', 'created_at']
    list_filter = ['meal_type', 'day_of_week']


@admin.register(UserPantryItem)
class UserPantryItemAdmin(admin.ModelAdmin):
    list_display = ['name', 'profile', 'created_at']


@admin.register(FavouriteMeal)
class FavouriteMealAdmin(admin.ModelAdmin):
    list_display = ['meal_name', 'meal_type', 'profile', 'created_at']
    list_filter = ['meal_type']


@admin.register(Reminder)
class ReminderAdmin(admin.ModelAdmin):
    list_display = ['title', 'reminder_type', 'profile', 'remind_at', 'is_sent']
    list_filter = ['reminder_type', 'is_sent']


@admin.register(KidsActivityPlan)
class KidsActivityPlanAdmin(admin.ModelAdmin):
    list_display = ['profile', 'week_start_date', 'theme', 'generated_at']
    list_filter = ['week_start_date']


@admin.register(KidsActivityDay)
class KidsActivityDayAdmin(admin.ModelAdmin):
    list_display = ['child', 'day_of_week', 'story_title', 'unlocked', 'is_read', 'is_downloaded']
    list_filter = ['unlocked', 'is_read', 'is_downloaded', 'day_of_week']
