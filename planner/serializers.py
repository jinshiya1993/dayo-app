from django.contrib.auth.models import User
from rest_framework import serializers

from .models import (
    ChatConversation, ChatMessage, Child, CustomSectionList,
    CustomSectionTask, DayPlan, EssentialsCheck,
    GroceryItem, GroceryList, HouseworkList, HouseworkTask,
    HouseworkTemplate, KidsActivityDay, KidsActivityPlan,
    MealPlan, PlanBlock, Reminder, ScheduleEvent, UserProfile,
)


# -------------------------------------------------------------------
# Auth
# -------------------------------------------------------------------
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = ['username', 'email', 'password']

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()


# -------------------------------------------------------------------
# UserProfile
# -------------------------------------------------------------------
class UserProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = UserProfile
        fields = [
            'id', 'username', 'email',
            'user_type', 'display_name', 'timezone',
            'wake_time', 'sleep_time',
            'dietary_restrictions', 'cuisine_preferences', 'custom_cuisines',
            'breakfast_weight', 'breakfast_types',
            'lunch_weight', 'lunch_types',
            'dinner_weight', 'dinner_types',
            'snack_preferences',
            'planning_modules', 'module_preferences', 'custom_layout',
            'grocery_day', 'exclusions', 'home_help_type',
            'baby_name', 'baby_date_of_birth', 'is_breastfeeding',
            'had_csection', 'support_type',
            'location_city', 'notes', 'onboarding_complete',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


# -------------------------------------------------------------------
# Child
# -------------------------------------------------------------------
class ChildSerializer(serializers.ModelSerializer):
    age = serializers.IntegerField(read_only=True)

    class Meta:
        model = Child
        fields = [
            'id', 'name', 'date_of_birth', 'age',
            'interests', 'school_name', 'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'age', 'created_at', 'updated_at']


# -------------------------------------------------------------------
# ScheduleEvent
# -------------------------------------------------------------------
class ScheduleEventSerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source='child.name', read_only=True)

    class Meta:
        model = ScheduleEvent
        fields = [
            'id', 'event_type', 'title', 'description',
            'start_time', 'end_time', 'location',
            'travel_time_minutes',
            'recurrence', 'recurrence_days',
            'child', 'child_name',
            'event_date', 'is_active', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']

    def validate_child(self, value):
        if value and value.parent != self.context['request'].user.profile:
            raise serializers.ValidationError("This child does not belong to you.")
        return value


# -------------------------------------------------------------------
# PlanBlock
# -------------------------------------------------------------------
class PlanBlockSerializer(serializers.ModelSerializer):
    class Meta:
        model = PlanBlock
        fields = [
            'id', 'block_type', 'title', 'description',
            'start_time', 'end_time', 'order',
            'is_fixed', 'completed',
        ]


# -------------------------------------------------------------------
# MealPlan
# -------------------------------------------------------------------
class MealPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = MealPlan
        fields = [
            'id', 'meal_type', 'name', 'description',
            'prep_time_minutes', 'ingredients',
        ]


# -------------------------------------------------------------------
# DayPlan (with nested blocks and meals)
# -------------------------------------------------------------------
class DayPlanSerializer(serializers.ModelSerializer):
    blocks = PlanBlockSerializer(many=True, read_only=True)
    meals = MealPlanSerializer(many=True, read_only=True)

    class Meta:
        model = DayPlan
        fields = [
            'id', 'date', 'status',
            'plan_data',
            'blocks', 'meals',
            'created_at', 'updated_at',
        ]


# -------------------------------------------------------------------
# ChatMessage
# -------------------------------------------------------------------
class ChatMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ChatMessage
        fields = ['id', 'role', 'content', 'pending_action', 'action_status', 'created_at']
        read_only_fields = ['id', 'role', 'created_at']


# -------------------------------------------------------------------
# ChatConversation (with nested messages)
# -------------------------------------------------------------------
class ChatConversationSerializer(serializers.ModelSerializer):
    messages = ChatMessageSerializer(many=True, read_only=True)
    message_count = serializers.IntegerField(source='messages.count', read_only=True)

    class Meta:
        model = ChatConversation
        fields = ['id', 'title', 'is_active', 'message_count', 'messages', 'created_at', 'updated_at']
        read_only_fields = ['id', 'title', 'created_at', 'updated_at']


class ChatConversationListSerializer(serializers.ModelSerializer):
    """Lighter serializer for listing conversations (no messages)."""
    message_count = serializers.IntegerField(source='messages.count', read_only=True)

    class Meta:
        model = ChatConversation
        fields = ['id', 'title', 'is_active', 'message_count', 'created_at', 'updated_at']


# -------------------------------------------------------------------
# GroceryItem
# -------------------------------------------------------------------
class GroceryItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = GroceryItem
        fields = ['id', 'name', 'quantity', 'category', 'checked']


# -------------------------------------------------------------------
# GroceryList (with nested items)
# -------------------------------------------------------------------
class GroceryListSerializer(serializers.ModelSerializer):
    items = GroceryItemSerializer(many=True, read_only=True)
    item_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = GroceryList
        fields = ['id', 'week_start_date', 'item_count', 'items', 'completed', 'generated_at']


class GroceryListSummarySerializer(serializers.ModelSerializer):
    """Lighter serializer for listing grocery lists (no items)."""
    item_count = serializers.IntegerField(source='items.count', read_only=True)

    class Meta:
        model = GroceryList
        fields = ['id', 'week_start_date', 'item_count', 'completed', 'generated_at']


# -------------------------------------------------------------------
# HouseworkTask
# -------------------------------------------------------------------
class HouseworkTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseworkTask
        fields = ['id', 'name', 'completed', 'is_user_added']


# -------------------------------------------------------------------
# HouseworkList (with nested tasks)
# -------------------------------------------------------------------
class HouseworkListSerializer(serializers.ModelSerializer):
    tasks = HouseworkTaskSerializer(many=True, read_only=True)
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = HouseworkList
        fields = ['id', 'date', 'task_count', 'tasks', 'completed', 'generated_at']


class HouseworkListSummarySerializer(serializers.ModelSerializer):
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = HouseworkList
        fields = ['id', 'date', 'task_count', 'completed', 'generated_at']


# -------------------------------------------------------------------
# HouseworkTemplate (recurring tasks)
# -------------------------------------------------------------------
class HouseworkTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = HouseworkTemplate
        fields = ['id', 'name', 'days', 'is_active', 'created_at']


# -------------------------------------------------------------------
# CustomSectionTask / CustomSectionList
# -------------------------------------------------------------------
class CustomSectionTaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomSectionTask
        fields = ['id', 'name', 'completed', 'is_user_added']


class CustomSectionListSerializer(serializers.ModelSerializer):
    tasks = CustomSectionTaskSerializer(many=True, read_only=True)
    task_count = serializers.IntegerField(source='tasks.count', read_only=True)

    class Meta:
        model = CustomSectionList
        fields = ['id', 'section_key', 'date', 'task_count', 'tasks', 'generated_at']


# -------------------------------------------------------------------
# EssentialsCheck
# -------------------------------------------------------------------
class EssentialsCheckSerializer(serializers.ModelSerializer):
    class Meta:
        model = EssentialsCheck
        fields = ['id', 'item', 'is_checked', 'checked_at', 'added_to_grocery']


# -------------------------------------------------------------------
# Reminder
# -------------------------------------------------------------------
class ReminderSerializer(serializers.ModelSerializer):
    class Meta:
        model = Reminder
        fields = [
            'id', 'reminder_type', 'title',
            'remind_at', 'is_sent', 'created_at',
        ]


# -------------------------------------------------------------------
# KidsActivityDay
# -------------------------------------------------------------------
class KidsActivityDaySerializer(serializers.ModelSerializer):
    child_name = serializers.CharField(source='child.name', read_only=True)
    child_age = serializers.IntegerField(source='child.age', read_only=True)

    class Meta:
        model = KidsActivityDay
        fields = [
            'id', 'child', 'child_name', 'child_age',
            'day_of_week', 'story_title', 'story_text',
            'story_emoji', 'story_illustration',
            'worksheet_topic', 'worksheet_content',
            'coloring_description',
            'is_read', 'is_downloaded', 'downloaded_at', 'unlocked',
        ]
        read_only_fields = [
            'id', 'child_name', 'child_age', 'downloaded_at',
        ]


# -------------------------------------------------------------------
# KidsActivityPlan (with nested days)
# -------------------------------------------------------------------
class KidsActivityPlanSerializer(serializers.ModelSerializer):
    days = KidsActivityDaySerializer(many=True, read_only=True)
    children_progress = serializers.SerializerMethodField()

    class Meta:
        model = KidsActivityPlan
        fields = [
            'id', 'week_start_date', 'theme', 'generated_at',
            'days', 'children_progress',
        ]
        read_only_fields = ['id', 'generated_at']

    def get_children_progress(self, obj):
        """Per-child summary: completed days and next active day."""
        children = {}
        for day in obj.days.select_related('child').all():
            cid = day.child_id
            if cid not in children:
                children[cid] = {
                    'child_id': cid,
                    'child_name': day.child.name,
                    'completed_days': 0,
                    'total_days': 0,
                    'next_day_id': None,
                }
            children[cid]['total_days'] += 1
            if day.is_read or day.is_downloaded:
                children[cid]['completed_days'] += 1
            elif day.unlocked and children[cid]['next_day_id'] is None:
                children[cid]['next_day_id'] = day.id
        return list(children.values())
