"""Explainable candidate/job keyword overlap scoring."""


def calculate_ats_score(job_description, profile_text, candidate=None, vocabulary=None):
    candidate = candidate or {}
    terms = {
        str(value).strip().lower()
        for value in (vocabulary or candidate.get("skills", []))
        if str(value).strip()
    }
    description = (job_description or "").lower()
    profile = (profile_text or "").lower()
    candidate_skills = {str(value).lower() for value in candidate.get("skills", [])}
    requested = sorted(term for term in terms if term in description)
    matched = sorted(term for term in requested if term in profile or term in candidate_skills)
    if not description.strip():
        return None, {"reason": "Job description unavailable", "matched": [], "missing": []}
    if not requested:
        return None, {"reason": "No configured requirements detected", "matched": [], "missing": []}
    score = round(100 * len(matched) / len(requested))
    return score, {"matched": matched, "missing": sorted(set(requested) - set(matched))}
