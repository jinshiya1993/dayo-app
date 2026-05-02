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
    ChatConversation, ChatMessage, CustomSectionDeletionLog,
    CustomSectionList, CustomSectionTask, DayPlan, EssentialsCheck,
    FavouriteMeal, GroceryItem,
    GroceryList, HouseholdMember, HouseworkList, HouseworkTask, HouseworkTaskDeletionLog, HouseworkTemplate,
    KidsActivityDay, KidsActivityPlan, MealSwapLog,
    Reminder, ScheduleEvent, TodayTimelineCheck, UserPantryItem, UserProfile,
)
from .serializers import (
    ChatConversationListSerializer,
    ChatConversationSerializer,
    ChatMessageSerializer,
    CustomSectionListSerializer,
    HouseholdMemberSerializer,
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
from .services.meal_suggester import get_suggestions as get_meal_suggestions
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
class HouseholdMemberViewSet(viewsets.ModelViewSet):
    serializer_class = HouseholdMemberSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return HouseholdMember.objects.filter(parent=self.request.user.profile)

    def perform_create(self, serializer):
        profile = self.request.user.profile
        member = serializer.save(parent=profile)

        # Make sure the kids_activities section is visible on the dashboard
        # when the user adds their first CHILD (not a partner/helper/etc.).
        if member.role != HouseholdMember.Role.CHILD:
            return
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
        # Auto-fill meals if running low (< 3 days planned). Don't block
        # the response on failure but log the traceback so we can see why
        # generation is failing in server logs.
        try:
            generator = PlanGenerator()
            generator.ensure_meals_ahead(request.user.profile)
        except Exception:
            logger.exception('DayPlanDetailView.retrieve: ensure_meals_ahead failed')
        return super().retrieve(request, *args, **kwargs)


# -------------------------------------------------------------------
# Meal Actions — swap, substitute, favourite
# -------------------------------------------------------------------
class ExtractIngredientsView(APIView):
    """POST /plans/<date>/extract-ingredients/<meal_type>/

    For old meals saved before we required `ingredients` in the schema.
    Reads the meal's name + description (+ any steps), asks Gemini to extract
    a clean ingredient list, persists it onto the meal in plan_data, and
    returns the updated meal. Idempotent — if ingredients already exist,
    just returns the meal as-is without hitting Gemini.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, date, meal_type):
        import json
        import re
        from django.conf import settings as django_settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
            return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            day_plan = DayPlan.objects.get(profile=request.user.profile, date=date)
        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan for that date.'}, status=status.HTTP_404_NOT_FOUND)

        plan_data = day_plan.plan_data or {}
        meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
        meal = (plan_data.get(meals_key) or {}).get(meal_type) or {}

        # Already has ingredients? Nothing to do.
        if isinstance(meal.get('ingredients'), list) and meal['ingredients']:
            return Response({'meal': meal})

        name = meal.get('name', '').strip()
        if not name:
            return Response({'error': 'Meal has no name to extract ingredients from.'}, status=status.HTTP_400_BAD_REQUEST)

        recipe_text_parts = [meal.get('description', '')]
        if isinstance(meal.get('steps'), list):
            recipe_text_parts.extend(meal['steps'])
        recipe_text = '\n'.join(p for p in recipe_text_parts if p).strip()

        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=django_settings.GEMINI_API_KEY,
            temperature=0.2,
            max_output_tokens=2048,
            transport='rest',
        )
        messages = [
            SystemMessage(content=(
                'Extract the ingredient list for a recipe. Return ONLY a JSON object '
                'of the shape {"ingredients": ["item 1", "item 2", ...]}. '
                'Each item: short, specific, includes quantity when implied (e.g. '
                '"200g firm tofu", "2 eggs", "1 cup spinach"). 6-12 items max. '
                'Keep each item under 8 words. '
                'NEVER put the word "Halal" in any ingredient name — say '
                '"chicken broth" not "Halal chicken broth", "soy sauce" not '
                '"Halal soy sauce". '
                'No prose, no markdown fences, no extra keys.'
            )),
            HumanMessage(content=f'Dish: {name}\n\nRecipe:\n{recipe_text or "(no description provided)"}'),
        ]

        try:
            response = llm.invoke(messages)
        except Exception as e:
            logger.error(f'extract-ingredients Gemini error: {e}')
            return Response({'error': 'Could not extract ingredients right now.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw = (response.content or '').strip()
        # Strip markdown fences if Gemini ignored the "no markdown" instruction.
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1)
        else:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f'extract-ingredients JSON parse failed ({e}): {raw[:300]}')
            return Response({'error': 'Could not parse ingredients.'}, status=status.HTTP_502_BAD_GATEWAY)

        ingredients = data.get('ingredients') or []
        ingredients = [str(i).strip() for i in ingredients if str(i).strip()]
        if not ingredients:
            return Response({'error': 'No ingredients found.'}, status=status.HTTP_502_BAD_GATEWAY)

        meal['ingredients'] = ingredients
        meals_dict = plan_data.get(meals_key) or {}
        meals_dict[meal_type] = meal
        plan_data[meals_key] = meals_dict
        day_plan.plan_data = plan_data
        day_plan.save(update_fields=['plan_data', 'updated_at'])

        return Response({'meal': meal})


class ExtractRecipeView(APIView):
    """POST /plans/<date>/extract-recipe/<meal_type>/

    Backfills steps + kcal + tags + pairings for old meals saved before
    the schema required them. Reads the meal's name + description +
    ingredients along with the user's profile (health conditions) and
    household (members + their per-member dietary needs), asks Gemini
    for the missing fields in a single call, persists onto plan_data,
    returns the updated meal.

    Idempotent — if steps + kcal + tags are all already present, returns
    the meal as-is without hitting Gemini. Pairings are conditional, so
    we don't gate on them (would re-fetch every time for simple meals).
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, date, meal_type):
        import json
        import re
        from django.conf import settings as django_settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
            return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            day_plan = DayPlan.objects.get(profile=request.user.profile, date=date)
        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan for that date.'}, status=status.HTTP_404_NOT_FOUND)

        plan_data = day_plan.plan_data or {}
        meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
        meal = (plan_data.get(meals_key) or {}).get(meal_type) or {}

        has_steps = isinstance(meal.get('steps'), list) and meal['steps']
        has_kcal = isinstance(meal.get('kcal'), (int, float)) and meal['kcal']
        has_tags = isinstance(meal.get('tags'), list) and meal['tags']
        if has_steps and has_kcal and has_tags:
            return Response({'meal': meal})

        name = meal.get('name', '').strip()
        if not name:
            return Response({'error': 'Meal has no name to extract a recipe from.'}, status=status.HTTP_400_BAD_REQUEST)

        ingredients = meal.get('ingredients') or []
        ingredients_text = ', '.join(str(i) for i in ingredients) if ingredients else '(none listed)'
        description = meal.get('description', '') or '(no description)'

        # Build profile + household context so the LLM can drive condition-
        # aware tags ("PCOS-friendly") and decide when pairings are needed.
        profile = request.user.profile
        conditions = profile.health_conditions or []
        conditions_text = ', '.join(str(c) for c in conditions) if conditions else '(none)'

        members = list(profile.members.all())
        if members:
            member_lines = []
            for m in members:
                bits = [f'{m.name} ({m.role}, age {m.age})']
                m_conds = m.member_health_conditions or []
                if m_conds:
                    bits.append(f'conditions: {", ".join(str(c) for c in m_conds)}')
                m_diet = m.member_dietary or []
                if m_diet:
                    bits.append(f'dietary: {", ".join(str(d) for d in m_diet)}')
                member_lines.append(' — '.join(bits))
            household_text = '\n'.join(f'- {l}' for l in member_lines)
        else:
            household_text = '(solo cook, no other members)'

        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=django_settings.GEMINI_API_KEY,
            temperature=0.3,
            max_output_tokens=2048,
            transport='rest',
        )
        messages = [
            SystemMessage(content=(
                'You are filling in missing fields for a recipe. Return ONLY a JSON object of shape:\n'
                '{\n'
                '  "steps": ["Step 1", "Step 2", ...],\n'
                '  "kcal": 320,\n'
                '  "tags": ["PCOS-friendly", "High protein"],\n'
                '  "pairings": [{"for": "Sara, Ahmed", "with": "Quinoa pilaf", "why": "low-GI"}]\n'
                '}\n'
                'No markdown fences, no extra keys.\n\n'
                'steps: 4-8 short imperative sentences. Each step = one action.\n'
                'kcal: integer estimate per single adult serving. Realistic ranges: '
                'breakfast 250-450, lunch 400-650, dinner 400-700, snack 80-220.\n'
                'tags: 2-3 SHORT (1-3 word) dietary highlights. Pick from condition tags '
                '(PCOS-friendly, Diabetic-friendly, Heart-healthy, Anti-inflammatory, Low GI), '
                'nutrition tags (High protein, Iron-rich, Fiber-rich, Low carb, Healthy fats), '
                'context tags (Family-friendly, Quick, One-pan, Make-ahead, Comfort), '
                'recovery tags (Postpartum, Lactation support). '
                "If the user has health conditions, AT LEAST ONE tag must reflect a condition.\n"
                'pairings: ONLY include when household members have differing dietary needs '
                '(child + adult, member with a condition others don\'t share, per-member '
                'dietary override). Each entry: `for` (real first names), `with` (a SIMPLE side '
                "— rice, chappathi, salad, yoghurt, fruit; never another recipe), `why` "
                '(one-line reason). If everyone has identical constraints, return pairings: [].\n'
                'NEVER use the word "Halal" in any field.'
            )),
            HumanMessage(content=(
                f'Dish: {name}\n'
                f'Meal type: {meal_type}\n'
                f'Description: {description}\n'
                f'Ingredients: {ingredients_text}\n\n'
                f"User's health conditions: {conditions_text}\n"
                f'Household members:\n{household_text}\n'
            )),
        ]

        try:
            response = llm.invoke(messages)
        except Exception as e:
            logger.error(f'extract-recipe Gemini error: {e}')
            return Response({'error': 'Could not extract recipe right now.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw = (response.content or '').strip()
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1)
        else:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f'extract-recipe JSON parse failed ({e}): {raw[:300]}')
            return Response({'error': 'Could not parse recipe.'}, status=status.HTTP_502_BAD_GATEWAY)

        steps = [str(s).strip() for s in (data.get('steps') or []) if str(s).strip()]
        if not steps and not has_steps:
            return Response({'error': 'No steps found.'}, status=status.HTTP_502_BAD_GATEWAY)
        if steps:
            meal['steps'] = steps

        kcal_raw = data.get('kcal')
        try:
            kcal_int = int(kcal_raw) if kcal_raw is not None else None
        except (TypeError, ValueError):
            kcal_int = None
        if kcal_int and kcal_int > 0:
            meal['kcal'] = kcal_int

        tags = [str(t).strip() for t in (data.get('tags') or []) if str(t).strip()]
        if tags:
            meal['tags'] = tags[:3]

        # Pairings — only overwrite when LLM returned a non-empty list.
        # Empty list means "no per-person sides needed", which is a valid
        # answer; we don't want to clobber a previously good pairings list
        # with [] just because the LLM decided differently this run.
        pairings_raw = data.get('pairings')
        if isinstance(pairings_raw, list) and pairings_raw:
            cleaned = []
            for p in pairings_raw:
                if not isinstance(p, dict):
                    continue
                for_v = str(p.get('for', '')).strip()
                with_v = str(p.get('with', '')).strip()
                why_v = str(p.get('why', '')).strip()
                if for_v and with_v:
                    cleaned.append({'for': for_v, 'with': with_v, 'why': why_v})
            if cleaned:
                meal['pairings'] = cleaned

        meals_dict = plan_data.get(meals_key) or {}
        meals_dict[meal_type] = meal
        plan_data[meals_key] = meals_dict
        day_plan.plan_data = plan_data
        day_plan.save(update_fields=['plan_data', 'updated_at'])

        return Response({'meal': meal})


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

            if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
                return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)

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


class RenameMealView(APIView):
    """POST /plans/<date>/rename-meal/

    User-edited meal name from the weekly card. Replaces the meal's name,
    drops cached ingredients/steps/pairings/tags (they describe the old
    dish), and asks Gemini for fresh prep_mins + kcal + tags + a short
    description so the day card has accurate metadata immediately.
    Ingredients and steps are left unset — RecipePage will lazy-extract
    them on next open via the existing extract endpoints.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, date):
        import json
        import re
        from django.conf import settings as django_settings
        from langchain_google_genai import ChatGoogleGenerativeAI
        from langchain_core.messages import HumanMessage, SystemMessage

        meal_type = request.data.get('meal_type')
        new_name = (request.data.get('name') or '').strip()

        if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
            return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)
        if not new_name:
            return Response({'error': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            day_plan = DayPlan.objects.get(profile=request.user.profile, date=date)
        except DayPlan.DoesNotExist:
            return Response({'error': 'No plan for that date.'}, status=status.HTTP_404_NOT_FOUND)

        plan_data = day_plan.plan_data or {}
        meals_key = 'mom_meals' if 'mom_meals' in plan_data else 'meals'
        meals_dict = plan_data.get(meals_key) or {}
        meal = dict(meals_dict.get(meal_type) or {})

        if meal.get('name', '').strip().lower() == new_name.lower():
            return Response({'meal': meal})

        profile = request.user.profile
        conditions = profile.health_conditions or []
        conditions_text = ', '.join(str(c) for c in conditions) if conditions else '(none)'

        llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=django_settings.GEMINI_API_KEY,
            temperature=0.3,
            max_output_tokens=512,
            transport='rest',
        )
        messages = [
            SystemMessage(content=(
                'You are estimating quick metadata for a renamed meal. Return ONLY a JSON object:\n'
                '{"prep_mins": 20, "kcal": 420, "description": "Short one-sentence summary", '
                '"tags": ["High protein", "Quick"]}\n'
                'No markdown fences, no extra keys.\n'
                'prep_mins: integer minutes for one cook session.\n'
                'kcal: integer per single adult serving. Realistic ranges: '
                'breakfast 250-450, lunch 400-650, dinner 400-700, snack 80-220.\n'
                'description: one short sentence describing the dish.\n'
                'tags: 2-3 SHORT (1-3 word) dietary highlights. If the user has health '
                'conditions, AT LEAST ONE tag must reflect a condition '
                '(PCOS-friendly, Diabetic-friendly, Heart-healthy, Anti-inflammatory, Low GI).\n'
                'NEVER use the word "Halal".'
            )),
            HumanMessage(content=(
                f'Dish: {new_name}\n'
                f'Meal type: {meal_type}\n'
                f"User's health conditions: {conditions_text}\n"
            )),
        ]

        try:
            response = llm.invoke(messages)
        except Exception as e:
            logger.error(f'rename-meal Gemini error: {e}')
            return Response({'error': 'Could not refresh meal details right now.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        raw = (response.content or '').strip()
        fenced = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', raw, re.DOTALL)
        if fenced:
            raw = fenced.group(1)
        else:
            match = re.search(r'\{.*\}', raw, re.DOTALL)
            if match:
                raw = match.group(0)
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            logger.error(f'rename-meal JSON parse failed ({e}): {raw[:300]}')
            data = {}

        new_meal = {'name': new_name}

        prep_raw = data.get('prep_mins')
        try:
            prep_int = int(prep_raw) if prep_raw is not None else None
        except (TypeError, ValueError):
            prep_int = None
        if prep_int and prep_int > 0:
            new_meal['prep_mins'] = prep_int

        kcal_raw = data.get('kcal')
        try:
            kcal_int = int(kcal_raw) if kcal_raw is not None else None
        except (TypeError, ValueError):
            kcal_int = None
        if kcal_int and kcal_int > 0:
            new_meal['kcal'] = kcal_int

        desc = (data.get('description') or '').strip()
        if desc:
            new_meal['description'] = desc

        tags = [str(t).strip() for t in (data.get('tags') or []) if str(t).strip()]
        if tags:
            new_meal['tags'] = tags[:3]

        meals_dict[meal_type] = new_meal
        plan_data[meals_key] = meals_dict
        day_plan.plan_data = plan_data
        day_plan.save(update_fields=['plan_data', 'updated_at'])

        return Response({'meal': new_meal})


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

        if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
            return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)
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


class MealSuggestionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cuisine = (request.query_params.get('cuisine') or '').strip()
        if not cuisine:
            return Response(
                {'error': 'cuisine query param required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(get_meal_suggestions(cuisine))


class WeeklyMealsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        """Get meals for the next 7 days from existing day plans.

        Returns full meal objects (name, prep_mins, kcal, tags, ingredients,
        steps) plus the day's meal_health_banner so the inline weekly UI
        can render rich cards without hitting the per-day plan endpoint.

        Auto-fills missing days via ensure_meals_ahead so direct visits to
        the weekly page (without first loading the dashboard) still work.
        """
        from datetime import date, timedelta
        profile = request.user.profile

        # Mirrors the auto-fill behavior of DayPlanDetailView.retrieve().
        # No-op if the week is already planned. Don't block the response on
        # failure but log the full traceback so server logs surface why
        # generation is failing instead of silently returning empty days.
        try:
            generator = PlanGenerator()
            generator.ensure_meals_ahead(profile)
        except Exception:
            logger.exception('WeeklyMealsView: ensure_meals_ahead failed')

        today = date.today()
        days = []

        def _meal_summary(m):
            if not isinstance(m, dict):
                return None
            return {
                'name': m.get('name', ''),
                'prep_mins': m.get('prep_mins'),
                'kcal': m.get('kcal'),
                'tags': m.get('tags') or [],
                'ingredients': m.get('ingredients') or [],
                'steps': m.get('steps') or [],
                'description': m.get('description', ''),
                'pairings': m.get('pairings') or [],
            }

        for i in range(7):
            d = today + timedelta(days=i)
            plan = DayPlan.objects.filter(profile=profile, date=d, status='ready').first()
            meals_raw = {}
            banner = ''
            if plan and plan.plan_data:
                meals_raw = plan.plan_data.get('meals') or plan.plan_data.get('mom_meals') or {}
                banner = plan.plan_data.get('meal_health_banner') or ''
            days.append({
                'date': str(d),
                'day_name': d.strftime('%A'),
                'is_today': i == 0,
                'has_plan': plan is not None,
                'meal_health_banner': banner,
                'meals': {
                    'breakfast': _meal_summary(meals_raw.get('breakfast')),
                    'lunch': _meal_summary(meals_raw.get('lunch')),
                    'dinner': _meal_summary(meals_raw.get('dinner')),
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

        if meal_type not in ('breakfast', 'lunch', 'dinner', 'snack'):
            return Response({'error': 'meal_type must be breakfast, lunch, dinner, or snack'}, status=status.HTTP_400_BAD_REQUEST)
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

        # Idempotent retry: if there's already an active list, return it
        # rather than kicking off a second Gemini call. Prevents double-mount
        # / double-click from generating two lists in quick succession and
        # wiping the first via the generator's "mark all open lists completed"
        # step.
        existing = GroceryList.objects.filter(
            profile=profile, completed=False,
        ).order_by('-generated_at').first()
        if existing:
            serializer = GroceryListSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

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
# Today timeline
# ===================================================================

# Default times when a meal object doesn't carry its own. Match the
# constants used on the frontend so order of operations is consistent.
_DEFAULT_MEAL_TIMES = {
    'breakfast': '07:00',
    'lunch': '13:00',
    'snack': '17:00',
    'dinner': '19:00',
}


def _event_active_today(ev, today):
    """Return True if a ScheduleEvent should appear on today's timeline."""
    if not ev.is_active:
        return False
    py_day = today.weekday()  # Mon=0 … Sun=6
    rec = ev.recurrence
    if rec == 'none':
        return ev.event_date == today if ev.event_date else True
    if rec == 'daily':
        return True
    if rec == 'weekdays':
        return py_day < 5
    if rec in ('weekly', 'custom'):
        return py_day in (ev.recurrence_days or [])
    return False


def _build_timeline_items(profile, target_date):
    """Aggregate today's items from meals, schedule events, class alerts,
    selfcare, and grocery. Each item carries a stable item_key so checks can
    be looked up. Items are returned sorted by time (HH:MM lexicographic)."""

    items = []

    # ── Meals from DayPlan ───────────────────────────────────────
    day_plan = DayPlan.objects.filter(profile=profile, date=target_date).first()
    plan_data = (day_plan.plan_data if day_plan else None) or {}
    meals = plan_data.get('meals') or plan_data.get('mom_meals') or {}

    for meal_type in ('breakfast', 'lunch', 'snack', 'dinner'):
        meal = meals.get(meal_type)
        if not isinstance(meal, dict) or not meal.get('name'):
            continue
        time = meal.get('time') or _DEFAULT_MEAL_TIMES.get(meal_type, '12:00')
        prep = meal.get('prep_mins')
        kcal = meal.get('kcal')
        sub_bits = []
        if prep:
            sub_bits.append(f'{prep} min')
        if kcal:
            sub_bits.append(f'{kcal} kcal')
        items.append({
            'item_key': f'meal:{meal_type}',
            'kind': 'meal',
            'meal_type': meal_type,
            'time': time,
            'title': f'{meal_type.title()} — {meal["name"]}',
            'subtitle': ' · '.join(sub_bits),
        })

    # ── Class alerts (JSON inside plan_data) ─────────────────────
    for alert in plan_data.get('class_alerts') or []:
        if not isinstance(alert, dict):
            continue
        time = (alert.get('time') or '').strip()
        title_bits = [str(p) for p in (alert.get('class'), alert.get('child')) if p]
        title = ' — '.join(title_bits) or 'Class alert'
        sub_bits = []
        if alert.get('leave_by'):
            sub_bits.append(f"leave by {alert['leave_by']}")
        if alert.get('location'):
            sub_bits.append(alert['location'])
        items.append({
            'item_key': f'class:{time}' if time else f'class:{title.lower()[:30]}',
            'kind': 'class',
            'time': time,
            'title': title,
            'subtitle': ' · '.join(sub_bits),
        })

    # ── Self-care (object or list inside plan_data) ──────────────
    selfcare_raw = plan_data.get('selfcare')
    selfcare_items = selfcare_raw if isinstance(selfcare_raw, list) else (
        [selfcare_raw] if isinstance(selfcare_raw, dict) else []
    )
    for sc in selfcare_items:
        if not isinstance(sc, dict):
            continue
        time = (sc.get('time') or '').strip()
        activity = sc.get('activity') or 'Self-care time'
        sub = sc.get('duration') or ''
        items.append({
            'item_key': f'selfcare:{time}' if time else f'selfcare:{activity.lower()[:30]}',
            'kind': 'selfcare',
            'time': time,
            'title': activity,
            'subtitle': sub,
        })

    # ── Schedule events (recurring + one-off) ────────────────────
    for ev in ScheduleEvent.objects.filter(profile=profile, is_active=True):
        if not _event_active_today(ev, target_date):
            continue
        time = ev.start_time.strftime('%H:%M') if ev.start_time else ''
        sub_bits = []
        if ev.location:
            sub_bits.append(ev.location)
        if ev.travel_time_minutes:
            sub_bits.append(f'travel {ev.travel_time_minutes}m')
        items.append({
            'item_key': f'event:{ev.id}',
            'kind': _event_kind(ev.event_type),
            'time': time,
            'title': ev.title,
            'subtitle': ' · '.join(sub_bits),
        })

    # ── Grocery checkpoint (if generated today) ──────────────────
    grocery = GroceryList.objects.filter(profile=profile).order_by('-generated_at').first()
    if grocery and grocery.generated_at.date() == target_date:
        item_count = grocery.items.count() if hasattr(grocery, 'items') else 0
        items.append({
            'item_key': 'grocery:ready',
            'kind': 'grocery',
            'time': grocery.generated_at.strftime('%H:%M'),
            'title': 'Grocery list ready',
            'subtitle': f'{item_count} items' if item_count else '',
        })

    items.sort(key=lambda it: it.get('time') or '99:99')
    return items


def _event_kind(event_type):
    """Group ScheduleEvent.event_type into a small set of icon kinds."""
    if event_type in ('school_drop', 'school_pick', 'child_activity'):
        return 'school'
    if event_type in ('meeting', 'work_shift'):
        return 'work'
    if event_type in ('class', 'study', 'exam', 'assignment_due'):
        return 'study'
    return 'event'


class TodayTimelineView(APIView):
    """GET /api/v1/timeline/today/ — returns today's aggregated timeline
    plus the list of item_keys the user has already checked."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile = request.user.profile
        today = date.today()

        items = _build_timeline_items(profile, today)
        checks = list(
            TodayTimelineCheck.objects.filter(
                profile=profile, date=today, completed=True,
            ).values_list('item_key', flat=True)
        )

        return Response({
            'date': today.isoformat(),
            'items': items,
            'checked_keys': checks,
        })


class TimelineCheckToggleView(APIView):
    """POST /api/v1/timeline/check/ — body {item_key, completed}.
    Idempotent upsert into TodayTimelineCheck for the current date."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        item_key = (request.data.get('item_key') or '').strip()
        if not item_key:
            return Response({'error': 'item_key is required'}, status=status.HTTP_400_BAD_REQUEST)
        completed = bool(request.data.get('completed', True))

        profile = request.user.profile
        today = date.today()

        if completed:
            TodayTimelineCheck.objects.update_or_create(
                profile=profile, date=today, item_key=item_key,
                defaults={'completed': True, 'completed_at': timezone.now()},
            )
        else:
            TodayTimelineCheck.objects.filter(
                profile=profile, date=today, item_key=item_key,
            ).delete()

        return Response({'item_key': item_key, 'completed': completed})


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


def _derive_user_type(works_outside_home, children):
    """Pick a legacy user_type label from the flags + children data.

    Kept as a derived field on UserProfile so plan_generator's per-type
    JSON schemas, admin filters, and analytics keep working without a
    bigger refactor. Priority: baby takes precedence to preserve
    postpartum meal/plan tailoring. The 'professional' type has been
    retired — adults with no children fall under 'homemaker' regardless
    of whether they work outside the home.
    """
    from datetime import date
    today = date.today()

    def months_old(child):
        dob = child.date_of_birth
        return (today.year - dob.year) * 12 + (today.month - dob.month)

    has_infant = any(months_old(c) < 24 for c in children)
    has_kid = any(2 <= c.age < 13 for c in children)

    if has_infant:
        return 'new_mom'
    if has_kid and works_outside_home:
        return 'working_mom'
    if has_kid:
        return 'parent'
    return 'homemaker'


def save_onboarding_profile(user, profile_data, fallback_name=None, fallback_user_type=None):
    """Persist onboarding profile_data to the DB.

    Shared by the chat-based and form-based onboarding flows. The form
    sends `works_outside_home`; the chat agent sends `user_type`. If only
    user_type is present we infer works_outside_home from it so chat-flow
    users don't lose their work-focused sections.
    """
    data = profile_data or {}
    display_name = (data.get('display_name') or fallback_name or '').strip() or 'Friend'

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={'display_name': display_name},
    )

    profile.display_name = display_name
    if data.get('age') is not None:
        try:
            profile.age = int(data['age']) or None
        except (TypeError, ValueError):
            pass

    explicit_user_type = data.get('user_type') or fallback_user_type
    if 'works_outside_home' in data:
        profile.works_outside_home = bool(data['works_outside_home'])
    else:
        profile.works_outside_home = explicit_user_type == 'working_mom'
    profile.dietary_restrictions = data.get('dietary_restrictions', [])
    profile.health_conditions = data.get('health_conditions', [])
    profile.family_size = data.get('family_size', 1)
    profile.cuisine_preferences = data.get('cuisine_preferences', [])
    profile.secondary_cuisines = data.get('secondary_cuisines', [])
    if data.get('spice_level') is not None:
        try:
            level = int(data['spice_level'])
            if 1 <= level <= 5:
                profile.spice_level = level
        except (TypeError, ValueError):
            pass

    profile.kids_activity_focus = data.get('kids_activity_focus', [])
    if data.get('kids_default_difficulty') is not None:
        profile.kids_default_difficulty = data.get('kids_default_difficulty', '') or ''
    if data.get('kids_activity_time_pref') is not None:
        profile.kids_activity_time_pref = data.get('kids_activity_time_pref', '') or ''
    profile.breakfast_weight = data.get('breakfast_weight', 'light')
    profile.breakfast_types = data.get('breakfast_types', [])
    profile.lunch_weight = data.get('lunch_weight', 'heavy')
    profile.lunch_types = data.get('lunch_types', [])
    profile.dinner_weight = data.get('dinner_weight', 'light')
    profile.dinner_types = data.get('dinner_types', [])
    profile.snack_preferences = data.get('snack_preferences', [])
    profile.planning_modules = data.get('planning_modules', [])
    profile.grocery_day = data.get('grocery_day', 'Saturday')
    profile.cooking_responsibility = data.get('cooking_responsibility', 'me')
    profile.exclusions = data.get('exclusions', [])
    profile.notes = data.get('notes', '')
    profile.module_preferences = data.get('module_preferences', {})
    # user_type / custom_layout are derived AFTER children are created,
    # because both depend on the children's age bands.
    profile.save()

    # Household members. Backwards-compat: payloads using `children` are
    # treated as children. New payloads use `members` with explicit roles.
    raw_members = data.get('members')
    if raw_members is None:
        raw_members = [{**c, 'role': 'child'} for c in data.get('children', [])]

    for idx, member_data in enumerate(raw_members, start=1):
        name = (member_data.get('name') or '').strip()
        age = member_data.get('age', 0)
        age_months = member_data.get('age_months', 0)
        role = member_data.get('role') or 'child'

        if not age and not age_months:
            continue

        if not name:
            name = f'Child {idx}' if role == 'child' else f'{role.title()} {idx}'

        today = date.today()
        if age_months and age_months > 0:
            months = int(age_months)
            year = today.year if today.month > months else today.year - 1
            month = today.month - months
            if month <= 0:
                month += 12
                year -= 1
            dob = date(year, max(1, min(12, month)), 1)
        else:
            age_int = max(0, int(float(age)))
            dob = date(today.year - age_int, 1, 1)

        HouseholdMember.objects.create(
            parent=profile,
            role=role,
            name=name,
            date_of_birth=dob,
            interests=member_data.get('interests', []),
            school_name=member_data.get('school_name', ''),
            member_dietary=member_data.get('member_dietary', []),
            member_health_conditions=member_data.get('member_health_conditions', []),
            member_exclusions=member_data.get('member_exclusions', []),
        )

    for event_data in data.get('schedule_events', []):
        if event_data.get('title'):
            child = None
            child_name = event_data.get('child_name', '')
            if child_name:
                child = profile.members.filter(role='child', name__icontains=child_name).first()

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

    # Now that children exist, derive user_type and compose the dashboard
    # layout from the actual data. If the caller explicitly set a
    # user_type (chat flow), honour it — otherwise derive from data.
    children_qs = list(profile.members.filter(role='child'))
    if explicit_user_type:
        profile.user_type = explicit_user_type
    else:
        profile.user_type = _derive_user_type(profile.works_outside_home, children_qs)
    profile.custom_layout = build_initial_layout(profile)
    profile.onboarding_complete = True
    profile.save()

    return profile


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
            save_onboarding_profile(
                request.user,
                profile_data,
                fallback_name=session['name'],
                fallback_user_type=session['db_type'],
            )
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


class OnboardingCompleteView(APIView):
    """POST /api/v1/onboarding/complete/ — form-based onboarding submission."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile_data = request.data or {}
        # user_type is derived server-side now; only display_name is required.
        if not profile_data.get('display_name'):
            return Response(
                {'error': 'display_name is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        save_onboarding_profile(request.user, profile_data)

        return Response({
            'is_complete': True,
            'profile_data': profile_data,
        })


# -------------------------------------------------------------------
# Kids Activities
# -------------------------------------------------------------------
class GenerateKidsActivitiesView(APIView):
    """POST /api/v1/kids-activities/generate/ — generate (or retry) today's pack."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile = request.user.profile
        # Ages 2-12 qualify (2-3 gets a story-only pack; teens don't get one).
        if not any(2 <= m.age < 13 for m in profile.members.filter(role='child')):
            return Response(
                {'error': 'Activities are for children aged 2 through 12.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        today = date.today()

        # Retry is idempotent — if a complete plan is already on disk (e.g.
        # from a concurrent /current/ call that won the race), return it
        # instead of 409 so the UI can recover. The generator itself wipes
        # any empty-shell plan on next run.
        existing = KidsActivityPlan.objects.filter(
            profile=profile, week_start_date=today,
        ).first()
        if existing and existing.days.exists():
            serializer = KidsActivityPlanSerializer(existing)
            return Response(serializer.data, status=status.HTTP_200_OK)

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

        # Ages 2-12 qualify for an activity pack (2-3 gets story-only;
        # teens aren't served by this section).
        has_children = any(2 <= m.age < 13 for m in profile.members.filter(role='child'))

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
