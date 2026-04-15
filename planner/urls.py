from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register(r'children', views.ChildViewSet, basename='child')
router.register(r'events', views.ScheduleEventViewSet, basename='event')

urlpatterns = [
    # CSRF
    path('csrf/', views.get_csrf_token, name='csrf-token'),

    # Auth
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/logout/', views.LogoutView.as_view(), name='logout'),

    # Profile
    path('profile/', views.ProfileView.as_view(), name='profile'),
    path('profile/layout/', views.LayoutView.as_view(), name='profile-layout'),

    # Dashboard sections registry
    path('sections/', views.SectionsView.as_view(), name='sections'),

    # Day Plans
    path('plans/generate/', views.GeneratePlanView.as_view(), name='generate-plan'),
    path('plans/weekly/', views.WeeklyMealsView.as_view(), name='weekly-meals'),
    path('plans/<str:date>/', views.DayPlanDetailView.as_view(), name='day-plan-detail'),
    path('plans/<str:date>/swap-meal/', views.SwapMealView.as_view(), name='swap-meal'),
    path('plans/<str:date>/substitute-meal/', views.SubstituteMealView.as_view(), name='substitute-meal'),
    path('plans/<str:date>/change-meal/', views.ChangeMealView.as_view(), name='change-meal'),

    # Favourite meals
    path('meals/favourites/', views.FavouriteMealListView.as_view(), name='favourite-meals-list'),
    path('meals/favourite/', views.FavouriteMealToggleView.as_view(), name='favourite-meal-toggle'),

    # Chat
    path('chat/', views.ChatConversationListCreateView.as_view(), name='chat-list-create'),
    path('chat/<int:pk>/', views.ChatConversationDetailView.as_view(), name='chat-detail'),
    path('chat/<int:pk>/message/', views.ChatSendMessageView.as_view(), name='chat-send-message'),
    path('chat/messages/<int:message_id>/confirm/', views.ChatMessageConfirmView.as_view(), name='chat-message-confirm'),
    path('chat/messages/<int:message_id>/cancel/', views.ChatMessageCancelView.as_view(), name='chat-message-cancel'),

    # Grocery
    path('grocery/', views.GroceryListView.as_view(), name='grocery-list'),
    path('grocery/current/', views.GroceryCurrentView.as_view(), name='grocery-current'),
    path('grocery/generate/', views.GroceryGenerateView.as_view(), name='grocery-generate'),
    path('grocery/done/', views.GroceryDoneView.as_view(), name='grocery-done'),
    path('grocery/<int:list_id>/items/<int:item_id>/', views.GroceryItemToggleView.as_view(), name='grocery-item-toggle'),
    path('grocery/<int:list_id>/items/<int:item_id>/delete/', views.GroceryItemDeleteView.as_view(), name='grocery-item-delete'),
    path('grocery/<int:list_id>/items/add/', views.GroceryItemAddView.as_view(), name='grocery-item-add'),
    path('grocery/quick-add/', views.GroceryQuickAddView.as_view(), name='grocery-quick-add'),

    # Housework
    path('housework/current/', views.HouseworkCurrentView.as_view(), name='housework-current'),
    path('housework/generate/', views.HouseworkGenerateView.as_view(), name='housework-generate'),
    path('housework/<int:list_id>/tasks/<int:task_id>/', views.HouseworkTaskToggleView.as_view(), name='housework-task-toggle'),
    path('housework/<int:list_id>/tasks/<int:task_id>/delete/', views.HouseworkTaskDeleteView.as_view(), name='housework-task-delete'),
    path('housework/<int:list_id>/tasks/add/', views.HouseworkTaskAddView.as_view(), name='housework-task-add'),
    path('housework/templates/', views.HouseworkTemplateListCreateView.as_view(), name='housework-templates'),
    path('housework/templates/<int:template_id>/', views.HouseworkTemplateUpdateDeleteView.as_view(), name='housework-template-detail'),

    # Custom sections
    path('custom-sections/<str:section_key>/current/', views.CustomSectionCurrentView.as_view(), name='custom-section-current'),
    path('custom-sections/<str:section_key>/generate/', views.CustomSectionGenerateView.as_view(), name='custom-section-generate'),
    path('custom-sections/<str:section_key>/<int:list_id>/tasks/<int:task_id>/', views.CustomSectionTaskToggleView.as_view(), name='custom-section-task-toggle'),
    path('custom-sections/<str:section_key>/<int:list_id>/tasks/<int:task_id>/delete/', views.CustomSectionTaskDeleteView.as_view(), name='custom-section-task-delete'),
    path('custom-sections/<str:section_key>/<int:list_id>/tasks/add/', views.CustomSectionTaskAddView.as_view(), name='custom-section-task-add'),

    # Essentials (new mom)
    path('essentials/current/', views.EssentialsCurrentView.as_view(), name='essentials-current'),
    path('essentials/<int:check_id>/toggle/', views.EssentialsToggleView.as_view(), name='essentials-toggle'),
    path('essentials/add/', views.EssentialsAddView.as_view(), name='essentials-add'),
    path('essentials/<int:check_id>/remove/', views.EssentialsRemoveView.as_view(), name='essentials-remove'),
    path('essentials/<int:check_id>/to-grocery/', views.EssentialsMarkGroceryView.as_view(), name='essentials-to-grocery'),

    # Pantry
    path('pantry/', views.PantryListView.as_view(), name='pantry-list'),
    path('pantry/toggle/', views.PantryToggleView.as_view(), name='pantry-toggle'),

    # Onboarding Agent
    path('onboarding/start/', views.OnboardingStartView.as_view(), name='onboarding-start'),
    path('onboarding/chat/', views.OnboardingChatView.as_view(), name='onboarding-chat'),

    # Reminders
    path('reminders/', views.ReminderListView.as_view(), name='reminder-list'),
    path('reminders/upcoming/', views.ReminderUpcomingView.as_view(), name='reminder-upcoming'),
    path('reminders/<int:pk>/dismiss/', views.ReminderDismissView.as_view(), name='reminder-dismiss'),

    # Kids Activities
    path('kids-activities/generate/', views.GenerateKidsActivitiesView.as_view(), name='kids-activities-generate'),
    path('kids-activities/current/', views.CurrentKidsActivitiesView.as_view(), name='kids-activities-current'),
    path('kids-activities/<int:day_id>/mark-read/', views.KidsActivityMarkReadView.as_view(), name='kids-activities-mark-read'),
    path('kids-activities/<int:day_id>/download/', views.KidsActivityDownloadView.as_view(), name='kids-activities-download'),

    # Router-generated CRUD endpoints
    path('', include(router.urls)),
]
