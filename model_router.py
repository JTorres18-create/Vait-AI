
import os

# ==========================================
# VAIT 1.0 — SMART MODEL ROUTER
# ==========================================

EVERYDAY_MODEL = os.getenv(
    "VAIT_EVERYDAY_MODEL", "gpt-5.4-mini"
)

ADVANCED_MODEL = os.getenv(
    "VAIT_ADVANCED_MODEL", "gpt-5.4"
)

# Initial routing rules.
# We'll improve these using testing later.

ADVANCED_KEYWORDS = [
    "engineering",
    "physics",
    "calculus",
    "differential equation",
    "linear algebra",
    "thermodynamics",
    "fluid mechanics",
    "circuit analysis",
    "robotics",
    "structural analysis",
    "derive",
    "prove mathematically"
]


def choose_model(message, mode="auto"):
    """
    Select a model based on user settings.

    auto: Use basic task classification
    everyday: Always use inexpensive model
    advanced: Always use advanced model
    """

    mode = mode.lower().strip()

    if mode == "everyday":
        return EVERYDAY_MODEL, "manual_everyday"

    if mode == "advanced":
        return ADVANCED_MODEL, "manual_advanced"

    if mode != "auto":
        raise ValueError("Invalid model mode")

    message_lower = message.lower()

    if any(
        keyword in message_lower
        for keyword in ADVANCED_KEYWORDS
    ):
        return ADVANCED_MODEL, "automatic_advanced"

    return EVERYDAY_MODEL, "automatic_everyday"
