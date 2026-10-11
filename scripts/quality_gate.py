"""Candidate-agnostic technical quality gate for tailored resumes."""

import argparse
import json

from profile_support import add_profile_argument, load_profile_config
from validate_tailoring import validate_entry


def score_entry(entry, job_desc="", candidate=None, settings=None):
    candidate = candidate or {}
    settings = settings or {}
    issues = validate_entry(entry, 0, candidate, settings)
    score = max(0, 100 - 10 * len(issues))

    highlights = entry.get("tailored_highlights", [])
    if not highlights:
        score = 0
        issues.append(f"{entry.get('company', '?')}: no employment highlights")
    for highlight in highlights:
        for bullet in highlight.get("bullets", []):
            if not str(bullet).strip():
                score -= 5
                issues.append(f"{entry.get('company', '?')}: empty bullet")
    return max(0, score), issues


def main():
    parser = argparse.ArgumentParser(description="Score tailored resume quality")
    parser.add_argument("tailoring_json")
    add_profile_argument(parser)
    parser.add_argument("--threshold", type=int)
    args = parser.parse_args()
    _, config = load_profile_config(args.profile_dir)
    candidate = config.get("candidate", {})
    settings = config.get("resume_tailoring", {})
    threshold = args.threshold or int(settings.get("quality_gate_threshold", 75))

    with open(args.tailoring_json, encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        data = [data]
    failed = 0
    for entry in data:
        score, issues = score_entry(entry, candidate=candidate, settings=settings)
        status = "PASS" if score >= threshold else "FAIL"
        print(f"{status}: {entry.get('company', '?')} ({score}/100)")
        for issue in issues:
            print(f"  {issue}")
        failed += status == "FAIL"
    return failed


if __name__ == "__main__":
    raise SystemExit(1 if main() else 0)
