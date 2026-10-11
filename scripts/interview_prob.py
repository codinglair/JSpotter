"""Explainable fit indicators.

JSpotter intentionally does not present uncalibrated interview probabilities.
"""


def calculate_fit_indicator(match_score, details=None):
    if match_score is None:
        return "Unknown"
    if match_score >= 75:
        return "Strong"
    if match_score >= 50:
        return "Moderate"
    return "Weak"


def calculate_interview_prob(match_score, ats_score=None, title="", description="", location=""):
    """Deprecated compatibility alias returning a label, never a percentage.

    ``ats_score`` and the remaining legacy context arguments are accepted but ignored so
    existing positional and keyword callers keep working without legacy ATS influence.
    """
    return calculate_fit_indicator(match_score)
