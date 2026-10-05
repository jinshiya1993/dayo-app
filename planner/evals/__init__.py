"""Evaluation harness for Dayo's AI generation.

Answers one question: when Gemini generates a meal plan, does it actually
obey the rules our prompts tell it to obey?

Those rules live in ai_context.py and plan_generator.py as prose aimed at a
model -- "FORBIDDEN INGREDIENTS", "VARIETY is critical", "EVERY meal must
respect health conditions". Prose is not enforceable. This package restates
each rule as a check that runs against real output, so compliance becomes a
number instead of a hope.

Unlike tests/, nothing here asserts an exact value: the output is different
every run. Rules assert *properties* that must hold whatever the model says.

Layout:
  context.py   builds the per-user ctx dict rules receive
  rules.py     the rules + registries (DAY_RULES, WEEK_RULES, GROCERY_RULES)
  profiles.py  golden profiles -- the fixed test households every run uses
  report.py    scorecard aggregation, console render, JSON save, --compare
  reports/     saved run reports (gitignored)

Run it (real Gemini calls, local dev DB only):

  python manage.py run_evals                          # cheap: 2 profiles, 1 repeat
  python manage.py run_evals --profiles all --repeats 3 --grocery
  python manage.py run_evals --compare planner/evals/reports/<old>.json

Reading the scorecard: each rule shows applications passed / total. Output
varies per run, so compliance is a RATE -- run with --repeats 3+ before
trusting a number, and compare rates across prompt versions, not runs.
"""
