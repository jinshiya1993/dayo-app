# Dayo — Personal AI Day Planner

## What is Dayo
A personal AI day planner for homemakers, mothers, and professionals. Each user type gets a completely different, personalised dashboard based on their life.

## Tech Stack
- **Backend:** Django 4.2 + Django REST Framework
- **Frontend:** React 19 (Create React App) inside `frontend/`
- **AI:** LangChain + Google Gemini 2.5 Flash (NOT Anthropic/Claude)
- **Database:** SQLite (PostgreSQL later)
- **Auth:** Django session auth

## Project Structure
```
Dayo.app/
├── Dayo_project/          # Django project settings
├── planner/               # Main Django app
│   ├── models.py          # UserProfile, Child, ScheduleEvent, DayPlan, etc.
│   ├── views.py           # All API endpoints
│   ├── urls.py            # URL routing
│   ├── serializers.py     # DRF serializers
│   ├── section_registry.py # Dashboard section definitions + layout builder
│   ├── admin.py
│   └── services/
│       ├── ai_context.py        # Builds AI prompts from user profile
│       ├── plan_generator.py    # Generates day plans via Gemini
│       ├── chat_service.py      # Chat with AI
│       ├── grocery_generator.py # Weekly grocery lists
│       └── profile_builder.py   # Conversational onboarding agent
├── frontend/src/
│   ├── App.js             # Routing + auth check
│   ├── services/api.js    # All API calls
│   ├── pages/             # Full page components
│   │   ├── Dashboard.jsx
│   │   ├── OnboardingPage.jsx      # Step 1: name + user type
│   │   ├── OnboardingChat.jsx      # AI conversation onboarding
│   │   ├── OnboardingPreview.jsx   # Preview + inline "creating plan" overlay before dashboard
│   │   ├── CustomiseDashboard.jsx  # Drag/reorder sections
│   │   ├── ChatPage.jsx
│   │   ├── SchedulePage.jsx
│   │   ├── ProfilePage.jsx
│   │   └── AuthPage.jsx
│   ├── components/
│   │   ├── DynamicDashboard.jsx    # Config-driven dashboard renderer
│   │   ├── HomemakerDashboard.jsx  # (legacy, replaced by DynamicDashboard)
│   │   └── sections/              # 22 reusable dashboard section components
│   └── styles/design.css          # Full design system
├── manage.py
├── requirements.txt
└── .env                   # GEMINI_API_KEY
```

## Key Architecture Decisions

### 3-Layer Dashboard System
1. **Layer 1 — User type defaults:** Pick "Parent" → get meals, kids, grocery, etc.
2. **Layer 2 — AI profile:** Onboarding chat extracts what the user actually needs
3. **Layer 3 — User customisation:** Manual add/remove/reorder sections anytime
Stored in `UserProfile.custom_layout` JSONField.

### User Types
- `parent` — Homemaker with kids
- `new_mom` — New mom with infant
- `working_mom` — Working mother
- `homemaker` — Homemaker without kids
- `professional` — Working professional

### Plan Generation
Each user type gets a different JSON structure from the AI:
- Parent: meals, class_alerts, kids_activities, grocery, housework
- New mom: baby_schedule, mom_rest, mom_meals, recovery_exercise, milestones
- Professional: deep_work, priorities, meetings, meals (compact)

### Onboarding Flow
1. Form: name + user type + city + wake/sleep
2. AI chat: conversational profile building (3-5 exchanges). On completion, city/wake/sleep are saved in the background during the fade-out, then navigates straight to preview — no interstitial loading screen.
3. Preview: show what was built, remove sections with ×, add from the registry list, or add a custom section via the "Add a section" dashed CTA.
4. Confirm → inline "Creating your plan..." overlay runs `plans.generate()` → Dashboard.

## Commands
```bash
# Backend
source venv/bin/activate
python manage.py runserver

# Frontend (separate terminal)
cd frontend && npm start

# Migrations
python manage.py makemigrations planner && python manage.py migrate
```

## API Base
All endpoints under `/api/v1/`

## Design System
- Background: #FAF7F5 (warm off-white)
- Brand: #C2855A (terracotta)
- Text: #1a1a1a
- Border: #EDE8E3
- Cards: white, 14px radius
- Font: Georgia (headings), system-ui (body)
- Max width: 430px centered, mobile first

## Important Notes
- Uses Gemini API key (GEMINI_API_KEY in .env), NOT Anthropic
- Always ask before editing files
- Keep code simple — solo developer
- User type "student" was removed
- The old generic timeline dashboard is replaced by user-type-specific dashboards
- Section components are in `frontend/src/components/sections/`
- `section_registry.py` is the single source of truth for all available sections
