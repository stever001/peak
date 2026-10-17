"""The Peak discovery instrument (Phase 216): canonical questions and their rationale catalogue.

Application configuration, not client data. This module is the versioned, in-repo source of the
Peak Method discovery questions:

- **29 core questions** that every interview asks;
- **17 conditional follow-ups**, each shown by the existing deterministic branch (one earlier
  question, ``equals`` / ``not_equals`` a value) only when an answer warrants it;
- for every question, a **12-field rationale**, keyed by the stable question key. It records why
  the question earns its place and how to read the answer. It is source material for a later Peak
  Method training phase; nothing here teaches, tests or certifies;
- for every question, its **source provenance** (``PROVENANCE``, ``SOURCES``): the sources that
  shaped it and what each supports, further reading, and what would trigger a revision. A question
  that is primarily a Peak Method design choice is labelled so; no citation is added to fill a field.

``tools/init_discovery_questions.py`` inserts these questions once each (keyed by ``seed_key``) and
retires the superseded Phase 204 questions by deactivation, never deletion. After that the rows are
ordinary pool rows. Canonical rows (those with a ``seed_key``) can be edited or deactivated only by
an Admin (``peak.workspace.discovery.update_question``). The rationale stays here and is never
written to the database.

**Governing rule (Phase 216).** Question answers may:
- determine which question is displayed next;
- trigger conditional follow-ups;
- trigger evidence requests;
- guide or contextualize consultant observations.

Question answers may not, by themselves, create a finding, become governed evidence, or authorize
a recommendation. A finding is a consultant observation (Phase 206). It may name the question that
prompted it and its basis, and it stays discovery material under Contract C4. The next question is
chosen only by the stored deterministic branch, never by a model.

**Evidence requests** are ordinary single-choice questions answered ``Provided`` /
``Will provide`` / ``Not available``. The answer records the state of a request; it is not the
evidence. Any document obtained is reviewed through the governed evidence path, not here.

A question's ``question`` field is its wording, and ``category`` is the interview section it
appears under. ``branch`` names an earlier entry's key, an operator and a value.
"""

from __future__ import annotations

INSTRUMENT_VERSION = "peak.discovery_instrument.2026-10.v1"

YN = "yes_no"
SHORT = "short_text"
LONG = "long_text"
CHOICE = "single_choice"

#: The answer choices of every evidence-request question.
EVIDENCE_REQUEST_CHOICES = ("Provided", "Will provide", "Not available")

#: The purpose types a question may carry (Phase 216 design, Part B item 3).
PURPOSE_TYPES = ("fact", "symptom", "process description", "evidence request", "control check",
                 "root-cause probe", "desired outcome")

#: Diagnostic classification vocabulary (provisional). A code describes what an observation is
#: about. It is never evidence that a finding exists.
FINDING_CLASSES = {
    "ACC": "Record inaccuracy / unreliable on-hand quantities",
    "CTRL": "Weak transaction control or authorization",
    "PROC": "Undefined or inconsistent process step",
    "LOC": "Location and storage discipline",
    "REPL": "Replenishment and reorder method",
    "FUL": "Picking and fulfillment quality",
    "COND": "Returns, damaged, excess, slow-moving or obsolete stock",
    "DATA": "Item master data quality",
    "SYS": "System-of-record fragmentation, manual handoffs, integration gaps",
    "VIS": "Measurement and management visibility gap",
    "OWN": "Ownership and accountability gap",
    "PEOPLE": "Key-person dependency, undocumented knowledge, training",
    "TRACE": "Lot, serial or expiry traceability",
    "IMPACT": "Business consequence (supports a finding; never stands alone)",
}

#: The 12 rationale fields every catalogue entry defines (Phase 216 design, Part B).
RATIONALE_FIELDS = ("question", "domain", "purpose", "why_it_matters", "healthy_indicators",
                    "risk_indicators", "corroborating_evidence", "follow_up_triggers",
                    "finding_classes", "cannot_support", "novice_mistakes",
                    "recommendation_relevance")

NONE_APPLICABLE = "None applicable."

CTX = "Context and goals"
REL = "Record reliability"
RCV = "Receiving and storage"
FUL = "Replenishment and fulfillment"
CNT = "Counting and adjustments"
RTN = "Returns and stock condition"
SYS = "Systems and data"
PPL = "People and accountability"
KPI = "Management measures"
CLS = "Close"


def _q(key, category, answer_type, question, *, domain, purpose, why, healthy, risky, evidence,
       triggers, classes, cannot, mistakes, relevance, choices=None, branch=None, core=True):
    return {
        "key": key, "category": category, "type": answer_type, "question": question,
        "choices": list(choices) if choices else None, "branch": branch, "core": core,
        "rationale": {
            "question": question, "domain": domain, "purpose": list(purpose),
            "why_it_matters": why, "healthy_indicators": healthy, "risk_indicators": risky,
            "corroborating_evidence": evidence, "follow_up_triggers": triggers,
            "finding_classes": list(classes), "cannot_support": cannot,
            "novice_mistakes": mistakes, "recommendation_relevance": relevance,
        },
    }


def _evidence(key, category, request, parent, operator, value, *, domain, why, classes, cannot,
              mistakes, relevance):
    """A follow-up that records the state of one evidence request."""
    return _q(
        key, category, CHOICE, f"Evidence request: {request}",
        choices=EVIDENCE_REQUEST_CHOICES, branch=(parent, operator, value), core=False,
        domain=domain, purpose=("evidence request",), why=why,
        healthy="Provided, and consistent with the interview answers.",
        risky="Not available where the client said the record exists; or it contradicts the "
              "interview answers.",
        evidence="This question is the evidence request; the material itself is reviewed through "
                 "the governed evidence path.",
        triggers=NONE_APPLICABLE, classes=classes, cannot=cannot, mistakes=mistakes,
        relevance=relevance)


QUESTIONS = [
    # ---------------------------------------------------------------- Context and goals
    _q("ctx_operation", CTX, LONG,
       "Briefly describe the operation: what you stock, roughly how many active SKUs, how many "
       "buildings or stocking locations, and typical daily order and receipt volume.",
       domain="Operating context", purpose=("fact",),
       why="Sizes every later answer: 5% error on 300 SKUs and on 30,000 SKUs are different "
           "problems, and recommendations must fit the scale.",
       healthy="Knows the figures within a range.",
       risky="Cannot estimate the SKU count; locations unknown; 'it varies' with no range.",
       evidence="Item master count and order count from the system.",
       triggers=NONE_APPLICABLE, classes=(),
       cannot="Any finding by itself; it scales ACC, REPL, FUL and IMPACT.",
       mistakes="Spending ten minutes here; treating owner estimates as data.",
       relevance="High: sets the scale of tools and process recommended."),
    _q("ctx_traceability", CTX, YN,
       "Do any items require lot, serial number or expiry-date tracking — by regulation, customer "
       "requirement or shelf life?",
       domain="Traceability", purpose=("fact",),
       why="Traceability failure is a distinct, high-consequence risk (recall, regulatory, "
           "spoilage).",
       healthy="No; or yes with tracking described in the follow-up.",
       risky="'Yes, but we track it on paper' or 'we're supposed to'.",
       evidence="A trace of one lot or serial (follow-up).",
       triggers="Yes opens trace_how and trace_evidence.", classes=("TRACE",),
       cannot="Compliance conclusions; Peak does not certify compliance.",
       mistakes="Assuming 'we have lot numbers' means 'we can trace'.",
       relevance="High when yes."),
    _q("trace_how", CTX, LONG,
       "How are lot, serial or expiry captured at receiving, storage and shipping — and could you "
       "trace one lot to the customers who received it today?",
       branch=("ctx_traceability", "equals", "yes"), core=False,
       domain="Traceability", purpose=("process description", "control check"),
       why="Shows where in the flow traceability is captured or lost.",
       healthy="Captured at receipt and shipment in the system; a trace is quick.",
       risky="Captured only at receipt; recorded on paper; a trace takes days or is impossible.",
       evidence="The trace requested in trace_evidence.",
       triggers=NONE_APPLICABLE, classes=("TRACE", "CTRL", "SYS"),
       cannot="That a trace would succeed, without performing one.",
       mistakes="Accepting 'yes we could' without asking how long it takes.",
       relevance="High for regulated or perishable goods."),
    _evidence("trace_evidence", CTX, "a trace of one recent lot or serial from receipt to "
              "shipment.", "ctx_traceability", "equals", "yes",
              domain="Traceability",
              why="A demonstrated trace is the only reliable test of traceability.",
              classes=("TRACE",), cannot="Regulatory compliance.",
              mistakes="Letting the client choose an easy, recent lot only.",
              relevance="High for regulated or perishable goods."),
    _q("goal_pain_incident", CTX, LONG,
       "What inventory problem is causing the business the most trouble right now? Walk me "
       "through the most recent time it happened.",
       domain="Root causes and recurring pain points", purpose=("symptom",),
       why="Anchors the engagement in a real, recent incident rather than a general complaint, "
           "and tells the consultant where to probe deepest.",
       healthy="A specific, recent incident with a sequence of events.",
       risky="Vague ('everything's a mess'); blame only; only years-old incidents.",
       evidence="The incident's transactions or documents.",
       triggers=NONE_APPLICABLE, classes=("IMPACT",),
       cannot="A root cause: the client's diagnosis is a hypothesis, not a finding.",
       mistakes="Accepting the client's stated cause; solving the incident instead of the "
                "pattern.",
       relevance="High: often the first-priority recommendation area."),
    _q("goal_impact", CTX, LONG,
       "What does that problem cost — lost or late sales, expedited freight, write-offs, "
       "overtime, customer credits? A rough range is fine. How do you know?",
       domain="Business impact", purpose=("symptom",),
       why="Prioritization and economically justified recommendations need an order of "
           "magnitude.",
       healthy="A range with a source ('about $40k of credits last year, from the credit memo "
               "report').",
       risky="'A lot'; a single unsourced figure; refusal.",
       evidence="Credit memos, freight invoices, write-off journal entries.",
       triggers=NONE_APPLICABLE, classes=("IMPACT",),
       cannot="A quantified claim in the report without corroboration; a testimony figure is "
              "labelled as the client's estimate.",
       mistakes="Turning a guess into a reported number; skipping the question because it feels "
                "awkward.",
       relevance="High: justifies effort and priority."),
    _q("goal_north_star", CTX, LONG,
       "Twelve months from now, if this work succeeded, what would be different? What could you "
       "do that you can't do today?",
       domain="Future state / North Star", purpose=("desired outcome",),
       why="The input to the engagement North Star.",
       healthy="Observable outcomes ('promise ship dates from the system without walking the "
               "floor').",
       risky="Solution-shaped ('a new WMS'); activity with no outcome.",
       evidence=NONE_APPLICABLE, triggers=NONE_APPLICABLE, classes=(),
       cannot="That the solution named is the right one.",
       mistakes="Recording the requested tool as the goal; not carrying the answer into the "
                "North Star field.",
       relevance="High: recommendations are checked against it."),
    # ---------------------------------------------------------------- Record reliability
    _q("acc_check_before_promise", REL, CHOICE,
       "When the system shows an item on hand, how often does someone physically check before "
       "promising it to a customer?",
       choices=("Rarely", "Sometimes", "Usually or always"),
       domain="Inventory accuracy and record reliability", purpose=("symptom",),
       why="Behavior reveals trust in the record better than asking how confident people are.",
       healthy="Rarely.",
       risky="Usually or always: the system is not functioning as the record.",
       evidence="Observation of how orders are promised.",
       triggers="Anything but Rarely opens acc_distrust_reason.", classes=("ACC", "SYS"),
       cannot="An accuracy percentage.",
       mistakes="Treating 'Rarely' as proof of accuracy; people may simply not check.",
       relevance="Medium–high."),
    _q("acc_distrust_reason", REL, LONG,
       "What makes people double-check — which items, areas or transactions are least trusted?",
       branch=("acc_check_before_promise", "not_equals", "Rarely"), core=False,
       domain="Inventory accuracy and record reliability", purpose=("root-cause probe",),
       why="Locates the distrust, which usually points at the transaction or area causing error.",
       healthy="A narrow, specific answer (one zone, one item family).",
       risky="'All of it'; distrust tied to receiving, returns or a system sync.",
       evidence="Transaction history for the items named.",
       triggers=NONE_APPLICABLE, classes=("ACC", "PROC", "SYS"),
       cannot="The actual cause; it locates where to look.",
       mistakes="Recording the client's theory as the cause.",
       relevance="High: directs where counts and fixes start."),
    _q("acc_phantom", REL, YN,
       "In the last three months, has an order come up short, or a stockout been found, on an "
       "item the system showed as available?",
       domain="Inventory accuracy; stockouts", purpose=("symptom",),
       why="Phantom inventory is the most direct operational symptom of record error.",
       healthy="No, and credible given the other answers.",
       risky="Yes, especially 'regularly'.",
       evidence="The item's transaction history around the event (follow-up).",
       triggers="Yes opens acc_phantom_example and acc_phantom_evidence.",
       classes=("ACC", "FUL", "IMPACT"),
       cannot="A frequency or rate.",
       mistakes="Stopping at 'yes' without getting the example.",
       relevance="High."),
    _q("acc_phantom_example", REL, LONG,
       "Describe the most recent one: the item, how it was discovered, what the system said versus "
       "what was there, and what it cost.",
       branch=("acc_phantom", "equals", "yes"), core=False,
       domain="Inventory accuracy; stockouts", purpose=("symptom",),
       why="One concrete case gives a transaction trail to test and an impact to size.",
       healthy="A specific item and date the consultant can look up.",
       risky="Cannot name one despite saying yes; discovered by a customer.",
       evidence="Transaction history (acc_phantom_evidence).",
       triggers=NONE_APPLICABLE, classes=("ACC", "IMPACT"),
       cannot="A pattern from one case.",
       mistakes="Generalizing from a single incident.",
       relevance="High."),
    _evidence("acc_phantom_evidence", REL, "transaction history for that item around the event.",
              "acc_phantom", "equals", "yes",
              domain="Inventory accuracy; stockouts",
              why="The history shows which transaction created the gap: receipt, pick, adjustment "
                  "or sync.",
              classes=("ACC", "CTRL"), cannot="A cause across other items.",
              mistakes="Reading the history without the physical context.",
              relevance="High."),
    _q("acc_how_known", REL, CHOICE,
       "How do you know how accurate your inventory records are?",
       choices=("We measure it regularly from counts", "We see it at physical inventory",
                "We don't measure it"),
       domain="Inventory accuracy; metrics", purpose=("control check",),
       why="An unmeasured accuracy claim is a visibility finding in itself, and the answer shows "
           "which evidence exists.",
       healthy="Measured regularly, with the method known.",
       risky="Not measured, alongside high stated confidence.",
       evidence="The latest count results (follow-up).",
       triggers="'Regularly' opens acc_results_evidence; 'physical inventory' opens "
                "acc_physical_variance.",
       classes=("VIS", "ACC"),
       cannot="That a measured figure is computed correctly (units versus value, net versus "
              "absolute).",
       mistakes="Accepting '98% accurate' without asking how it is calculated: net value variance "
                "hides large offsetting errors.",
       relevance="High."),
    _evidence("acc_results_evidence", REL, "the latest accuracy results, and how they are "
              "calculated (units or value; net or absolute).",
              "acc_how_known", "equals", "We measure it regularly from counts",
              domain="Inventory accuracy; metrics",
              why="The calculation method decides whether the figure means anything.",
              classes=("ACC", "VIS"), cannot="Accuracy outside the counted sample.",
              mistakes="Accepting a net-value figure as item-level accuracy.",
              relevance="High."),
    _q("acc_physical_variance", REL, LONG,
       "What did the last physical inventory find — total variance in units or value — and what "
       "happened to it? Can you share the reconciliation?",
       branch=("acc_how_known", "equals", "We see it at physical inventory"), core=False,
       domain="Physical inventory; adjustments", purpose=("fact", "evidence request"),
       why="The physical inventory variance is the business's own measure of record error.",
       healthy="Known variance, investigated, booked with a reconciliation.",
       risky="Unknown; large variance written off without investigation.",
       evidence="The physical inventory reconciliation.",
       triggers=NONE_APPLICABLE, classes=("ACC", "CTRL", "IMPACT"),
       cannot="Current accuracy: the figure is a point in time.",
       mistakes="Reading a small net variance as good accuracy.",
       relevance="High."),
    _q("acc_discrepancy_cause", REL, LONG,
       "When the record turns out to be wrong, how does the difference usually get explained — "
       "and is the cause ever traced back to the transaction that caused it?",
       domain="Adjustments and exception handling; root causes", purpose=("root-cause probe",),
       why="Shows whether variances are investigated (a learning system) or simply overwritten.",
       healthy="Variances researched against recent transactions, with the cause recorded.",
       risky="'We just fix the number'; blame without investigation.",
       evidence="Adjustment reason codes in the adjustment history.",
       triggers=NONE_APPLICABLE, classes=("CTRL", "PROC", "ACC"),
       cannot="The actual root cause: the client's explanation is testimony.",
       mistakes="Reporting the client's theory ('it's receiving') as the cause.",
       relevance="High."),
    # ---------------------------------------------------------------- Receiving and storage
    _q("rcv_walkthrough", RCV, LONG,
       "Walk me through receiving: how is a delivery checked against what was ordered, and at "
       "what point does the system show it as available?",
       domain="Receiving", purpose=("process description",),
       why="Receiving is where many record errors start: unverified quantities and a delay "
           "between physical and system receipt.",
       healthy="Counted against the PO (ideally blind); system updated at receipt; putaway "
               "recorded.",
       risky="Packing slip trusted; keyed in batches hours or days later; available before "
             "putaway.",
       evidence="Observe a receipt; compare receipt timestamps with deliveries.",
       triggers=NONE_APPLICABLE, classes=("PROC", "CTRL", "ACC"),
       cannot="An error rate.",
       mistakes="Recording the documented process instead of the observed one.",
       relevance="High."),
    _q("rcv_exceptions", RCV, LONG,
       "What happens when a delivery doesn't match the order — short, over, wrong item or "
       "damaged? Who decides, and how is it recorded?",
       domain="Receiving; exception handling", purpose=("process description", "control check"),
       why="Exception handling exposes control gaps and leakage of vendor credits.",
       healthy="A defined discrepancy step, recorded and fed back to purchasing or the vendor.",
       risky="Absorbed silently; whoever is there decides; no record.",
       evidence="Receiving discrepancy log; vendor credits.",
       triggers=NONE_APPLICABLE, classes=("CTRL", "PROC", "IMPACT"),
       cannot="Vendor performance conclusions.",
       mistakes="Missing that 'we just accept it' is a control finding.",
       relevance="Medium–high."),
    _q("loc_recorded", RCV, CHOICE,
       "Does every item have a recorded storage location that staff actually use to find it?",
       choices=("Yes, every item", "Some items or areas", "No — people know where things are"),
       domain="Putaway; storage and location discipline", purpose=("control check",),
       why="Location discipline underlies picking speed, counting and new-hire productivity; "
           "for a small business it matters more than system-directed putaway.",
       healthy="Yes, with locations held in the system.",
       risky="'People know'; overflow areas with no location.",
       evidence="A floor walk sampling items against recorded locations.",
       triggers="Anything but 'Yes, every item' opens loc_how_found.",
       classes=("LOC", "PEOPLE"),
       cannot="That the recorded locations are correct; sample them.",
       mistakes="Accepting 'yes' without a floor check.",
       relevance="High."),
    _q("loc_how_found", RCV, LONG,
       "How do staff decide where to put items and find them later? Where does overflow go?",
       branch=("loc_recorded", "not_equals", "Yes, every item"), core=False,
       domain="Putaway; storage and location discipline", purpose=("process description",),
       why="Shows how much of the operation depends on memory rather than a record.",
       healthy="A simple, consistent rule (fixed zones by family).",
       risky="Memory only; overflow stacked wherever space exists.",
       evidence="Observe putaway; floor walk.",
       triggers=NONE_APPLICABLE, classes=("LOC", "PEOPLE", "PROC"),
       cannot="Search-time or labor figures.",
       mistakes="Recommending a WMS before simple location labels.",
       relevance="High."),
    # ---------------------------------------------------------------- Replenishment and fulfillment
    _q("repl_trigger", FUL, LONG,
       "How do you decide when and how much to reorder, and when to refill pick locations? Who "
       "makes that call?",
       domain="Replenishment; ownership", purpose=("process description",),
       why="Exposes gut-feel ordering, missing min/max levels and single-person dependency: root "
           "drivers of both stockouts and excess.",
       healthy="Defined reorder points or min/max, reviewed periodically, with a named owner.",
       risky="'When we notice we're low'; one buyer's memory.",
       evidence="Reorder settings for a sample of items.",
       triggers=NONE_APPLICABLE, classes=("REPL", "OWN", "PEOPLE"),
       cannot="That the reorder parameters are right; that is an analytical task.",
       mistakes="Recommending a forecasting tool when the underlying problem is record accuracy.",
       relevance="High."),
    _q("pick_method_confirm", FUL, CHOICE,
       "How are orders picked and confirmed?",
       choices=("Paper pick lists", "Scanned with handhelds", "Mixed", "Other"),
       domain="Picking and fulfillment", purpose=("fact",),
       why="Pick confirmation decides both the error rate and whether the record updates at pick.",
       healthy="Scan-confirmed picks.",
       risky="Paper with no confirmation step.",
       evidence="Observe picking.",
       triggers="'Paper pick lists' opens pick_confirmation.", classes=("FUL", "PROC"),
       cannot="An error rate.",
       mistakes="Jumping to 'buy scanners'.",
       relevance="Medium."),
    _q("pick_confirmation", FUL, LONG,
       "How is a pick confirmed as correct before it ships, and when does the system record it?",
       branch=("pick_method_confirm", "equals", "Paper pick lists"), core=False,
       domain="Picking and fulfillment; controls", purpose=("control check",),
       why="On paper, the confirmation step is the only error control, and system timing "
           "affects accuracy.",
       healthy="A second check (weight, count, pack verification); same-day system update.",
       risky="No check; picks keyed in later from paper.",
       evidence="Observe pack-out.",
       triggers=NONE_APPLICABLE, classes=("FUL", "CTRL", "ACC"),
       cannot="An error rate.",
       mistakes="Assuming paper means error-prone; a well-run paper check can be adequate.",
       relevance="Medium–high."),
    _q("pick_error_detection", FUL, CHOICE,
       "How are picking or shipping errors usually discovered?",
       choices=("We catch them before shipping", "Customers report them",
                "We don't really know"),
       domain="Picking and fulfillment; metrics", purpose=("symptom",),
       why="The detection channel is diagnostic: customer-detected errors carry cost and "
           "reputational impact, and 'don't know' is a visibility gap.",
       healthy="Caught internally, at a check step.",
       risky="Customer-detected, or unknown.",
       evidence="Credit and return records for wrong-item reasons.",
       triggers="'Customers report them' opens pick_error_volume.",
       classes=("FUL", "VIS", "IMPACT"),
       cannot="An error rate.",
       mistakes="Recording 'not many' as a rate.",
       relevance="High."),
    _q("pick_error_volume", FUL, LONG,
       "Roughly how many wrong or short shipments are reported in a month, and is there a record "
       "of them (credits, returns)?",
       branch=("pick_error_detection", "equals", "Customers report them"), core=False,
       domain="Picking and fulfillment; business impact", purpose=("symptom", "evidence request"),
       why="Sizes customer-facing error cost and locates the record that can corroborate it.",
       healthy="A known figure from a record.",
       risky="Unknown volume; no record kept.",
       evidence="Credit memo or return reason report.",
       triggers=NONE_APPLICABLE, classes=("FUL", "IMPACT", "VIS"),
       cannot="A rate without the order volume (ctx_operation).",
       mistakes="Reporting the estimate as measured.",
       relevance="High."),
    # ---------------------------------------------------------------- Counting and adjustments
    _q("count_method", CNT, CHOICE,
       "How are inventory counts done today?",
       choices=("Regular cycle counts", "Periodic physical inventory only", "Both",
                "No regular counting"),
       domain="Cycle counting and physical inventory", purpose=("fact",),
       why="Counting is the main accuracy control.",
       healthy="Cycle counts, prioritized by value or velocity.",
       risky="None, or an annual physical inventory only.",
       evidence="Count sheets or count history.",
       triggers="Anything but 'No regular counting' opens count_program; 'No regular counting' "
                "opens count_why_not.",
       classes=("CTRL", "ACC", "VIS"),
       cannot="Count quality.",
       mistakes="Treating 'we count' as 'we count well'.",
       relevance="High."),
    _q("count_program", CNT, LONG,
       "Describe how counts work: what's counted and how often, who counts, whether counters see "
       "the expected quantity, and what happens when a count doesn't match.",
       branch=("count_method", "not_equals", "No regular counting"), core=False,
       domain="Cycle counting; controls", purpose=("process description", "control check"),
       why="Count design decides whether counts catch error: blind counts, recounts and variance "
           "research.",
       healthy="Blind counts, a recount before adjusting, variances researched.",
       risky="Counters see the expected quantity; the counter adjusts directly; no research.",
       evidence="Count history and adjustment history.",
       triggers=NONE_APPLICABLE, classes=("CTRL", "PROC", "ACC"),
       cannot="Count accuracy.",
       mistakes="Missing that non-blind counts confirm the record instead of testing it.",
       relevance="High."),
    _q("count_why_not", CNT, LONG,
       "What has prevented regular counting?",
       branch=("count_method", "equals", "No regular counting"), core=False,
       domain="Cycle counting; staffing", purpose=("root-cause probe",),
       why="The blocker (time, staff, system, belief it isn't needed) shapes the recommendation.",
       healthy="A specific, solvable blocker.",
       risky="'Never needed it' alongside other accuracy symptoms.",
       evidence=NONE_APPLICABLE, triggers=NONE_APPLICABLE, classes=("CTRL", "PEOPLE", "OWN"),
       cannot="That counting alone would fix accuracy.",
       mistakes="Prescribing a full cycle-count program for a team with no capacity.",
       relevance="High."),
    _q("adj_control", CNT, LONG,
       "Who can change on-hand quantities in the system, and what has to happen before an "
       "adjustment is posted — a reason, a review, an approval?",
       domain="Controls and authorization; adjustments", purpose=("control check",),
       why="Unrestricted adjustment rights hide error and loss; separating counting from adjusting "
           "is a core inventory control.",
       healthy="A limited set of users, mandatory reason codes, review above a threshold.",
       risky="Anyone can adjust; the counter adjusts their own counts; no reasons.",
       evidence="User permission list; adjustment history.",
       triggers=NONE_APPLICABLE, classes=("CTRL", "OWN"),
       cannot="A finding of loss or theft; Peak does not make that allegation.",
       mistakes="Implying wrongdoing; skipping the question because it feels sensitive.",
       relevance="High."),
    _q("adj_reviewed", CNT, YN,
       "Does someone other than the person who posted them regularly review inventory "
       "adjustments — by value or by reason?",
       domain="Controls and authorization; adjustments", purpose=("control check",),
       why="Independent review is the compensating control in a small team where full "
           "segregation may be impossible.",
       healthy="Yes, with the review evidenced.",
       risky="No.",
       evidence="The review itself, or the raw adjustment history (follow-ups).",
       triggers="No opens adj_history_evidence; yes opens adj_review_evidence.",
       classes=("CTRL", "VIS"),
       cannot="That the review is effective.",
       mistakes="Accepting 'the owner looks at it' without an example.",
       relevance="High."),
    _evidence("adj_history_evidence", CNT, "adjustment history for the last 90 days: item, "
              "quantity, value, reason and user.", "adj_reviewed", "equals", "no",
              domain="Controls and authorization; adjustments",
              why="With no independent review, the history is the only way to see what is being "
                  "adjusted and by whom.",
              classes=("CTRL", "ACC", "IMPACT"), cannot="Intent behind any adjustment.",
              mistakes="Drawing conclusions about individuals.",
              relevance="High."),
    _evidence("adj_review_evidence", CNT, "an example of the most recent adjustment review.",
              "adj_reviewed", "equals", "yes",
              domain="Controls and authorization; adjustments",
              why="Shows whether the stated review happens and what it looks at.",
              classes=("CTRL", "VIS"), cannot="Review effectiveness over time.",
              mistakes="Accepting a report nobody signs or acts on as a review.",
              relevance="Medium–high."),
    # ---------------------------------------------------------------- Returns and stock condition
    _q("rtn_damaged", RTN, LONG,
       "What happens to returned, damaged or unsellable items — where do they go physically, how "
       "are they recorded, and who decides whether they're restocked, repaired or written off?",
       domain="Returns; damaged stock", purpose=("process description", "control check"),
       why="Returns and damaged stock are a common source of sellable-looking phantom stock and "
           "unrecorded loss.",
       healthy="A quarantine location, an inspect-then-disposition step, a system status that "
               "reflects it.",
       risky="Returns go straight back to the shelf uninspected; damaged items sit counted as "
             "available.",
       evidence="A floor walk of the returns and damaged area against the system.",
       triggers=NONE_APPLICABLE, classes=("COND", "CTRL", "ACC"),
       cannot="A write-off value.",
       mistakes="Treating returns as a customer-service topic only.",
       relevance="Medium–high."),
    _q("excess_obsolete", RTN, LONG,
       "Where does excess, slow-moving or obsolete stock build up, and when was any of it last "
       "written down, sold off or cleared out?",
       domain="Excess, slow-moving and obsolete inventory", purpose=("symptom",),
       why="It ties up cash and space and distorts counts; the last write-down shows whether "
           "anyone owns stock aging.",
       healthy="A periodic aging review and a disposition practice.",
       risky="'Never written anything off'; aisles of dead stock kept 'just in case'.",
       evidence="An aging or no-movement report.",
       triggers=NONE_APPLICABLE, classes=("COND", "OWN", "IMPACT"),
       cannot="A valuation or reserve conclusion; that is an accounting judgement.",
       mistakes="Stating carrying cost as fact.",
       relevance="Medium."),
    # ---------------------------------------------------------------- Systems and data
    _q("sys_record", SYS, LONG,
       "Which systems hold inventory quantities — ERP, WMS, e-commerce, accounting, spreadsheets "
       "— and which one wins when they disagree?",
       domain="ERP/WMS/spreadsheets and system-of-record behavior", purpose=("fact",),
       why="Establishes the system of record, or shows there isn't one.",
       healthy="One system of record; the others fed from it.",
       risky="Several systems hold quantities; 'it depends'; a spreadsheet wins.",
       evidence="A screen comparison of one item across systems.",
       triggers=NONE_APPLICABLE, classes=("SYS",),
       cannot="An integration defect diagnosis.",
       mistakes="Recommending a system replacement from this answer.",
       relevance="High."),
    _q("sys_handoffs", SYS, LONG,
       "Where is inventory information re-keyed, exported, or reconciled by hand — between "
       "systems, or onto paper, whiteboards or spreadsheets?",
       domain="Integrations and manual handoffs", purpose=("process description",),
       why="Manual handoffs are both error sources and labor cost.",
       healthy="Few handoffs, each with a check.",
       risky="Daily re-keying; a shadow spreadsheet that is the real record.",
       evidence="A sample spreadsheet; observe the handoff.",
       triggers=NONE_APPLICABLE, classes=("SYS", "PROC", "PEOPLE"),
       cannot="Error rates.",
       mistakes="Treating every spreadsheet as a problem; some are fine.",
       relevance="High."),
    _q("item_master", SYS, LONG,
       "How are new items set up, and how often do problems come from item data — duplicate "
       "SKUs, wrong units of measure, missing barcodes or wrong costs?",
       domain="Item and master data", purpose=("process description", "symptom"),
       why="Master-data errors, unit-of-measure errors especially, silently corrupt quantities.",
       healthy="Controlled setup with an owner and required fields.",
       risky="Anyone creates items; unit-of-measure conversions known to be wrong.",
       evidence="An item master extract (duplicates, blank fields).",
       triggers=NONE_APPLICABLE, classes=("DATA", "CTRL", "OWN"),
       cannot="A data-quality percentage without the extract.",
       mistakes="Overlooking unit of measure.",
       relevance="Medium–high."),
    # ---------------------------------------------------------------- People and accountability
    _q("own_accuracy", PPL, LONG,
       "Who is accountable for inventory accuracy, and what happens when it's off?",
       domain="Ownership and accountability", purpose=("control check",),
       why="Without an owner every fix is temporary.",
       healthy="A named owner with a routine or consequence for misses.",
       risky="'Everyone'; 'no one'; an owner without authority.",
       evidence="Consistency of the answer across interviews.",
       triggers=NONE_APPLICABLE, classes=("OWN",),
       cannot="A performance judgement about a person.",
       mistakes="Naming individuals in findings.",
       relevance="High."),
    _q("people_dependency", PPL, LONG,
       "If your most experienced warehouse person were out for two weeks, what would go wrong?",
       domain="Staffing and process knowledge", purpose=("root-cause probe",),
       why="Exposes undocumented knowledge and training gaps better than asking whether "
           "procedures are documented.",
       healthy="'Not much — it's written down and others are cross-trained.'",
       risky="A list of things only that person knows.",
       evidence="Existing written procedures.",
       triggers=NONE_APPLICABLE, classes=("PEOPLE", "PROC"),
       cannot="Individual performance conclusions.",
       mistakes="Framing the question as criticism of that person.",
       relevance="Medium–high."),
    _q("labor_rework", PPL, LONG,
       "Where does the team lose time searching for stock, re-counting, or fixing inventory "
       "problems?",
       domain="Staffing; recurring pain points", purpose=("symptom",),
       why="Surfaces hidden labor cost and points to the process causing it.",
       healthy="Little rework, with known causes.",
       risky="Daily searching; recurring recounts.",
       evidence="Observation; overtime records.",
       triggers=NONE_APPLICABLE, classes=("PROC", "LOC", "IMPACT"),
       cannot="A labor-savings figure.",
       mistakes="Promising labor savings.",
       relevance="Medium."),
    # ---------------------------------------------------------------- Management measures
    _q("kpi_reviewed", KPI, YN,
       "Are inventory measures — accuracy, fill rate, turns, adjustments, aging — reviewed on a "
       "regular schedule?",
       domain="Metrics and KPIs", purpose=("control check",),
       why="Shows whether management can see problems early, and which data exists.",
       healthy="Yes, with a rhythm and actions taken.",
       risky="No; or reports nobody acts on.",
       evidence="The latest report (follow-up).",
       triggers="Yes opens kpi_which and kpi_report_evidence; no opens kpi_missing.",
       classes=("VIS", "OWN"),
       cannot="That the measures are computed correctly.",
       mistakes="Collecting KPI names instead of asking what action followed.",
       relevance="Medium–high."),
    _q("kpi_which", KPI, LONG,
       "Which measures, how often, who reviews them — and what action followed the last bad "
       "result?",
       branch=("kpi_reviewed", "equals", "yes"), core=False,
       domain="Metrics and KPIs", purpose=("control check",),
       why="A measure matters only if someone acts on it.",
       healthy="A named reviewer and a concrete action taken.",
       risky="Measures listed but no action ever follows.",
       evidence="The report (kpi_report_evidence).",
       triggers=NONE_APPLICABLE, classes=("VIS", "OWN"),
       cannot="Measure correctness.",
       mistakes="Counting KPIs as maturity.",
       relevance="Medium."),
    _evidence("kpi_report_evidence", KPI, "the most recent inventory report reviewed by "
              "management.", "kpi_reviewed", "equals", "yes",
              domain="Metrics and KPIs",
              why="Shows what management actually sees and how it is calculated.",
              classes=("VIS",), cannot="That management acts on it.",
              mistakes="Taking the report's figures as correct without checking the method.",
              relevance="Medium."),
    _q("kpi_missing", KPI, LONG,
       "What would you most want to see each week that you can't get reliably today?",
       branch=("kpi_reviewed", "equals", "no"), core=False,
       domain="Metrics and KPIs; future state", purpose=("desired outcome",),
       why="Defines the first useful measure to establish.",
       healthy="A specific measure tied to a decision.",
       risky="'Everything'; no decision attached.",
       evidence=NONE_APPLICABLE, triggers=NONE_APPLICABLE, classes=("VIS",),
       cannot="That the data exists to produce it.",
       mistakes="Designing a dashboard before the record is reliable.",
       relevance="Medium."),
    # ---------------------------------------------------------------- Close
    _q("prior_attempts", CLS, LONG,
       "Of everything we've discussed, what keeps coming back no matter what you try — and what "
       "has already been tried?",
       domain="Root causes and recurring pain points", purpose=("root-cause probe",),
       why="Identifies chronic issues and stops Peak recommending a fix that already failed "
           "without explaining why it would work this time.",
       healthy="A clear history of attempts and why they failed.",
       risky="Repeated failed fixes; initiative fatigue.",
       evidence=NONE_APPLICABLE, triggers=NONE_APPLICABLE, classes=(),
       cannot="Why the attempts failed; that is the consultant's analysis.",
       mistakes="Recommending the thing that already failed.",
       relevance="High."),
    _q("constraints", CLS, LONG,
       "What should our recommendations respect — budget, systems you're committed to, staffing, "
       "peak seasons, or changes already planned (new system, move, growth)?",
       domain="Future state; recommendation constraints", purpose=("fact",),
       why="Keeps recommendations implementable, which matters for small-business economics.",
       healthy="Clear constraints.",
       risky="A planned system change that makes process fixes short-lived or urgent.",
       evidence=NONE_APPLICABLE, triggers=NONE_APPLICABLE, classes=(),
       cannot="Any finding.",
       mistakes="Ignoring a planned ERP change.",
       relevance="High."),
]

#: Stable key -> catalogue entry.
BY_KEY = {q["key"]: q for q in QUESTIONS}

CORE_KEYS = tuple(q["key"] for q in QUESTIONS if q["core"])
FOLLOW_UP_KEYS = tuple(q["key"] for q in QUESTIONS if not q["core"])

#: The Phase 204 seed keys this instrument supersedes. They are retired by deactivation only:
#: their rows, and every answer given to them (with its prompt snapshot), are kept.
SUPERSEDED_PHASE204_KEYS = (
    "goal_success", "goal_pain", "goal_90_days", "acc_confidence", "acc_measured",
    "acc_how_measured", "acc_discrepancy_source", "rcv_process", "rcv_delays", "put_directed",
    "put_how_chosen", "pick_method", "pick_errors", "cc_performed", "cc_frequency",
    "cc_blockers", "cc_why_not", "stock_outs", "stock_outs_example", "stock_overstock",
    "sys_source_of_truth", "sys_workarounds", "sys_trusted", "sys_distrust_reason",
    "labor_bottleneck", "labor_training", "mgmt_missing_info", "mgmt_kpis", "mgmt_which_kpis",
)


def rationale(key: str):
    """The 12-field rationale for a canonical question key, or ``None`` for any other key."""
    entry = BY_KEY.get(key)
    return dict(entry["rationale"]) if entry else None


# --------------------------------------------------------------------------- source provenance
#
# Where each question comes from (Phase 216). Sources are used selectively: a question cites an
# external source only where the source materially shaped it, and a question that is primarily a
# Peak Method design choice says so (source ``peak_method_design``). Every external source was checked
# to exist, and its author, title and edition confirmed, on ``SOURCES_VERIFIED_ON``; a role a source
# could not support was removed. No page numbers are given: training material that quotes a source
# adds them from the copy used. Nothing here is fetched or checked at run time.

#: What a source can support for a question.
SOURCE_SUPPORTS = ("inclusion", "wording", "interpretation", "evidence", "follow_up")

#: Provenance kinds. ``peak_field_observation`` is the internal empirical source: a consultant-added
#: (supplemental) question from a prior engagement that an Admin later reviewed for the canonical
#: pool. It is cited by that label only, never with client-identifying information.
SOURCE_KINDS = ("standard", "regulation", "book", "research", "benchmark", "peak_method_design",
                "peak_field_observation")

#: When the external sources below were checked to exist, with author, title and edition confirmed
#: against publisher, library or standards-body records (Phase 216, proportional verification).
SOURCES_VERIFIED_ON = "2026-10-17"

SOURCES = {
    "peak_method_design": {
        "kind": "peak_method_design",
        "title": "Peak Method design choice",
        "note": "Framed by Peak for small-business inventory discovery; not derived from an "
                "external source."},
    "peak_field_observation": {
        "kind": "peak_field_observation",
        "title": "Peak field observation / consultant-added question from prior engagement",
        "note": "Internal empirical source. Cited without client-identifying information; the "
                "supplemental question's field-use provenance stays in the question pool."},
    "ascm_dictionary": {
        "kind": "standard",
        "title": "ASCM Supply Chain Dictionary (formerly the APICS Dictionary)",
        "author": "Association for Supply Chain Management (ASCM)",
        "edition": "19th edition (current when verified)",
        "note": "Reference definitions: inventory record accuracy, cycle counting, reorder point."},
    "piasecki_inventory_accuracy": {
        "kind": "book",
        "title": "Inventory Accuracy: People, Processes, & Technology",
        "author": "David J. Piasecki", "publisher": "OPS Publishing", "year": 2003,
        "edition": "1st edition (ISBN 0-9727631-0-4); a 2nd edition was published in 2021",
        "note": "Practical source on causes of record error, cycle counting, root-cause analysis, "
                "process evaluation and accuracy measurement."},
    "piasecki_inventory_management": {
        "kind": "book",
        "title": "Inventory Management Explained: A Focus on Forecasting, Lot Sizing, Safety "
                 "Stock, and Ordering Systems",
        "author": "David J. Piasecki", "publisher": "OPS Publishing", "year": 2009,
        "edition": "ISBN 978-0-9727631-1-0",
        "note": "Reorder points, lot sizing, safety stock and ordering systems in practice."},
    "frazelle_warehousing": {
        "kind": "book",
        "title": "World-Class Warehousing and Material Handling",
        "author": "Edward H. Frazelle", "publisher": "McGraw-Hill Education", "year": 2016,
        "edition": "2nd edition (ISBN 978-0-07-184282-2); revises the 2002 1st edition",
        "note": "Warehouse activity profiling, receiving and put-away, storage and order picking."},
    "richards_warehouse_management": {
        "kind": "book",
        "title": "Warehouse Management: The Definitive Guide to Improving Efficiency and "
                 "Minimizing Costs in the Modern Warehouse",
        "author": "Gwynne Richards", "publisher": "Kogan Page", "year": 2021,
        "edition": "4th edition (ISBN 978-1-78966-840-7); earlier editions (2011, 2014, 2017) "
                   "were subtitled 'A Complete Guide to ...'",
        "note": "Receiving, putaway, picking and returns processes; warehouse systems."},
    "werc_dc_measures": {
        "kind": "benchmark",
        "title": "DC Measures (annual benchmarking report)",
        "author": "Warehousing Education and Research Council (WERC)",
        "edition": "Annual; the metric set and definitions change by edition (2025 edition the "
                   "latest seen when verified)",
        "note": "Warehouse KPIs and their definitions, including order picking accuracy (percent "
                "by order)."},
    "dehoratius_raman_2008": {
        "kind": "research",
        "title": "Inventory Record Inaccuracy: An Empirical Analysis",
        "author": "Nicole DeHoratius and Ananth Raman",
        "publisher": "Management Science 54(4), 627–641", "year": 2008,
        "edition": "DOI 10.1287/mnsc.1070.0789",
        "note": "In about 370,000 records from 37 stores of one retailer, 65% were inaccurate; "
                "inaccuracy varied with auditing practice, environment complexity and product "
                "category. A retail study: applying it to warehouses is Peak's inference."},
    "kang_gershwin_2005": {
        "kind": "research",
        "title": "Information Inaccuracy in Inventory Systems: Stock Loss and Stockout",
        "author": "Yun Kang and Stanley B. Gershwin",
        "publisher": "IIE Transactions 37(9), 843–859", "year": 2005,
        "note": "Even a small rate of unrecorded stock loss can disrupt replenishment and cause "
                "severe stockouts on items the record shows as available."},
    "coso_internal_control_2013": {
        "kind": "standard",
        "title": "Internal Control — Integrated Framework",
        "author": "Committee of Sponsoring Organizations of the Treadway Commission (COSO)",
        "year": 2013,
        "note": "Principle 5 (accountability, Control Environment) and Principle 10 (control "
                "activities, including segregation of duties); monitoring activities."},
    "aicpa_au_c_501": {
        "kind": "standard",
        "title": "AU-C 501, Audit Evidence — Specific Considerations for Selected Items",
        "author": "AICPA",
        "edition": "AICPA Professional Standards (clarified auditing standards), as currently "
                   "codified",
        "note": "Auditor attendance at physical inventory counting (paragraphs .11–.14): count "
                "instructions, test counts and reconciliation. An audit standard, used here as a "
                "practice reference for what a sound count leaves behind."},
    "fasb_asc_330": {
        "kind": "standard",
        "title": "ASC 330, Inventory (as amended by ASU 2015-11)",
        "author": "Financial Accounting Standards Board (FASB)",
        "edition": "FASB Accounting Standards Codification, as currently codified; ASU 2015-11 "
                   "effective for fiscal years beginning after December 15, 2016",
        "note": "Inventory measurement (lower of cost and net realizable value) and write-downs. "
                "It marks what an operational interview cannot conclude."},
    "fda_fsma_204": {
        "kind": "regulation",
        "title": "Requirements for Additional Traceability Records for Certain Foods (FSMA "
                 "section 204 Food Traceability Rule), 21 CFR Part 1, Subpart S (§1.1300 et seq.)",
        "author": "U.S. Food and Drug Administration",
        "edition": "Compliance date extended from January 20, 2026 to July 20, 2028",
        "note": "Key data elements at critical tracking events (including receiving, shipping and "
                "transformation) and traceability lot codes, for foods on the Food Traceability "
                "List."},
    "gs1_global_traceability": {
        "kind": "standard",
        "title": "GS1 Global Traceability Standard",
        "author": "GS1", "year": 2017,
        "edition": "Release 2.0, ratified August 2017",
        "note": "Cross-industry traceability events and data capture."},
    "gs1_general_specifications": {
        "kind": "standard",
        "title": "GS1 General Specifications",
        "author": "GS1",
        "edition": "Revised regularly (Release 25, January 2025, the latest seen when verified)",
        "note": "Identification keys (GTIN) and barcode rules relevant to item master data."},
    "iso_9001_2015": {
        "kind": "standard",
        "title": "ISO 9001:2015, clause 7.1.6 Organizational knowledge",
        "author": "International Organization for Standardization",
        "edition": "2015 edition with Amendment 1:2024; a revised edition is in final stages",
        "note": "The knowledge needed to operate processes is determined, maintained and made "
                "available."},
    "ohno_tps": {
        "kind": "book",
        "title": "Toyota Production System: Beyond Large-Scale Production",
        "author": "Taiichi Ohno", "publisher": "Productivity Press", "year": 1988,
        "edition": "English edition (Japanese original 1978)",
        "note": "'Repeating why five times': questioning to a root cause."},
    "flanagan_critical_incident": {
        "kind": "research",
        "title": "The Critical Incident Technique",
        "author": "John C. Flanagan", "publisher": "Psychological Bulletin 51(4), 327–358",
        "year": 1954, "edition": "DOI 10.1037/h0061470",
        "note": "Asking for a specific recent incident yields more reliable accounts than "
                "general opinion."},
    "rogers_tibben_lembke_reverse_logistics": {
        "kind": "book",
        "title": "Going Backwards: Reverse Logistics Trends and Practices",
        "author": "Dale S. Rogers and Ronald S. Tibben-Lembke",
        "publisher": "Reverse Logistics Executive Council (University of Nevada, Reno, Center "
                     "for Logistics Management)", "year": 1998,
        "edition": "Title page 1998; some library records give c1999",
        "note": "Returns handling and disposition, and the value recovered or lost there."},
}

_DEFAULT_TRIGGER = ("Peak field use showing the question is low-yield, misread or redundant "
                    "(review of answers, observations and supplemental questions).")


def _p(primary, further=(), revision=_DEFAULT_TRIGGER):
    """``primary``: ``((source, (supports...)), ...)``. The basis is derived from the sources."""
    names = {source for source, _ in primary}
    basis = ("peak_method_design" if names == {"peak_method_design"}
             else "mixed" if "peak_method_design" in names else "external")
    return {"basis": basis,
            "primary_sources": [{"source": s, "supports": list(sup)} for s, sup in primary],
            "further_reading": list(further), "revision_triggers": revision}


PEAK = "peak_method_design"
PIA = "piasecki_inventory_accuracy"
PIM = "piasecki_inventory_management"
COSO = "coso_internal_control_2013"
WERC = "werc_dc_measures"

PROVENANCE = {
    "ctx_operation": _p(((PEAK, ("wording",)), ("frazelle_warehousing", ("inclusion",)))),
    "ctx_traceability": _p(
        (("fda_fsma_204", ("inclusion", "interpretation", "evidence")),
         ("gs1_global_traceability", ("inclusion", "follow_up"))),
        revision="A change in the scope of the FSMA 204 rule or its compliance date (extended to "
                 "July 20, 2028), or a new sector traceability rule affecting Peak clients."),
    "trace_how": _p((("fda_fsma_204", ("evidence", "follow_up")),
                     ("gs1_global_traceability", ("wording",))),
                    revision="A change in FSMA 204 key data elements or critical tracking events."),
    "trace_evidence": _p((("fda_fsma_204", ("evidence",)),
                          ("gs1_global_traceability", ("evidence",)))),
    "goal_pain_incident": _p(((PEAK, ("inclusion",)),
                              ("flanagan_critical_incident", ("wording", "interpretation")))),
    "goal_impact": _p(((PEAK, ("inclusion", "wording")),), further=("kang_gershwin_2005",)),
    "goal_north_star": _p(((PEAK, ("inclusion", "wording")),)),
    "acc_check_before_promise": _p(((PEAK, ("wording", "interpretation")),
                                    ("dehoratius_raman_2008", ("inclusion",)))),
    "acc_distrust_reason": _p((("dehoratius_raman_2008", ("interpretation",)),
                               (PIA, ("follow_up",)))),
    "acc_phantom": _p((("kang_gershwin_2005", ("inclusion", "interpretation")),
                       ("dehoratius_raman_2008", ("inclusion",)))),
    "acc_phantom_example": _p((("flanagan_critical_incident", ("wording",)), (PIA, ("evidence",)))),
    "acc_phantom_evidence": _p(((PIA, ("evidence",)),)),
    "acc_how_known": _p(((PIA, ("inclusion", "interpretation")),
                         ("ascm_dictionary", ("wording",))), further=(WERC,)),
    "acc_results_evidence": _p(((PIA, ("evidence", "interpretation")),), further=(WERC,)),
    "acc_physical_variance": _p((("aicpa_au_c_501", ("evidence",)), (PIA, ("interpretation",))),
                                further=("fasb_asc_330",)),
    "acc_discrepancy_cause": _p(((PIA, ("inclusion", "interpretation")),
                                 ("ohno_tps", ("follow_up",)))),
    "rcv_walkthrough": _p(((PIA, ("inclusion", "interpretation")),),
                          further=("frazelle_warehousing", "richards_warehouse_management")),
    "rcv_exceptions": _p(((PIA, ("inclusion",)),
                          ("richards_warehouse_management", ("interpretation",))),
                         further=(COSO,)),
    "loc_recorded": _p(((PEAK, ("wording",)), (PIA, ("inclusion", "interpretation")),
                        ("frazelle_warehousing", ("interpretation",)))),
    "loc_how_found": _p(((PIA, ("follow_up",)),)),
    "repl_trigger": _p(((PIM, ("inclusion", "interpretation")), ("ascm_dictionary", ("wording",)))),
    "pick_method_confirm": _p((("frazelle_warehousing", ("inclusion", "interpretation")),),
                              further=("richards_warehouse_management",)),
    "pick_confirmation": _p((("frazelle_warehousing", ("interpretation",)),
                             (PIA, ("interpretation",)))),
    "pick_error_detection": _p(((PEAK, ("wording",)), (WERC, ("inclusion",))),
                               revision="A new WERC DC Measures edition that changes the order "
                                        "picking accuracy definition."),
    "pick_error_volume": _p(((PEAK, ("follow_up",)), (WERC, ("interpretation",)))),
    "count_method": _p(((PIA, ("inclusion", "interpretation")), ("ascm_dictionary", ("wording",))),
                       further=("aicpa_au_c_501",)),
    "count_program": _p(((PIA, ("interpretation", "follow_up")),)),
    "count_why_not": _p(((PEAK, ("inclusion", "wording")),), further=(PIA,)),
    "adj_control": _p(((COSO, ("inclusion", "interpretation")), (PIA, ("interpretation",))),
                      revision="A revision of the COSO framework's control-activity guidance."),
    "adj_reviewed": _p(((COSO, ("inclusion", "interpretation")), (PIA, ("evidence",)))),
    "adj_history_evidence": _p(((PIA, ("evidence",)),), further=(COSO,)),
    "adj_review_evidence": _p(((COSO, ("evidence",)),)),
    "rtn_damaged": _p((("rogers_tibben_lembke_reverse_logistics", ("inclusion", "interpretation")),
                       (PIA, ("interpretation",)))),
    "excess_obsolete": _p(((PIM, ("inclusion", "interpretation")),
                           ("fasb_asc_330", ("interpretation",))),
                          revision="A change to ASC 330 inventory measurement guidance."),
    "sys_record": _p(((PEAK, ("inclusion", "wording")),),
                     further=("richards_warehouse_management",)),
    "sys_handoffs": _p(((PEAK, ("inclusion", "wording")),), further=(PIA,)),
    "item_master": _p((("gs1_general_specifications", ("inclusion",)),
                       (PIA, ("interpretation",)))),
    "own_accuracy": _p(((COSO, ("inclusion",)),), further=(PIA,)),
    "people_dependency": _p(((PEAK, ("wording",)), ("iso_9001_2015", ("inclusion",))),
                            revision="Publication of the revised ISO 9001 edition: confirm the "
                                     "organizational-knowledge clause and its numbering."),
    "labor_rework": _p(((PEAK, ("inclusion", "wording", "interpretation")),),
                       further=("ohno_tps",)),
    "kpi_reviewed": _p(((WERC, ("inclusion", "interpretation")),), further=(COSO,),
                       revision="A new WERC DC Measures edition that changes core inventory "
                                "metrics."),
    "kpi_which": _p(((WERC, ("interpretation",)),), further=(COSO,)),
    "kpi_report_evidence": _p(((WERC, ("evidence",)),)),
    "kpi_missing": _p(((PEAK, ("inclusion", "wording")),)),
    "prior_attempts": _p(((PEAK, ("inclusion", "wording")),), further=("ohno_tps",)),
    "constraints": _p(((PEAK, ("inclusion", "wording")),)),
}


def provenance(key: str):
    """The source provenance for a canonical question key, or ``None`` for any other key."""
    entry = PROVENANCE.get(key)
    return {**entry, "primary_sources": [dict(s) for s in entry["primary_sources"]]} if entry \
        else None
