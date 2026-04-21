import logging
from datetime import date, timedelta

from django.contrib.auth import authenticate, login, logout

logger = logging.getLogger(__name__)
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils import timezone
from rest_framework import generics, status, viewsets
from rest_framework.decorators import api_view, permission_classes as perm_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView


@api_view(['GET'])
@perm_classes([AllowAny])
def get_csrf_token(request):
    """Sets the CSRF cookie and returns the token."""
    token = get_token(request)
    return Response({'csrfToken': token})

from .models import (
    ChatConversation, ChatMessage, Child, CustomSectionDeletionLog,
    CustomSectionList, CustomSectionTask, DayPlan, EssentialsCheck,
    FavouriteMeal, GroceryItem,
    GroceryList, HouseworkList, HouseworkTask, HouseworkTaskDeletionLog, HouseworkTemplate,
    KidsActivityDay, KidsActivityPlan, MealSwapLog,
    Reminder, ScheduleEvent, UserPantryItem, UserProfile,
)
from .serializers import (
    ChatConversationListSerializer,
    ChatConversationSerializer,
    ChatMessageSerializer,
    ChildSerializer,
    CustomSectionListSerializer,
    CustomSectionTaskSerializer,
    DayPlanSerializer,
    EssentialsCheckSerializer,
    GroceryItemSerializer,
    GroceryListSerializer,
    GroceryListSummarySerializer,
    HouseworkListSerializer,
    HouseworkTaskSerializer,
    HouseworkTemplateSerializer,
    KidsActivityPlanSerializer,
    LoginSerializer,
    RegisterSerializer,
    ReminderSerializer,
    ScheduleEventSerializer,
    UserProfileSerializer,
)
from .services.chat_service import ChatService
from .services.grocery_generator import GroceryGenerator
from .services.kids_activity_generator import KidsActivityGenerator
from .services.kids_activity_pdf import KidsActivityPDFGenerator
from .services.plan_generator import PlanGenerator
from .services.profile_builder import ProfileBuilderAgent
from .section_registry import SECTION_REGISTRY, build_initial_layout


# -------------------------------------------------------------------
# Auth
# -------------------------------------------------------------------
class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]
    authentication_classes = []  # Skip SessionAuth CSRF check for register

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Auto-create a profile for the new user
        UserProfile.objects.create(
            user=user,
            display_name=user.username,
        )

        login(request, user)
        return Response(
            {'message': 'Account created', 'username': user.username},
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []  # Skip SessionAuth CSRF check for login

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = authenticate(
            request,
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password'],
        )
        if user is None:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        login(request, user)
        return Response({'message': 'Logged in', 'username': user.username})


class LogoutView(APIView):
    def post(self, request):
        logout(request)
        return Response({'message': 'Logged out'})


# -------------------------------------------------------------------
# UserProfile — single object for the logged-in user
# -------------------------------------------------------------------
class ProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = UserProfile.objects.get_or_create(
            user=self.request.user,
            defaults={'display_name': self.request.user.username},
        )
        return profile


class SectionsView(APIView):
    """Returns all available dashboard sections with metadata."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(SECTION_REGISTRY)


class LayoutView(APIView):
    """Save the user's custom dashboard layout."""
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        profile = request.user.profile
        layout = request.data.get('custom_layout')
        if layout is None:
            return Response({'error': 'custom_layout is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Cap: max 3 custom sections
        custom_count = sum(
            1 for item in layout
            if item.get('custom_label') or item.get('added_by_user')
        )
        if custom_count > 3:
            return Response(
                {'error': 'You can add up to 3 custom sections.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.custom_layout = layout
        profile.save()
        return Response({'custom_layout': profile.custom_layout})


# -------------------------------------------------------------------
# Children — scoped to the logged-in user's profile
# -------------------------------------------------------------------
class ChildViewSet(viewsets.ModelViewSet):
    serializer_class = ChildSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Child.objects.filter(parent=self.request.user.profile)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        serializer.save(parent=profile)

        # Make sure the kids_activities section is visible on the dashboard.
        # Users on non-parent user types (homemaker, new_mom, professional) don't
        # get it by default, so adding a child also adds the section.
        layout = list(profile.custom_layout or [])
        if not any(item.get('key') == 'kids_activities' for item in layout):
            layout.append({
                'key': 'kids_activities',
                'visible': True,
                'locked': False,
                'added_by_ai': False,
            })
            profile.custom_layout = layout
            profile.save(update_fields=['custom_layout'])


# -------------------------------------------------------------------
# Schedule Events — scoped to the logged-in user's profile
# -------------------------------------------------------------------
class ScheduleEventViewSet(viewsets.ModelViewSet):
    serializer_class = ScheduleEventSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        queryset = ScheduleEvent.objects.filter(profile=self.request.user.profile)

        # Optional filters
        event_type = self.request.query_params.get('event_type')
        if event_type:
            queryset = queryset.filter(event_type=event_type)

        child_id = self.request.query_params.get('child')
        if child_id:
            queryset = queryset.filter(child_id=child_id)

        active_only = self.request.query_params.get('active')
        if active_only == 'true':
            queryset = queryset.filter(is_active=True)

        return queryset

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


# -------------------------------------------------------------------
# Day Plans
# -------------------------------------------------------------------
class GeneratePlanView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        date_str = request.data.get('date')

        if date_str:
            from datetime import datetime
            try:
                target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                return Response(
                    {'error': 'Invalid date format. Use YYYY-MM-DD.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            from datetime import date
            target_date = date.today()

        generator = PlanGenerator()

        # First generate weekly meals (if not already planned)
        generator.ensure_meals_ahead(profile)

        # Then generate the full day plan (non-meal sections)
        # This preserves weekly meals if they exist
        day_plan = generator.generate_day_plan(profile, target_date)

        if day_plan.status == 'failed':
            return Response(
                {'error': 'Plan generation failed. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Kids activities and grocery are generated by separate follow-up
        # requests from the client. Chaining them here was OOM-killing the
        # worker on small plans (4 AI calls in one request).

        serializer = DayPlanSerializer(day_plan)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class DayPlanDetailView(generics.RetrieveAPIView):
    serializer_class = DayPlanSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'date'

    def get_queryset(self):
        return DayPlan.objects.filter(profile=self.request.user.profile)

    def retrieve(self, request, *args, **kwargs):
        # Auto-fill meals if running low (< 3 days planned)
        try:
            generator = PlanGenerator()
            generator.ensure_meals_ahead(request.user.profile)
        except Exception:
            pass  # Don't block the response if auto-fill fails
        return super().retrieve(request, *args, **kwargs)


# -------------------------------------------------------------------
# Meal Actions — swap, substitute, favourite
# -------------------------------------------------------------------
class SwapMealView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, date):
        """Regenerate a single meal using AI, keeping macros balanced."""
        import json
        import logging
        from datetime import datetime as dt
        from django.conf import settings as django_settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from .services.ai_context import AIContextAssembler

        logger = logging.getLogger(__name__)

        try:
            profile = request.user.profile
            meal_type = request.data.get('meal_type')
            date_str = date

            if meal_type not in ('breakfast', 'lunch', 'dinner'):
                return Response({'error': 'meal_type must be breakfast, lunch, or dinner'}, status=status.HTTP_400_BAD_REQUEST)

            day_plan = DayPlan.objects.get(profile=profile, date=date_str)

            plan_data = day_plan.plan_data or {}
            meals = plan_data.get('meals') or plan_data.get('mom_meals') or {}
            current_meal = meals.get(meal_type, {})
            current_name = current_meal.get('name', '')

            favourites = list(profile.favourite_meals.values_list('meal_name', flat=True)[:10])

            target_date = dt.strptime(date_str, '%Y-%m-%d').date()
            assembler = AIContextAssembler(profile)
            context = assembler.build_plan_generation_context(target_date)

            llm = ChatGoogleGenerativeAI(
                model='gemini-2.5-flash',
                google_api_key=django_settings.GEMINI_API_KEY,
                temperature=0.8,
                max_output_tokens=2048,
                transport='rest',
            )

            fav_text = f"\nThe user's favourite meals (try to vary from these but use similar style): {', '.join(favourites)}" if favourites else ""

            messages = [
                SystemMessage(content=context['system_prompt']),
                HumanMessage(content=(
                    f"The user wants to SWAP their {meal_type}. The current {meal_type} is '{current_name}' — suggest something DIFFERENT.\n"
                    f"Must be balanced: protein + carbs + healthy fats + fiber.\n"
                    f"Must respect the user's cuisine preferences and health conditions.\n"
                    f"Must work for {profile.family_size} people.{fav_text}\n\n"
                    f"Return ONLY a JSON object:\n"
                    f'{{"name": "Meal name", "prep_mins": 20, "description": "Brief recipe"}}\n'
                )),
            ]

            response = llm.invoke(messages)
            content = response.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            new_meal = json.loads(content)

            meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
            plan_data[meals_key][meal_type] = new_meal
            day_plan.plan_data = plan_data
            day_plan.save()

            # Log the swap for AI learning
            MealSwapLog.objects.create(
                profile=profile,
                meal_type=meal_type,
                rejected_meal=current_name,
                chosen_meal=new_meal.get('name', ''),
                day_of_week=target_date.strftime('%A'),
            )

            return Response({'meal_type': meal_type, 'meal': new_meal, 'plan_data': plan_data})

        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan found for this date'}, status=status.HTTP_404_NOT_FOUND)
        except Exception as e:
            logger.error(f'SwapMeal error: {e}', exc_info=True)
            return Response({'error': str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class SubstituteMealView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, date):
        """Substitute an ingredient in a meal with an alternative."""
        import json
        from datetime import datetime as dt
        from django.conf import settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from .services.ai_context import AIContextAssembler

        profile = request.user.profile
        meal_type = request.data.get('meal_type')
        missing_ingredient = request.data.get('ingredient', '').strip()
        date_str = date

        if meal_type not in ('breakfast', 'lunch', 'dinner'):
            return Response({'error': 'meal_type must be breakfast, lunch, or dinner'}, status=status.HTTP_400_BAD_REQUEST)
        if not missing_ingredient:
            return Response({'error': 'ingredient is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            day_plan = DayPlan.objects.get(profile=profile, date=date_str)
        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan found for this date'}, status=status.HTTP_404_NOT_FOUND)

        plan_data = day_plan.plan_data or {}
        meals = plan_data.get('meals') or plan_data.get('mom_meals') or {}
        current_meal = meals.get(meal_type, {})

        target_date = dt.strptime(date_str, '%Y-%m-%d').date()
        assembler = AIContextAssembler(profile)
        context = assembler.build_plan_generation_context(target_date
        )

        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=2048,
            transport='rest',
        )

        messages = [
            SystemMessage(content=context['system_prompt']),
            HumanMessage(content=(
                f"The user's {meal_type} is '{current_meal.get('name', '')}' — {current_meal.get('description', '')}.\n"
                f"They DON'T HAVE: {missing_ingredient}.\n"
                f"Modify the meal to substitute '{missing_ingredient}' with something else that's commonly available.\n"
                f"Keep the meal balanced (protein + carbs + healthy fats + fiber) and respect health conditions.\n\n"
                f"Return ONLY a JSON object:\n"
                f'{{"name": "Updated meal name", "prep_mins": 20, "description": "Brief recipe with substitution"}}\n'
            )),
        ]

        try:
            response = llm.invoke(messages)
            content = response.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            new_meal = json.loads(content)
        except Exception:
            return Response({'error': 'Failed to substitute ingredient'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        # Update plan_data
        meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
        plan_data[meals_key][meal_type] = new_meal
        day_plan.plan_data = plan_data
        day_plan.save()

        return Response({'meal_type': meal_type, 'meal': new_meal, 'plan_data': plan_data})


class FavouriteMealToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Toggle a meal as favourite — add if not exists, remove if exists."""
        profile = request.user.profile
        meal_name = request.data.get('meal_name', '').strip()
        meal_type = request.data.get('meal_type', '').strip()
        description = request.data.get('description', '').strip()

        if not meal_name:
            return Response({'error': 'meal_name is required'}, status=status.HTTP_400_BAD_REQUEST)

        existing = FavouriteMeal.objects.filter(profile=profile, meal_name=meal_name).first()
        if existing:
            existing.delete()
            return Response({'favourited': False, 'meal_name': meal_name})

        FavouriteMeal.objects.create(
            profile=profile,
            meal_name=meal_name,
            meal_type=meal_type or 'lunch',
            description=description,
        )
        return Response({'favourited': True, 'meal_name': meal_name})


class FavouriteMealListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List user's favourite meals."""
        profile = request.user.profile
        favourites = FavouriteMeal.objects.filter(profile=profile).values(
            'id', 'meal_name', 'meal_type', 'description', 'created_at'
        )
        return Response(list(favourites))


class WeeklyMealsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get meals for the next 7 days from existing day plans."""
        from datetime import date, timedelta
        profile = request.user.profile
        today = date.today()
        days = []

        for i in range(7):
            d = today + timedelta(days=i)
            plan = DayPlan.objects.filter(profile=profile, date=d, status='ready').first()
            meals = {}
            if plan and plan.plan_data:
                meals = plan.plan_data.get('meals') or plan.plan_data.get('mom_meals') or {}
            days.append({
                'date': str(d),
                'day_name': d.strftime('%A'),
                'is_today': i == 0,
                'has_plan': plan is not None,
                'meals': {
                    'breakfast': meals.get('breakfast', {}).get('name', '') if isinstance(meals.get('breakfast'), dict) else '',
                    'lunch': meals.get('lunch', {}).get('name', '') if isinstance(meals.get('lunch'), dict) else '',
                    'dinner': meals.get('dinner', {}).get('name', '') if isinstance(meals.get('dinner'), dict) else '',
                },
            })
        return Response(days)

    def post(self, request):
        """Generate meals for the week using the weekly meal generator."""
        from datetime import date
        profile = request.user.profile

        generator = PlanGenerator()
        plans = generator.generate_weekly_meals(profile, date.today(), 7)

        return Response({'generated_count': len(plans)})


class ChangeMealView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, date):
        """Change a meal based on user's specification — uses same AI agent with full health/family context."""
        import json
        from datetime import datetime as dt
        from django.conf import settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage
        from .services.ai_context import AIContextAssembler

        profile = request.user.profile
        meal_type = request.data.get('meal_type')
        user_request = request.data.get('request', '').strip()
        date_str = date  # URL parameter

        if meal_type not in ('breakfast', 'lunch', 'dinner'):
            return Response({'error': 'meal_type must be breakfast, lunch, or dinner'}, status=status.HTTP_400_BAD_REQUEST)
        if not user_request:
            return Response({'error': 'request is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            day_plan = DayPlan.objects.get(profile=profile, date=date_str)
        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan found for this date'}, status=status.HTTP_404_NOT_FOUND)

        # Get current meal name before changing
        current_plan_data = day_plan.plan_data or {}
        current_meals = current_plan_data.get('meals') or current_plan_data.get('mom_meals') or {}
        current_meal_name = current_meals.get(meal_type, {}).get('name', '') if isinstance(current_meals.get(meal_type), dict) else ''

        target_date = dt.strptime(date_str, '%Y-%m-%d').date()
        assembler = AIContextAssembler(profile)
        context = assembler.build_plan_generation_context(target_date)

        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=2048,
            transport='rest',
        )

        messages = [
            SystemMessage(content=context['system_prompt']),
            HumanMessage(content=(
                f"The user wants this for {meal_type}: \"{user_request}\"\n"
                f"Generate a {meal_type} based on their request.\n"
                f"IMPORTANT: Even though the user requested a specific style, the meal MUST still be:\n"
                f"- Balanced: protein + carbs + healthy fats + fiber\n"
                f"- Compatible with their health conditions\n"
                f"- Suitable for {profile.family_size} people\n"
                f"- Use their preferred cuisine style where possible, adapted to the request\n\n"
                f"Return ONLY a compact JSON object, keep description under 10 words:\n"
                f'{{"name": "Meal name", "prep_mins": 20, "description": "Under 10 words"}}\n'
            )),
        ]

        try:
            response = llm.invoke(messages)
            content = response.content.strip()
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0].strip()
            elif '```' in content:
                content = content.split('```')[1].split('```')[0].strip()
            new_meal = json.loads(content)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'ChangeMeal AI error: {e}')
            return Response({'error': f'Failed to generate meal: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        try:
            plan_data = day_plan.plan_data or {}
            meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
            if meals_key not in plan_data:
                plan_data[meals_key] = {}
            plan_data[meals_key][meal_type] = new_meal
            day_plan.plan_data = plan_data
            day_plan.save()

            # Log the change for AI learning
            MealSwapLog.objects.create(
                profile=profile,
                meal_type=meal_type,
                rejected_meal=current_meal_name,
                chosen_meal=new_meal.get('name', ''),
                user_request=user_request,
                day_of_week=target_date.strftime('%A'),
            )
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f'ChangeMeal save error: {e}')
            return Response({'error': f'Failed to save meal: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response({'meal_type': meal_type, 'meal': new_meal, 'plan_data': plan_data})


# -------------------------------------------------------------------
# Chat
# -------------------------------------------------------------------
class ChatConversationListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == 'GET':
            return ChatConversationListSerializer
        return ChatConversationSerializer

    def get_queryset(self):
        return ChatConversation.objects.filter(profile=self.request.user.profile)

    def perform_create(self, serializer):
        serializer.save(profile=self.request.user.profile)


class ChatConversationDetailView(generics.RetrieveDestroyAPIView):
    serializer_class = ChatConversationSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return ChatConversation.objects.filter(profile=self.request.user.profile)


class ChatSendMessageView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            conversation = ChatConversation.objects.get(
                pk=pk, profile=request.user.profile,
            )
        except ChatConversation.DoesNotExist:
            return Response(
                {'error': 'Conversation not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        message_text = request.data.get('message', '').strip()
        if not message_text:
            return Response(
                {'error': 'Message cannot be empty.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        service = ChatService()
        assistant_msg = service.send_message(conversation, message_text)

        serializer = ChatMessageSerializer(assistant_msg)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ChatMessageConfirmView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        """Execute a pending chat action, then auto-continue if more actions are needed."""
        from .services.chat_tools import execute_tool
        from .services.chat_service import ChatService

        try:
            msg = ChatMessage.objects.get(
                pk=message_id,
                conversation__profile=request.user.profile,
                action_status=ChatMessage.ActionStatus.PENDING,
            )
        except ChatMessage.DoesNotExist:
            return Response({'error': 'No pending action found.'}, status=status.HTTP_404_NOT_FOUND)

        result = execute_tool(
            tool_name=msg.pending_action['tool_name'],
            args=msg.pending_action['tool_args'],
            profile=request.user.profile,
        )

        msg.action_status = ChatMessage.ActionStatus.CONFIRMED
        msg.save(update_fields=['action_status'])

        result_msg = ChatMessage.objects.create(
            conversation=msg.conversation,
            role=ChatMessage.Role.ASSISTANT,
            content=result['message'],
        )

        # Auto-continue: send a follow-up so the LLM picks up remaining actions
        response_data = {
            'status': 'confirmed',
            'result': result,
            'message': ChatMessageSerializer(result_msg).data,
        }

        if result.get('success'):
            try:
                service = ChatService()
                follow_up = service.send_message(
                    msg.conversation,
                    'Done. Continue with the next action if there are any remaining.',
                )
                response_data['follow_up'] = ChatMessageSerializer(follow_up).data
            except Exception:
                pass  # If follow-up fails, the confirmed action still succeeded

        return Response(response_data)


class ChatMessageCancelView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, message_id):
        """Cancel a pending chat action."""
        try:
            msg = ChatMessage.objects.get(
                pk=message_id,
                conversation__profile=request.user.profile,
                action_status=ChatMessage.ActionStatus.PENDING,
            )
        except ChatMessage.DoesNotExist:
            return Response({'error': 'No pending action found.'}, status=status.HTTP_404_NOT_FOUND)

        msg.action_status = ChatMessage.ActionStatus.CANCELLED
        msg.save(update_fields=['action_status'])

        cancel_msg = ChatMessage.objects.create(
            conversation=msg.conversation,
            role=ChatMessage.Role.ASSISTANT,
            content="No problem, I've cancelled that.",
        )

        return Response({
            'status': 'cancelled',
            'message': ChatMessageSerializer(cancel_msg).data,
        })


# -------------------------------------------------------------------
# Grocery Lists
# -------------------------------------------------------------------
class GroceryListView(generics.ListAPIView):
    serializer_class = GroceryListSummarySerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return GroceryList.objects.filter(profile=self.request.user.profile)


class GroceryCurrentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        grocery_list = GroceryList.objects.filter(
            profile=profile, completed=False,
        ).first()

        # Self-heal: if there's no active list, no completed list this week, and
        # meals are planned for the week, auto-generate. This covers silent
        # failures of the auto-gen during plans.generate() and week rollovers
        # where the previous week's list was abandoned.
        if not grocery_list:
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            end_of_week = week_start + timedelta(days=6)
            has_completed_this_week = GroceryList.objects.filter(
                profile=profile, completed=True,
                week_start_date__gte=week_start,
            ).exists()
            has_meals_planned = DayPlan.objects.filter(
                profile=profile,
                date__gte=today,
                date__lte=end_of_week,
                status='ready',
            ).exists()
            if not has_completed_this_week and has_meals_planned:
                try:
                    grocery_list = GroceryGenerator().generate_grocery_list(profile)
                except Exception as e:
                    logger.error(f'On-demand grocery generation failed: {e}')

        if not grocery_list:
            return Response(
                {'error': 'No active grocery list.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = GroceryListSerializer(grocery_list)
        return Response(serializer.data)


class GroceryGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        generator = GroceryGenerator()
        grocery_list = generator.generate_grocery_list(profile)

        if not grocery_list:
            return Response(
                {'error': 'Could not generate grocery list right now. Please try again in a moment.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = GroceryListSerializer(grocery_list)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroceryItemToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, list_id, item_id):
        try:
            item = GroceryItem.objects.get(
                pk=item_id,
                grocery_list_id=list_id,
                grocery_list__profile=request.user.profile,
            )
        except GroceryItem.DoesNotExist:
            return Response(
                {'error': 'Item not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Update quantity if provided, otherwise toggle checked
        if 'quantity' in request.data:
            item.quantity = request.data['quantity']
            item.save()
        else:
            item.checked = not item.checked
            item.save()

        serializer = GroceryItemSerializer(item)
        return Response(serializer.data)


class GroceryDoneView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Mark the current grocery list as completed."""
        grocery_list = GroceryList.objects.filter(
            profile=request.user.profile,
            completed=False,
        ).first()

        if not grocery_list:
            return Response({'error': 'No active grocery list'}, status=status.HTTP_404_NOT_FOUND)

        unchecked = grocery_list.items.filter(checked=False).count()
        grocery_list.completed = True
        grocery_list.save()

        return Response({'completed': True, 'unchecked_remaining': unchecked})


class GroceryItemAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, list_id):
        """Manually add an item to a grocery list."""
        profile = request.user.profile
        name = request.data.get('name', '').strip()
        quantity = request.data.get('quantity', '').strip()
        category = request.data.get('category', 'other').strip()

        if not name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            grocery_list = GroceryList.objects.get(pk=list_id, profile=profile, completed=False)
        except GroceryList.DoesNotExist:
            return Response({'error': 'List not found'}, status=status.HTTP_404_NOT_FOUND)

        # Check if item already exists in this list
        existing = GroceryItem.objects.filter(
            grocery_list=grocery_list,
            name__iexact=name,
        ).first()
        if existing:
            return Response({'error': 'already_exists', 'message': f'{name} is already in your list'}, status=status.HTTP_409_CONFLICT)

        valid_categories = [c[0] for c in GroceryItem.Category.choices]
        if category not in valid_categories:
            category = 'other'

        item = GroceryItem.objects.create(
            grocery_list=grocery_list,
            name=name,
            quantity=quantity,
            category=category,
            is_user_added=True,
        )
        serializer = GroceryItemSerializer(item)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroceryQuickAddView(APIView):
    """Add an item mid-week. Creates a lightweight list if none is active."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        # Get or create active list
        grocery_list = GroceryList.objects.filter(profile=profile, completed=False).first()
        if not grocery_list:
            today = date.today()
            grocery_list = GroceryList.objects.create(
                profile=profile,
                week_start_date=today - timedelta(days=today.weekday()),
            )

        # Check duplicate
        if GroceryItem.objects.filter(grocery_list=grocery_list, name__iexact=name).exists():
            return Response(
                {'error': 'already_exists', 'message': f'{name} is already in your list'},
                status=status.HTTP_409_CONFLICT,
            )

        item = GroceryItem.objects.create(
            grocery_list=grocery_list,
            name=name,
            quantity=request.data.get('quantity', '').strip(),
            category='other',
            is_user_added=True,
        )

        serializer = GroceryListSerializer(grocery_list)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class GroceryItemDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, list_id, item_id):
        """Delete an item from a grocery list."""
        try:
            item = GroceryItem.objects.get(
                pk=item_id,
                grocery_list_id=list_id,
                grocery_list__profile=request.user.profile,
            )
        except GroceryItem.DoesNotExist:
            return Response({'error': 'Item not found'}, status=status.HTTP_404_NOT_FOUND)

        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# Housework
# ===================================================================

class HouseworkCurrentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = date.today()
        hw_list = HouseworkList.objects.filter(
            profile=request.user.profile,
            date=today,
        ).first()
        if not hw_list:
            return Response({'error': 'No housework list for today'}, status=status.HTTP_404_NOT_FOUND)
        serializer = HouseworkListSerializer(hw_list)
        return Response(serializer.data)


class HouseworkGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        today = date.today()

        # Already exists? Return it.
        existing = HouseworkList.objects.filter(profile=profile, date=today).first()
        if existing:
            serializer = HouseworkListSerializer(existing)
            return Response(serializer.data)

        # Try extracting from today's day plan (created by plan generator)
        day_plan = DayPlan.objects.filter(profile=profile, date=today, status='ready').first()
        if day_plan and day_plan.plan_data and day_plan.plan_data.get('housework'):
            from .services.plan_generator import PlanGenerator
            gen = PlanGenerator()
            gen._save_housework_from_plan_data(profile, today, day_plan.plan_data)
            hw_list = HouseworkList.objects.filter(profile=profile, date=today).first()
            if hw_list:
                serializer = HouseworkListSerializer(hw_list)
                return Response(serializer.data, status=status.HTTP_201_CREATED)

        # Fallback: standalone generator (rare — covers race conditions)
        from .services.housework_generator import HouseworkGenerator
        generator = HouseworkGenerator()
        hw_list = generator.generate_housework_list(profile)
        serializer = HouseworkListSerializer(hw_list)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HouseworkTaskToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, list_id, task_id):
        try:
            task = HouseworkTask.objects.get(
                pk=task_id,
                housework_list_id=list_id,
                housework_list__profile=request.user.profile,
            )
        except HouseworkTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        task.completed = not task.completed
        task.save()
        serializer = HouseworkTaskSerializer(task)
        return Response(serializer.data)


class HouseworkTaskAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, list_id):
        try:
            hw_list = HouseworkList.objects.get(
                pk=list_id,
                profile=request.user.profile,
            )
        except HouseworkList.DoesNotExist:
            return Response({'error': 'List not found'}, status=status.HTTP_404_NOT_FOUND)

        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

        existing = HouseworkTask.objects.filter(
            housework_list=hw_list,
            name__iexact=name,
        ).first()
        if existing:
            return Response(
                {'error': 'already_exists', 'message': f'{name} is already in your list'},
                status=status.HTTP_409_CONFLICT,
            )

        task = HouseworkTask.objects.create(
            housework_list=hw_list,
            name=name,
            is_user_added=True,
        )
        serializer = HouseworkTaskSerializer(task)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HouseworkTaskDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, list_id, task_id):
        try:
            task = HouseworkTask.objects.get(
                pk=task_id,
                housework_list_id=list_id,
                housework_list__profile=request.user.profile,
            )
        except HouseworkTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        # Log deletion for AI learning
        HouseworkTaskDeletionLog.objects.create(
            profile=request.user.profile,
            task_name=task.name,
            was_ai_generated=not task.is_user_added,
        )

        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# Housework Templates (recurring tasks)
# ===================================================================

class HouseworkTemplateListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        templates = HouseworkTemplate.objects.filter(
            profile=request.user.profile,
            is_active=True,
        )
        serializer = HouseworkTemplateSerializer(templates, many=True)
        return Response(serializer.data)

    def post(self, request):
        name = request.data.get('name', '').strip()
        days = request.data.get('days', [])
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

        template = HouseworkTemplate.objects.create(
            profile=request.user.profile,
            name=name,
            days=days,
        )
        serializer = HouseworkTemplateSerializer(template)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class HouseworkTemplateUpdateDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, template_id):
        try:
            template = HouseworkTemplate.objects.get(
                pk=template_id,
                profile=request.user.profile,
            )
        except HouseworkTemplate.DoesNotExist:
            return Response({'error': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)

        if 'name' in request.data:
            template.name = request.data['name'].strip()
        if 'days' in request.data:
            template.days = request.data['days']
        if 'is_active' in request.data:
            template.is_active = request.data['is_active']
        template.save()
        serializer = HouseworkTemplateSerializer(template)
        return Response(serializer.data)

    def delete(self, request, template_id):
        try:
            template = HouseworkTemplate.objects.get(
                pk=template_id,
                profile=request.user.profile,
            )
        except HouseworkTemplate.DoesNotExist:
            return Response({'error': 'Template not found'}, status=status.HTTP_404_NOT_FOUND)

        template.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# Custom Sections (parameterized by section_key)
# ===================================================================

def _get_valid_custom_keys(profile):
    """Return set of custom section keys from the user's layout."""
    from .section_registry import SECTION_REGISTRY
    known = set(SECTION_REGISTRY.keys())
    keys = set()
    for item in (profile.custom_layout or []):
        key = item.get('key', '')
        if key and key not in known and (item.get('custom_label') or item.get('added_by_user')):
            keys.add(key)
    return keys


class CustomSectionCurrentView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, section_key):
        profile = request.user.profile
        if section_key not in _get_valid_custom_keys(profile):
            return Response({'error': 'Invalid section'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        cs_list = CustomSectionList.objects.filter(
            profile=profile, section_key=section_key, date=today,
        ).first()
        if not cs_list:
            return Response({'error': 'No list for today'}, status=status.HTTP_404_NOT_FOUND)
        return Response(CustomSectionListSerializer(cs_list).data)


class CustomSectionGenerateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, section_key):
        profile = request.user.profile
        if section_key not in _get_valid_custom_keys(profile):
            return Response({'error': 'Invalid section'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()

        # Return existing if already generated
        existing = CustomSectionList.objects.filter(
            profile=profile, section_key=section_key, date=today,
        ).first()
        if existing:
            return Response(CustomSectionListSerializer(existing).data)

        # Try to extract from today's plan data
        cs_list = CustomSectionList.objects.create(
            profile=profile, section_key=section_key, date=today,
        )

        day_plan = DayPlan.objects.filter(profile=profile, date=today, status='ready').first()
        if day_plan and day_plan.plan_data:
            section_data = day_plan.plan_data.get(section_key)
            if isinstance(section_data, dict):
                for item in section_data.get('items', []):
                    if isinstance(item, str) and item.strip():
                        CustomSectionTask.objects.create(
                            section_list=cs_list, name=item.strip(),
                        )

        return Response(
            CustomSectionListSerializer(cs_list).data,
            status=status.HTTP_201_CREATED,
        )


class CustomSectionTaskToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, section_key, list_id, task_id):
        try:
            task = CustomSectionTask.objects.get(
                pk=task_id,
                section_list_id=list_id,
                section_list__profile=request.user.profile,
                section_list__section_key=section_key,
            )
        except CustomSectionTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        task.completed = not task.completed
        task.save()
        return Response(CustomSectionTaskSerializer(task).data)


class CustomSectionTaskAddView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, section_key, list_id):
        try:
            cs_list = CustomSectionList.objects.get(
                pk=list_id,
                profile=request.user.profile,
                section_key=section_key,
            )
        except CustomSectionList.DoesNotExist:
            return Response({'error': 'List not found'}, status=status.HTTP_404_NOT_FOUND)

        name = request.data.get('name', '').strip()
        if not name:
            return Response({'error': 'Name is required'}, status=status.HTTP_400_BAD_REQUEST)

        if CustomSectionTask.objects.filter(section_list=cs_list, name__iexact=name).exists():
            return Response(
                {'error': 'already_exists', 'message': f'{name} is already in your list'},
                status=status.HTTP_409_CONFLICT,
            )

        task = CustomSectionTask.objects.create(
            section_list=cs_list, name=name, is_user_added=True,
        )
        return Response(CustomSectionTaskSerializer(task).data, status=status.HTTP_201_CREATED)


class CustomSectionTaskDeleteView(APIView):
    permission_classes = [IsAuthenticated]

    def delete(self, request, section_key, list_id, task_id):
        try:
            task = CustomSectionTask.objects.get(
                pk=task_id,
                section_list_id=list_id,
                section_list__profile=request.user.profile,
                section_list__section_key=section_key,
            )
        except CustomSectionTask.DoesNotExist:
            return Response({'error': 'Task not found'}, status=status.HTTP_404_NOT_FOUND)

        CustomSectionDeletionLog.objects.create(
            profile=request.user.profile,
            section_key=section_key,
            task_name=task.name,
            was_ai_generated=not task.is_user_added,
        )

        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ===================================================================
# Essentials Check (new mom)
# ===================================================================

def _get_default_essentials(profile):
    """Personalized essential items based on profile."""
    if profile.is_breastfeeding:
        return ['Breast pads', 'Nipple cream', 'Water bottle', 'Nappies', 'Wipes', 'Burp cloths']
    else:
        return ['Formula', 'Clean bottles', 'Steriliser', 'Nappies', 'Wipes', 'Burp cloths']


def _get_low_stock_items(profile, today):
    """Items unchecked for 2+ consecutive days."""
    yesterday = today - timedelta(days=1)
    day_before = today - timedelta(days=2)
    unchecked_y = set(
        EssentialsCheck.objects.filter(
            profile=profile, date=yesterday, is_checked=False,
        ).values_list('item', flat=True)
    )
    unchecked_db = set(
        EssentialsCheck.objects.filter(
            profile=profile, date=day_before, is_checked=False,
        ).values_list('item', flat=True)
    )
    return unchecked_y & unchecked_db


class EssentialsCurrentView(APIView):
    """GET today's essentials. Creates records from plan_data if they don't exist yet."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        today = date.today()

        checks = EssentialsCheck.objects.filter(profile=profile, date=today)
        if not checks.exists():
            # Bootstrap from today's plan data or personalized defaults
            day_plan = DayPlan.objects.filter(profile=profile, date=today, status='ready').first()
            items = []
            if day_plan and day_plan.plan_data:
                essentials = day_plan.plan_data.get('essentials_check', [])
                if isinstance(essentials, list):
                    items = [str(i).strip() for i in essentials if str(i).strip()]

            if not items:
                items = _get_default_essentials(profile)

            for item in items:
                EssentialsCheck.objects.get_or_create(
                    profile=profile, date=today, item=item,
                )
            checks = EssentialsCheck.objects.filter(profile=profile, date=today)

        # Get low stock items
        low_items = _get_low_stock_items(profile, today)

        # Serialize with low_stock flag
        data = EssentialsCheckSerializer(checks, many=True).data
        for item_data in data:
            item_data['is_low'] = item_data['item'] in low_items

        return Response(data)


class EssentialsToggleView(APIView):
    """PATCH toggle an essential item's checked state."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, check_id):
        try:
            check = EssentialsCheck.objects.get(
                pk=check_id, profile=request.user.profile,
            )
        except EssentialsCheck.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        check.is_checked = not check.is_checked
        check.checked_at = timezone.now() if check.is_checked else None
        check.save()
        return Response(EssentialsCheckSerializer(check).data)


class EssentialsAddView(APIView):
    """Add a custom essential item. Creates for today + will persist in future days."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        item_name = request.data.get('item', '').strip()
        if not item_name:
            return Response({'error': 'item is required'}, status=status.HTTP_400_BAD_REQUEST)

        today = date.today()
        if EssentialsCheck.objects.filter(profile=profile, date=today, item__iexact=item_name).exists():
            return Response(
                {'error': 'already_exists', 'message': f'{item_name} is already in your list'},
                status=status.HTTP_409_CONFLICT,
            )

        check = EssentialsCheck.objects.create(profile=profile, date=today, item=item_name)
        return Response(EssentialsCheckSerializer(check).data, status=status.HTTP_201_CREATED)


class EssentialsRemoveView(APIView):
    """Remove an essential item from today's list."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, check_id):
        try:
            check = EssentialsCheck.objects.get(pk=check_id, profile=request.user.profile)
        except EssentialsCheck.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        check.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class EssentialsMarkGroceryView(APIView):
    """Mark an essential item as added to grocery list."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, check_id):
        try:
            check = EssentialsCheck.objects.get(pk=check_id, profile=request.user.profile)
        except EssentialsCheck.DoesNotExist:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        check.added_to_grocery = True
        check.save(update_fields=['added_to_grocery'])
        return Response(EssentialsCheckSerializer(check).data)


class PantryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """List all pantry items."""
        items = UserPantryItem.objects.filter(profile=request.user.profile).values('id', 'name')
        return Response(list(items))


class PantryToggleView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        """Add or remove a pantry item. If it exists, remove it. If not, add it."""
        profile = request.user.profile
        name = request.data.get('name', '').strip()

        if not name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        existing = UserPantryItem.objects.filter(profile=profile, name__iexact=name).first()
        if existing:
            existing.delete()
            return Response({'in_pantry': False, 'name': name})

        UserPantryItem.objects.create(profile=profile, name=name)
        return Response({'in_pantry': True, 'name': name})


# -------------------------------------------------------------------
# Reminders
# -------------------------------------------------------------------
class ReminderListView(generics.ListAPIView):
    serializer_class = ReminderSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Reminder.objects.filter(profile=self.request.user.profile)


class ReminderUpcomingView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from django.utils import timezone as tz
        now = tz.now()

        reminders = Reminder.objects.filter(
            profile=request.user.profile,
            remind_at__gte=now,
            is_sent=False,
        ).order_by('remind_at')[:10]

        serializer = ReminderSerializer(reminders, many=True)
        return Response(serializer.data)


class ReminderDismissView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        try:
            reminder = Reminder.objects.get(
                pk=pk, profile=request.user.profile,
            )
        except Reminder.DoesNotExist:
            return Response(
                {'error': 'Reminder not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        reminder.is_sent = True
        reminder.save()

        serializer = ReminderSerializer(reminder)
        return Response(serializer.data)


# -------------------------------------------------------------------
# Onboarding Chat Agent
# -------------------------------------------------------------------
# In-memory session store (fine for single-server dev)
_onboarding_sessions = {}


class OnboardingStartView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        name = request.data.get('name', '').strip()
        user_type = request.data.get('user_type', 'other').strip()

        if not session_id or not name:
            return Response(
                {'error': 'session_id and name are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Map display user types to DB-compatible types
        type_map = {
            'parent': 'parent',
            'new_mom': 'new_mom',
            'homemaker': 'homemaker',
            'working_mom': 'working_mom',
            'professional': 'professional',
        }
        db_type = type_map.get(user_type, 'homemaker')

        agent = ProfileBuilderAgent(name, user_type)
        result = agent.start()

        _onboarding_sessions[session_id] = {
            'agent': agent,
            'name': name,
            'user_type': user_type,
            'db_type': db_type,
        }

        return Response({
            'message': result['message'],
            'is_complete': result.get('is_complete', False),
            'chips': result.get('chips', []),
        })


class OnboardingChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get('session_id')
        message = request.data.get('message', '').strip()

        if not session_id or not message:
            return Response(
                {'error': 'session_id and message are required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        session = _onboarding_sessions.get(session_id)
        if not session:
            return Response(
                {'error': 'Session not found. Please restart onboarding.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        agent = session['agent']
        result = agent.chat(message)

        if result.get('is_complete'):
            profile_data = result.get('profile_data', {})
            # Save profile data
            self._save_profile(request.user, session, profile_data)
            # Clean up session
            del _onboarding_sessions[session_id]

            return Response({
                'message': result['message'],
                'is_complete': True,
                'profile_data': profile_data,
                'confidence': profile_data.get('confidence', {}),
                'section_reasons': profile_data.get('section_reasons', {}),
            })

        return Response({
            'message': result['message'],
            'is_complete': result.get('is_complete', False),
        })

    def _save_profile(self, user, session, data):
        """Save the extracted profile data to the database."""
        from datetime import date

        profile, _ = UserProfile.objects.get_or_create(
            user=user,
            defaults={'display_name': session['name']},
        )

        # Update profile fields
        profile.display_name = data.get('display_name', session['name'])
        profile.user_type = session['db_type']
        profile.dietary_restrictions = data.get('dietary_restrictions', [])
        profile.health_conditions = data.get('health_conditions', [])
        profile.family_size = data.get('family_size', 1)
        profile.cuisine_preferences = data.get('cuisine_preferences', [])
        profile.breakfast_weight = data.get('breakfast_weight', 'light')
        profile.breakfast_types = data.get('breakfast_types', [])
        profile.lunch_weight = data.get('lunch_weight', 'heavy')
        profile.lunch_types = data.get('lunch_types', [])
        profile.dinner_weight = data.get('dinner_weight', 'light')
        profile.dinner_types = data.get('dinner_types', [])
        profile.snack_preferences = data.get('snack_preferences', [])
        profile.planning_modules = data.get('planning_modules', [])
        profile.grocery_day = data.get('grocery_day', 'Saturday')
        profile.exclusions = data.get('exclusions', [])
        profile.notes = data.get('notes', '')
        profile.module_preferences = data.get('module_preferences', {})

        # Build initial custom_layout from Layer 1 (user type) + Layer 2 (AI modules)
        profile.custom_layout = build_initial_layout(
            session['db_type'],
            data.get('planning_modules', []),
        )

        profile.onboarding_complete = True
        profile.save()

        # Create children. Missing age → skip (we can't plan without it, and
        # guessing produces wildly wrong activities). Missing name but known
        # age → save as "Child N" placeholder so the plan still works; the
        # user can rename in profile settings.
        for idx, child_data in enumerate(data.get('children', []), start=1):
            name = (child_data.get('name') or '').strip()
            age = child_data.get('age', 0)
            age_months = child_data.get('age_months', 0)

            if not age and not age_months:
                continue

            if not name:
                name = f'Child {idx}'

            today = date.today()
            if age_months and age_months > 0:
                # Baby — age given in months
                months = int(age_months)
                year = today.year if today.month > months else today.year - 1
                month = today.month - months
                if month <= 0:
                    month += 12
                    year -= 1
                dob = date(year, max(1, min(12, month)), 1)
            else:
                # Older child — age given in years
                age_int = max(0, int(float(age)))
                dob = date(today.year - age_int, 1, 1)

            Child.objects.create(
                parent=profile,
                name=name,
                date_of_birth=dob,
                interests=child_data.get('interests', []),
                school_name=child_data.get('school_name', ''),
            )

        # Create schedule events
        for event_data in data.get('schedule_events', []):
            if event_data.get('title'):
                # Link to child by name if provided
                child = None
                child_name = event_data.get('child_name', '')
                if child_name:
                    child = profile.children.filter(name__icontains=child_name).first()

                ScheduleEvent.objects.create(
                    profile=profile,
                    child=child,
                    event_type=event_data.get('event_type', 'personal'),
                    title=event_data['title'],
                    start_time=event_data.get('start_time') or '09:00',
                    end_time=event_data.get('end_time') or None,
                    recurrence=event_data.get('recurrence', 'weekdays'),
                    recurrence_days=event_data.get('recurrence_days', []),
                )


# -------------------------------------------------------------------
# Kids Activities
# -------------------------------------------------------------------
class GenerateKidsActivitiesView(APIView):
    """POST /api/v1/kids-activities/generate/ — generate (or retry) today's pack."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        # Only children 3+ can use activities.
        if not any(c.age >= 3 for c in profile.children.all()):
            return Response(
                {'error': 'Activities are for children aged 3 and up.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = date.today()

        existing = KidsActivityPlan.objects.filter(
            profile=profile, week_start_date=today,
        ).first()
        if existing and existing.days.exists():
            return Response(
                {'error': 'Activities already generated for today.'},
                status=status.HTTP_409_CONFLICT,
            )

        try:
            generator = KidsActivityGenerator()
            plan = generator.generate_daily_plan(profile, today)
            serializer = KidsActivityPlanSerializer(plan)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            logger.error(f'Manual kids activities generation failed: {e}')
            return Response(
                {'error': 'Could not generate activities right now. Please try again in a moment.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class CurrentKidsActivitiesView(APIView):
    """GET /api/v1/kids-activities/current/ — get today's pack (auto-generate if missing)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        today = date.today()

        plan = KidsActivityPlan.objects.filter(
            profile=profile,
            week_start_date=today,
        ).first()

        # Only children 3+ can use activities — under-3s are ignored here.
        has_children = any(c.age >= 3 for c in profile.children.all())

        if not plan and has_children:
            try:
                generator = KidsActivityGenerator()
                plan = generator.generate_daily_plan(profile, today)
            except Exception as e:
                logger.error(f'On-demand kids activities generation failed: {e}')
                return Response({'plan': None, 'has_children': has_children})

        if not plan:
            return Response({'plan': None, 'has_children': has_children})

        serializer = KidsActivityPlanSerializer(plan)
        return Response({'plan': serializer.data, 'has_children': True})


class KidsActivityMarkReadView(APIView):
    """POST /api/v1/kids-activities/<day_id>/mark-read/"""
    permission_classes = [IsAuthenticated]

    def post(self, request, day_id):
        profile = request.user.profile

        try:
            day = KidsActivityDay.objects.select_related('plan', 'child').get(id=day_id)
        except KidsActivityDay.DoesNotExist:
            return Response(
                {'error': 'Activity day not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if day.plan.profile != profile:
            return Response(
                {'error': 'Not your activity plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not day.unlocked:
            return Response(
                {'error': 'This day is still locked.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if day.is_read:
            return Response(
                {'error': 'Already marked as read.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        day.mark_read()

        # Return full updated plan so frontend gets refreshed unlock states
        serializer = KidsActivityPlanSerializer(day.plan)
        return Response(serializer.data)


class KidsActivityDownloadView(APIView):
    """GET /api/v1/kids-activities/<day_id>/download/ — generate + serve PDF."""
    permission_classes = [IsAuthenticated]

    def get(self, request, day_id):
        from django.http import FileResponse

        profile = request.user.profile

        try:
            day = KidsActivityDay.objects.select_related('plan', 'child').get(id=day_id)
        except KidsActivityDay.DoesNotExist:
            return Response(
                {'error': 'Activity day not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        if day.plan.profile != profile:
            return Response(
                {'error': 'Not your activity plan.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        if not day.unlocked:
            return Response(
                {'error': 'This day is still locked.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Generate PDF
        try:
            generator = KidsActivityPDFGenerator()
            filepath = generator.generate_for_day(day)
        except Exception as e:
            return Response(
                {'error': f'PDF generation failed: {str(e)}'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # Mark as downloaded (also unlocks next day)
        if not day.is_downloaded:
            day.mark_downloaded()

        return FileResponse(
            open(filepath, 'rb'),
            content_type='application/pdf',
            as_attachment=True,
            filename=f'{day.child.name}_activity_day{day.day_of_week + 1}.pdf',
        )
