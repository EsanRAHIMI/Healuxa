"""Goal catalogue and the coordination plan derived from it.

A plan is a sequence of *coordination* steps (understand → consult → care → follow up). It never
selects a treatment, test or product: what care a customer receives is decided with the
practitioner they consult. Each bookable step only names the provider-catalog category to look in.
"""

from __future__ import annotations

from dataclasses import dataclass

# Goal code → provider-catalog service category (provider-service stores categories lowercased).
GOAL_CATEGORIES: dict[str, str] = {
    "skin_health": "dermatology",
    "facial_aesthetics": "aesthetics",
    "hair_restoration": "hair",
    "dental_smile": "dental",
    "weight_management": "nutrition",
    "fitness_recovery": "physiotherapy",
    "preventive_checkup": "general practice",
    "longevity": "longevity",
    "mental_wellbeing": "mental wellbeing",
}

GOAL_TITLES: dict[str, str] = {
    "skin_health": "Skin health",
    "facial_aesthetics": "Facial aesthetics",
    "hair_restoration": "Hair restoration",
    "dental_smile": "Dental and smile",
    "weight_management": "Weight management",
    "fitness_recovery": "Fitness and recovery",
    "preventive_checkup": "Preventive check-up",
    "longevity": "Longevity",
    "mental_wellbeing": "Mental wellbeing",
}

MAX_GOALS = 3

PHASE_UNDERSTAND = "understand"
PHASE_CONSULT = "consult"
PHASE_CARE = "care"
PHASE_FOLLOW_UP = "follow_up"

STEP_INTAKE = "intake_assessment"
STEP_CONSULTATION = "consultation"
STEP_CARE = "care"
STEP_FOLLOW_UP = "follow_up"
STEP_REVIEW = "progress_review"

# Steps completed by a provider visit; the rest are completed by the customer or by an assessment.
BOOKABLE_STEPS = frozenset({STEP_CONSULTATION, STEP_CARE, STEP_FOLLOW_UP})

ACTION_FOR_STEP: dict[str, str] = {
    STEP_INTAKE: "assess",
    STEP_CONSULTATION: "book",
    STEP_CARE: "book",
    STEP_FOLLOW_UP: "follow_up",
    STEP_REVIEW: "assess",
}


@dataclass(frozen=True)
class StepTemplate:
    code: str
    title: str
    goal: str | None = None
    service_category: str | None = None


@dataclass(frozen=True)
class PhaseTemplate:
    code: str
    name: str
    steps: tuple[StepTemplate, ...]


def build_plan(goals: list[str]) -> tuple[PhaseTemplate, ...]:
    """Deterministic plan for validated goal codes, in the order the customer chose them."""

    def per_goal(code: str, label: str) -> tuple[StepTemplate, ...]:
        return tuple(
            StepTemplate(
                code=code,
                title=f"{label} — {GOAL_TITLES[goal]}",
                goal=goal,
                service_category=GOAL_CATEGORIES[goal],
            )
            for goal in goals
        )

    return (
        PhaseTemplate(
            PHASE_UNDERSTAND,
            "Understand your needs",
            (StepTemplate(STEP_INTAKE, "Tell us your preferences"),),
        ),
        PhaseTemplate(PHASE_CONSULT, "Consult a verified practitioner", per_goal(STEP_CONSULTATION, "Consultation")),
        PhaseTemplate(PHASE_CARE, "Receive your care", per_goal(STEP_CARE, "Care agreed with your practitioner")),
        PhaseTemplate(
            PHASE_FOLLOW_UP,
            "Follow up and review",
            (*per_goal(STEP_FOLLOW_UP, "Follow-up visit"), StepTemplate(STEP_REVIEW, "Review your progress")),
        ),
    )
