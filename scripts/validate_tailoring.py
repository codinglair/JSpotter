"""Candidate-aware validation for LLM-generated resume tailoring JSON."""

from __future__ import annotations

import argparse
import json
import re

from profile_support import add_profile_argument, load_profile_config


REQUIRED_FIELDS = [
    "url", "company", "title", "tailored_summary", "tailored_strengths",
    "tailored_highlights", "ats_keywords_injected", "cover_letter",
]
PANDERING = ["directly relevant to", "well-suited for", "perfectly aligned", "ideal candidate"]


def _candidate_terms(candidate):
    return {
        str(value).strip().lower()
        for key in ("skills", "certifications", "domains")
        for value in candidate.get(key, [])
        if str(value).strip()
    }


def validate_entry(entry, idx=0, candidate=None, settings=None):
    candidate = candidate or {}
    settings = settings or {}
    errors = []
    company = entry.get("company", f"entry {idx}")

    for field in REQUIRED_FIELDS:
        if not entry.get(field):
            errors.append(f'{company}: missing required field "{field}"')
    if "claimed_qualifications" not in entry:
        errors.append(f'{company}: missing required field "claimed_qualifications"')

    highlights = entry.get("tailored_highlights", [])
    employment = candidate.get("employment_history", [])
    employers = [str(item.get("employer", "")).strip().lower() for item in employment]
    employers = [value for value in employers if value]
    for highlight in highlights:
        header = str(highlight.get("header") or "")
        if employers and not any(employer in header.lower() for employer in employers):
            errors.append(f'{company}: highlight employer is not in candidate profile — "{header}"')
        if not any(character.isdigit() for character in header[-16:]):
            errors.append(f'{company}: highlight header missing dates — "{header}"')
        for bullet in highlight.get("bullets", []):
            if len(str(bullet).split()) > int(settings.get("bullet_max_words", 35)):
                errors.append(f"{company}: bullet exceeds configured word limit")

    declared = _candidate_terms(candidate)
    claimed = {
        str(value).strip().lower()
        for value in entry.get("claimed_qualifications", [])
        if str(value).strip()
    }
    unsupported = sorted(claimed - declared)
    if unsupported:
        errors.append(f"{company}: unsupported claimed qualifications — {', '.join(unsupported)}")

    injected = {
        str(value).strip().lower()
        for value in entry.get("ats_keywords_injected", [])
        if str(value).strip()
    }
    unsupported_injected = sorted(injected - declared)
    if settings.get("require_supported_keywords", True) and unsupported_injected:
        errors.append(f"{company}: ATS keywords unsupported by candidate profile — {', '.join(unsupported_injected)}")

    summary = str(entry.get("tailored_summary") or "")
    if sum(summary.count(mark) for mark in ".!?") > int(settings.get("summary_max_sentences", 4)):
        errors.append(f"{company}: summary exceeds configured sentence limit")
    combined = (summary + " " + str(entry.get("cover_letter") or "")).lower()
    for phrase in PANDERING:
        if phrase in combined:
            errors.append(f'{company}: pandering phrase found — "{phrase}"')
    return errors


def validate_and_fix(entry, candidate=None):
    """Only reorder known employment entries; never delete candidate material."""
    candidate = candidate or {}
    order = [
        str(item.get("employer", "")).lower()
        for item in candidate.get("employment_history", [])
        if item.get("employer")
    ]
    highlights = entry.get("tailored_highlights", [])
    if not order:
        return entry, []

    def position(highlight):
        header = str(highlight.get("header") or "").lower()
        for index, employer in enumerate(order):
            if employer in header:
                return index
        return len(order)

    reordered = sorted(highlights, key=position)
    if reordered != highlights:
        entry["tailored_highlights"] = reordered
        return entry, ["reordered highlights to candidate employment history"]
    return entry, []


def main():
    parser = argparse.ArgumentParser(description="Validate tailored resume data")
    parser.add_argument("tailoring_json")
    add_profile_argument(parser)
    parser.add_argument("--fix", action="store_true", help="Rewrite input with safe ordering fixes")
    args = parser.parse_args()

    _, config = load_profile_config(args.profile_dir)
    candidate = config.get("candidate", {})
    settings = config.get("resume_tailoring", {})
    with open(args.tailoring_json, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        data = [data]

    all_errors = []
    changed = False
    for index, entry in enumerate(data):
        if args.fix:
            entry, changes = validate_and_fix(entry, candidate)
            changed = changed or bool(changes)
        all_errors.extend(validate_entry(entry, index, candidate, settings))

    for error in all_errors:
        print(f"ERROR: {error}")
    if changed:
        with open(args.tailoring_json, "w", encoding="utf-8") as handle:
            json.dump(data, handle, indent=2)
    return len(all_errors)


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
