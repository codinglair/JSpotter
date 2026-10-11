"""Deterministic candidate-aware eligibility and technical fit scoring."""

from __future__ import annotations

import re


# Candidate-independent vocabulary. Add aliases here only when they identify a
# concrete technical qualification rather than a broad responsibility.
TECHNICAL_SKILLS = {
    "c#": ("c#", "c sharp"),
    "c++": ("c++",),
    "java": ("java",),
    "javascript": ("javascript",),
    "typescript": ("typescript",),
    "python": ("python",),
    "selenium": ("selenium",),
    "playwright": ("playwright",),
    "cypress": ("cypress",),
    "junit": ("junit",),
    "testng": ("testng",),
    "rest assured": ("rest assured", "restassured"),
    "spring boot": ("spring boot",),
    "sql": ("sql",),
    "maven": ("maven",),
    "gradle": ("gradle",),
    "git": ("git",),
    "jenkins": ("jenkins",),
    "aws": ("aws", "amazon web services"),
    "azure": ("azure",),
    "gcp": ("gcp", "google cloud platform"),
    "docker": ("docker",),
    "kubernetes": ("kubernetes",),
    "kafka": ("kafka",),
    "ci/cd": ("ci/cd", "continuous integration", "continuous delivery"),
}

_REQUIRED_CUES = re.compile(
    r"\b(required|requires?|requiring|must(?:\s+have)?|minimum qualifications?|"
    r"basic qualifications?|you(?:'|’)ll need|need(?:ed)?|proficien(?:t|cy)|"
    r"hands-on experience|experience (?:with|using|in)|demonstrated (?:skill|experience)|"
    r"expertise in|\d+\+?\s+years? (?:of )?(?:experience )?(?:with|using|in)?)\b",
    re.I,
)
_PREFERRED_CUES = re.compile(
    r"\b(preferred|nice to have|bonus|desired|a plus|ideally)\b", re.I
)
_REMOTE_CUES = re.compile(
    r"\b(fully remote|100% remote|remote position|remote role|work from home|"
    r"work remotely|remote within (?:the )?(?:u\.?s\.?|united states))\b",
    re.I,
)
_ONSITE_CUES = re.compile(
    r"\b(on[- ]?site|in[- ]office|report to (?:the )?office|"
    r"work from (?:our|the) office)\b",
    re.I,
)
_HYBRID_CUES = re.compile(r"\bhybrid\b", re.I)
_ATTENDANCE_CUES = re.compile(
    r"\b(\d+|one|two|three|four|five)\s+days?\s+(?:per|a)\s+week\b|"
    r"\b(?:weekly|daily)\s+(?:office|on[- ]?site|in[- ]office)\b",
    re.I,
)
_RELOCATION_CUES = re.compile(
    r"\b(relocation (?:is )?required|must relocate|required to relocate)\b", re.I
)


def _terms(values):
    return {str(value).strip().lower() for value in values or [] if str(value).strip()}


def _contains_term(text, term):
    return re.search(rf"(?<![\w]){re.escape(term)}(?![\w])", text, re.I) is not None


def _canonical_skill(value):
    value = str(value).strip().lower()
    for canonical, aliases in TECHNICAL_SKILLS.items():
        if value == canonical or value in aliases:
            return canonical
    return value


def _skill_vocabulary(config):
    """Return job-requirement vocabulary independent of candidate skills."""
    configured = _terms(config.get("scoring", {}).get("skill_vocabulary"))
    vocabulary = dict(TECHNICAL_SKILLS)
    for term in configured:
        canonical = _canonical_skill(term)
        vocabulary.setdefault(canonical, tuple())
        vocabulary[canonical] = tuple(set(vocabulary[canonical]) | {term, canonical})
    return vocabulary


def identify_skill_requirements(description, config=None, candidate=None):
    """Identify mandatory, preferred, and ambiguous technical skill mentions."""
    config = config or {}
    candidate = candidate or {}
    mandatory, preferred, ambiguous = set(), set(), set()
    vocabulary = _skill_vocabulary(config)
    clauses = re.split(r"(?<=[.;!?])\s+|[\r\n]+|\s+[•|]\s+", description or "")

    for clause in clauses:
        found = {
            canonical
            for canonical, aliases in vocabulary.items()
            if any(_contains_term(clause, alias) for alias in aliases)
        }
        if not found:
            continue
        if _PREFERRED_CUES.search(clause):
            preferred.update(found)
        elif _REQUIRED_CUES.search(clause):
            mandatory.update(found)
        else:
            ambiguous.update(found)

    ambiguous -= mandatory | preferred
    preferred -= mandatory
    return {
        "required": sorted(mandatory),
        "preferred": sorted(preferred),
        "ambiguous": sorted(ambiguous),
    }


def assess_eligibility(job, description, candidate):
    """Return Eligible, Ineligible, or Unverified with concise evidence."""
    location = str(job.get("location") or "").strip()
    location_lower = location.lower()
    text = str(description or "")
    text_lower = text.lower()
    locations = candidate.get("locations", {}) or {}
    remote_us = bool(locations.get("remote_us", False))
    local_terms = _terms(locations.get("local"))
    home_state = str(locations.get("home_state") or "").strip().lower()
    home_state_aliases = _terms(locations.get("home_state_aliases"))
    if home_state:
        home_state_aliases.add(home_state)
    no_relocation = bool(locations.get("no_relocation", False))

    local_in_location = bool(local_terms) and any(
        _contains_term(location_lower, term) for term in local_terms
    )
    location_is_generic = location_lower.strip(" .") in {"", "united states", "us", "u.s.", "usa"}
    local_in_attendance_text = location_is_generic and bool(local_terms) and any(
        re.search(
            rf"(?:on[- ]?site|hybrid|office)[^.;]{{0,80}}{re.escape(term)}|"
            rf"{re.escape(term)}[^.;]{{0,80}}(?:on[- ]?site|hybrid|office)",
            text_lower,
            re.I,
        )
        for term in local_terms
    )
    is_local = local_in_location or local_in_attendance_text
    listed_remote = _contains_term(location_lower, "remote")
    generic_us = location_lower.strip(" .") in {
        "united states", "us", "u.s.", "usa", "remote usa", "remote us"
    }
    remote_evidence = listed_remote or bool(_REMOTE_CUES.search(text))
    onsite_evidence = bool(_ONSITE_CUES.search(text))
    hybrid_evidence = bool(_HYBRID_CUES.search(text))
    attendance_required = bool(_ATTENDANCE_CUES.search(text))
    relocation_required = bool(_RELOCATION_CUES.search(text))

    if home_state_aliases:
        for state_term in home_state_aliases:
            exclusion_patterns = (
                rf"(?:not available|not eligible|cannot hire|unable to hire|excluding|except)\s+"
                rf"(?:in\s+)?[^.;]{{0,100}}(?<![\w]){re.escape(state_term)}(?![\w])",
                rf"(?<![\w]){re.escape(state_term)}(?![\w])[^.;]{{0,60}}(?:excluded|not eligible|not permitted)",
            )
            if any(re.search(pattern, text_lower, re.I) for pattern in exclusion_patterns):
                return "Ineligible", f"Remote work explicitly excludes {home_state.title() or state_term.upper()}"

        allowlist = re.search(
            r"(?:remote[^.;]{0,40}(?:available|open|limited) (?:only )?(?:to )?(?:candidates )?in|"
            r"remote[^.;]{0,40}must reside in|hiring remote[^.;]{0,20}in)\s*([^.;]+)",
            text_lower,
            re.I,
        )
        if allowlist:
            allowed_text = allowlist.group(1)
            nationwide = any(term in allowed_text for term in ("united states", "nationwide", "anywhere in the us", "anywhere in the u.s."))
            home_allowed = any(_contains_term(allowed_text, term) for term in home_state_aliases)
            if not nationwide and not home_allowed:
                return "Ineligible", f"Remote hiring geography does not include {home_state.title()}"

    distant = bool(location_lower) and not is_local and not listed_remote and not generic_us
    if relocation_required and (no_relocation or distant):
        return "Ineligible", f"Relocation is required outside configured local geography ({location})"

    explicit_distant_attendance = distant and (
        onsite_evidence or (hybrid_evidence and attendance_required)
    )
    if explicit_distant_attendance:
        return "Ineligible", f"Required attendance is outside configured local geography ({location})"

    if remote_evidence and (onsite_evidence or hybrid_evidence):
        if distant and attendance_required:
            return "Ineligible", f"Posting requires attendance outside configured local geography ({location})"
        return "Unverified", "Posting contains conflicting remote and on-site/hybrid statements"

    if remote_evidence:
        if remote_us:
            return "Eligible", "Posting confirms remote work and profile permits remote US roles"
        return "Ineligible", "Posting is remote but profile does not permit remote US roles"

    if is_local and (onsite_evidence or hybrid_evidence):
        return "Eligible", "On-site/hybrid location matches configured local geography"

    if generic_us:
        return "Unverified", "United States location does not confirm remote eligibility"
    if distant:
        return "Unverified", f"Work arrangement is not confirmed for distant location ({location})"
    if is_local:
        return "Unverified", "Local location is compatible, but work arrangement is not explicit"
    return "Unverified", "Location and work-arrangement evidence is insufficient"


def calculate_match_score(job, description, profile_text="", candidate=None, config=None):
    """Return a transparent 0-100 technical fit score and evidence details."""
    candidate = candidate or {}
    config = config or {}
    eligibility, eligibility_reason = assess_eligibility(job, description, candidate)

    if not description or len(description.strip()) < 50:
        return None, {
            "fit_indicator": "Unknown",
            "evidence_confidence": "Low",
            "confidence_reason": "Description is unavailable or too short for a technical assessment",
            "reason": "Job description unavailable",
            "eligibility": eligibility,
            "eligibility_reason": eligibility_reason,
            "verified_matches": [],
            "verified_skill_matches": [],
            "missing_qualifications": [],
            "unknown": ["job_requirements"],
            "ambiguous_requirements": [],
            "components": {},
            "component_evidence": {},
            "matched_domains": [],
            "missing_domains": [],
        }

    text = description.lower()
    title = str(job.get("title") or "").lower()
    skills = {_canonical_skill(value) for value in candidate.get("skills", [])}
    domains = _terms(candidate.get("domains"))
    certifications = _terms(candidate.get("certifications"))
    preferred_roles = _terms(candidate.get("preferred_roles"))

    inferred = identify_skill_requirements(description, config, candidate)
    structured_skills = job.get("required_skills")
    if structured_skills is not None:
        required_skills = {_canonical_skill(value) for value in structured_skills}
        skill_source = "structured"
    else:
        required_skills = set(inferred["required"])
        skill_source = "description"
    preferred_skills = set(inferred["preferred"])
    ambiguous_skills = set(inferred["ambiguous"])

    required_certs_value = job.get("required_certifications")
    required_certs = _terms(required_certs_value)
    required_domains_value = job.get("required_domains")
    required_domains = _terms(required_domains_value)

    skill_matches = sorted(required_skills & skills)
    missing_skills = sorted(required_skills - skills)
    cert_matches = sorted(required_certs & certifications)
    missing_certs = sorted(required_certs - certifications)
    domain_matches = sorted(required_domains & domains)
    missing_domains = sorted(required_domains - domains)

    weights = {"skills": 50, "role": 15, "seniority": 5, "domain": 15, "certifications": 5}
    components = {}
    evidence = {}
    if required_skills:
        components["skills"] = 50 * len(skill_matches) / len(required_skills)
        evidence["skills"] = {
            "status": "verified",
            "source": skill_source,
            "required": sorted(required_skills),
            "matched": skill_matches,
            "missing": missing_skills,
            "preferred": sorted(preferred_skills),
        }
    elif job.get("skills_not_required") is True:
        components["skills"] = None
        evidence["skills"] = {"status": "not_applicable", "required": []}
    else:
        components["skills"] = None
        evidence["skills"] = {
            "status": "unknown",
            "required": [],
            "preferred": sorted(preferred_skills),
            "ambiguous": sorted(ambiguous_skills),
        }

    role_match = any(role in title for role in preferred_roles) if preferred_roles else None
    components["role"] = 15 if role_match else (0 if role_match is False else None)
    evidence["role"] = {"status": "verified" if role_match is not None else "unknown", "matched": bool(role_match)}

    levels = {"entry": 0, "junior": 0, "mid": 1, "senior": 2, "lead": 3, "principal": 3}
    candidate_level = levels.get(str(candidate.get("seniority", "")).lower())
    required_level = job.get("required_seniority")
    if required_level is None:
        required_level = next(
            (name for name in ("principal", "lead", "senior", "junior", "entry") if _contains_term(title, name)),
            None,
        )
    required_rank = levels.get(str(required_level).lower()) if required_level else None
    if required_rank is None:
        components["seniority"] = None
        evidence["seniority"] = {"status": "unknown", "required": None}
    else:
        matched = candidate_level is not None and candidate_level >= required_rank
        components["seniority"] = 5 if matched else 0
        evidence["seniority"] = {"status": "verified", "required": required_level, "matched": matched}

    if required_domains:
        components["domain"] = 15 * len(domain_matches) / len(required_domains)
        evidence["domain"] = {"status": "verified", "required": sorted(required_domains), "matched": domain_matches, "missing": missing_domains}
    elif job.get("domains_not_required") is True:
        components["domain"] = None
        evidence["domain"] = {"status": "not_applicable", "required": []}
    else:
        components["domain"] = None
        evidence["domain"] = {"status": "unknown", "required": []}

    if required_certs:
        components["certifications"] = 5 * len(cert_matches) / len(required_certs)
        evidence["certifications"] = {"status": "verified", "required": sorted(required_certs), "matched": cert_matches, "missing": missing_certs}
    elif job.get("certifications_not_required") is True:
        components["certifications"] = None
        evidence["certifications"] = {"status": "not_applicable", "required": []}
    else:
        components["certifications"] = None
        evidence["certifications"] = {"status": "unknown", "required": []}

    applicable = [name for name, points in components.items() if points is not None]
    maximum_applicable = sum(weights[name] for name in applicable)
    score = (
        max(0, min(100, round(100 * sum(components[name] for name in applicable) / maximum_applicable)))
        if maximum_applicable else None
    )
    indicator = (
        "Unknown" if score is None else
        "Strong" if score >= 75 else "Moderate" if score >= 50 else "Weak"
    )
    unknown = [
        name for name, item in evidence.items() if item.get("status") == "unknown"
    ]
    if ambiguous_skills:
        unknown.append("ambiguous_skill_requirements")

    # Evidence completeness is independent of geographic eligibility.
    evidence_points = (
        (2 if evidence["skills"]["status"] == "verified" else 0)
        + (1 if evidence["role"]["status"] == "verified" else 0)
        + (1 if evidence["seniority"]["status"] == "verified" else 0)
        + (1 if evidence["domain"]["status"] == "verified" else 0)
        + (1 if evidence["certifications"]["status"] == "verified" else 0)
    )
    if score is None or evidence_points < 2:
        confidence = "Low"
    elif evidence_points >= 4 and evidence["skills"]["status"] == "verified":
        confidence = "High"
    else:
        confidence = "Medium"
    if ambiguous_skills:
        confidence = {"High": "Medium", "Medium": "Low", "Low": "Low"}[confidence]
    confidence_reason = (
        f"{len(applicable)} applicable criteria; evidence points {evidence_points}/6"
        + (f"; {len(ambiguous_skills)} ambiguous skill requirement(s)" if ambiguous_skills else "")
    )

    return score, {
        "fit_indicator": indicator,
        "evidence_confidence": confidence,
        "confidence_reason": confidence_reason,
        "maximum_applicable_points": maximum_applicable,
        "components": components,
        "component_evidence": evidence,
        "eligibility": eligibility,
        "eligibility_reason": eligibility_reason,
        "verified_matches": skill_matches + domain_matches + cert_matches,
        "verified_skill_matches": skill_matches,
        "missing_qualifications": missing_skills + missing_certs,
        "unknown": unknown,
        "ambiguous_requirements": sorted(ambiguous_skills),
        "preferred_skills": sorted(preferred_skills),
        "identified_required_skills": sorted(required_skills),
        "matched_domains": domain_matches,
        "missing_domains": missing_domains,
    }
