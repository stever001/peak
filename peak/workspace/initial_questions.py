"""The initial Peak inventory discovery question pool (Phase 204).

Application configuration, not client data: prompts only, no answers, and nothing about any
client. Loaded only by the explicit ``tools/init_discovery_questions.py``, which inserts each entry
once (keyed by ``seed_key``). After that the questions are ordinary rows: editable and
deactivatable in the app, and never re-imposed from this file.

A ``branch`` names an earlier entry's ``seed_key``, an operator and a value.
"""

from __future__ import annotations

YN = "yes_no"
SHORT = "short_text"
LONG = "long_text"
CHOICE = "single_choice"

INITIAL_QUESTIONS = [
    # Business goals
    {"key": "goal_success", "category": "Business goals", "type": LONG,
     "prompt": "What outcome would make this engagement clearly successful?"},
    {"key": "goal_pain", "category": "Business goals", "type": LONG,
     "prompt": "What inventory problem creates the most business pain today?"},
    {"key": "goal_90_days", "category": "Business goals", "type": LONG,
     "prompt": "What would you most like to improve in the next 90 days?"},
    # Inventory accuracy
    {"key": "acc_confidence", "category": "Inventory accuracy", "type": CHOICE,
     "choices": ["Very confident", "Somewhat confident", "Not confident"],
     "prompt": "How confident are you in current inventory quantities?"},
    {"key": "acc_measured", "category": "Inventory accuracy", "type": YN,
     "prompt": "Is inventory accuracy measured today?"},
    {"key": "acc_how_measured", "category": "Inventory accuracy", "type": LONG,
     "branch": ("acc_measured", "equals", "yes"),
     "prompt": "How is inventory accuracy measured?"},
    {"key": "acc_discrepancy_source", "category": "Inventory accuracy", "type": LONG,
     "prompt": "Where do discrepancies most often originate?"},
    # Receiving
    {"key": "rcv_process", "category": "Receiving", "type": LONG,
     "prompt": "How is inbound inventory received and verified?"},
    {"key": "rcv_delays", "category": "Receiving", "type": LONG,
     "prompt": "What causes receiving delays or errors?"},
    # Putaway
    {"key": "put_directed", "category": "Putaway", "type": YN,
     "prompt": "Is putaway directed to a specific location by a system?"},
    {"key": "put_how_chosen", "category": "Putaway", "type": LONG,
     "branch": ("put_directed", "equals", "no"),
     "prompt": "How do staff decide where to put inventory away?"},
    # Picking / fulfillment
    {"key": "pick_method", "category": "Picking / fulfillment", "type": CHOICE,
     "choices": ["Paper pick lists", "Handheld scanners", "Mixed", "Other"],
     "prompt": "How are orders picked today?"},
    {"key": "pick_errors", "category": "Picking / fulfillment", "type": LONG,
     "prompt": "What are the most common picking or fulfillment errors?"},
    # Cycle counting
    {"key": "cc_performed", "category": "Cycle counting", "type": YN,
     "prompt": "Are cycle counts performed?"},
    {"key": "cc_frequency", "category": "Cycle counting", "type": SHORT,
     "branch": ("cc_performed", "equals", "yes"),
     "prompt": "How frequently are cycle counts performed?"},
    {"key": "cc_blockers", "category": "Cycle counting", "type": LONG,
     "prompt": "What prevents more frequent or reliable cycle counting?"},
    {"key": "cc_why_not", "category": "Cycle counting", "type": LONG,
     "branch": ("cc_performed", "equals", "no"),
     "prompt": "What prevents regular cycle counting from happening at all?"},
    # Stockouts / overstock
    {"key": "stock_outs", "category": "Stockouts / overstock", "type": YN,
     "prompt": "Do stockouts happen on items the system shows as available?"},
    {"key": "stock_outs_example", "category": "Stockouts / overstock", "type": LONG,
     "branch": ("stock_outs", "equals", "yes"),
     "prompt": "Describe a recent stockout and how it was discovered."},
    {"key": "stock_overstock", "category": "Stockouts / overstock", "type": LONG,
     "prompt": "Where does excess or slow-moving inventory build up?"},
    # Systems / visibility
    {"key": "sys_source_of_truth", "category": "Systems / visibility", "type": SHORT,
     "prompt": "Which system is considered the inventory source of truth?"},
    {"key": "sys_workarounds", "category": "Systems / visibility", "type": LONG,
     "prompt": "Where do staff rely on spreadsheets or manual workarounds?"},
    {"key": "sys_trusted", "category": "Systems / visibility", "type": YN,
     "prompt": "Do people trust the system's on-hand quantities enough to act on them?"},
    {"key": "sys_distrust_reason", "category": "Systems / visibility", "type": LONG,
     "branch": ("sys_trusted", "equals", "no"),
     "prompt": "What makes people distrust the system's quantities?"},
    # Labor / workflow
    {"key": "labor_bottleneck", "category": "Labor / workflow", "type": LONG,
     "prompt": "Where do people spend the most time on inventory tasks that feel like rework?"},
    {"key": "labor_training", "category": "Labor / workflow", "type": YN,
     "prompt": "Are inventory procedures documented and trained consistently?"},
    # Management reporting
    {"key": "mgmt_missing_info", "category": "Management reporting", "type": LONG,
     "prompt": "What inventory information do managers wish they had but cannot get reliably today?"},
    {"key": "mgmt_kpis", "category": "Management reporting", "type": YN,
     "prompt": "Are inventory KPIs reviewed on a regular schedule?"},
    {"key": "mgmt_which_kpis", "category": "Management reporting", "type": SHORT,
     "branch": ("mgmt_kpis", "equals", "yes"),
     "prompt": "Which inventory KPIs are reviewed, and how often?"},
]
