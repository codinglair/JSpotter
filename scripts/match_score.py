"""Deterministic, candidate-aware job fit scoring."""

from __future__ import annotations


def _terms(values):
    return {str(value).strip().lower() for value in values or [] if str(value).strip()}


def _mentioned(text, terms):
    return {term for term in terms if term in text}


def calculate_match_score(job, description, profile_text="", candidate=None, config=None):
    """Return a transparent 0-100 fit score and evidence details."""
    candidate = candidate or {}
    config = config or {}
    if not description or len(description.strip()) < 50:
        return None, {
            "fit_indicator": "Unknown",
            "reason": "Job description unavailable",
            "verified_matches": [],
            "missing_qualifications": [],
            "unknown": ["job_requirements"],
        }

    text = description.lower()
    title = str(job.get("title") or "").lower()
    location = str(job.get("location") or "").lower()
    skills = _terms(candidate.get("skills"))
    domains = _terms(candidate.get("domains"))
    certifications = _terms(candidate.get("certifications"))
    preferred_roles = _terms(candidate.get("preferred_roles"))

    required_skills = _terms(job.get("required_skills"))
    if not required_skills:
        vocabulary = _terms(config.get("scoring", {}).get("skill_vocabulary")) | skills
        required_skills = _mentioned(text, vocabulary)
    required_certs = _terms(job.get("required_certifications"))
    required_domains = _terms(job.get("required_domains")) or _mentioned(text, domains)

    skill_matches = sorted(required_skills & skills)
    missing_skills = sorted(required_skills - skills)
    cert_matches = sorted(required_certs & certifications)
    missing_certs = sorted(required_certs - certifications)
    domain_matches = sorted(required_domains & domains)

    components = {}
    components["skills"] = round(50 * len(skill_matches) / len(required_skills)) if required_skills else 25
    role_match = any(role in title for role in preferred_roles) if preferred_roles else True
    components["role"] = 15 if role_match else 3

    levels = {"entry": 0, "junior": 0, "mid": 1, "senior": 2, "lead": 3, "principal": 3}
    candidate_level = levels.get(str(candidate.get("seniority", "")).lower())
    required_level = job.get("required_seniority")
    if required_level is None:
        required_level = next((name for name in ("principal", "lead", "senior", "junior", "entry") if name in title), None)
    required_rank = levels.get(str(required_level).lower()) if required_level else None
    components["seniority"] = 5 if required_rank is None or candidate_level is None or candidate_level >= required_rank else 0
    components["domain"] = 15 if domain_matches else (8 if not required_domains else 0)

    locations = candidate.get("locations", {})
    remote_ok = bool(locations.get("remote_us", False))
    local_terms = _terms(locations.get("local"))
    location_match = (
        remote_ok and ("remote" in location or "united states" in location)
    ) or any(term in location for term in local_terms)
    components["location"] = 10 if location_match else (5 if not location else 0)
    components["certifications"] = (
        round(5 * len(cert_matches) / len(required_certs)) if required_certs else 5
    )

    score = max(0, min(100, int(sum(components.values()))))
    indicator = "Strong" if score >= 75 else "Moderate" if score >= 50 else "Weak"
    return score, {
        "fit_indicator": indicator,
        "components": components,
        "verified_matches": skill_matches + domain_matches + cert_matches,
        "missing_qualifications": missing_skills + missing_certs,
        "unknown": [],
        "matched_domains": domain_matches,
        "missing_domains": sorted(required_domains - domains),
    }
