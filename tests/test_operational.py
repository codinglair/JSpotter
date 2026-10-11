import json
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from ats_score import calculate_ats_score
from match_score import calculate_match_score
from profile_support import configured_path, load_profile_config, safe_output_path
from search_linkedin import filter_by_keywords
from validate_tailoring import validate_entry


SDET = {
    "skills": ["java", "selenium", "junit"],
    "domains": ["test automation"],
    "preferred_roles": ["sdet", "test automation"],
    "locations": {"remote_us": True, "local": ["chicago"]},
    "employment_history": [{"employer": "Quality Labs"}],
}
SWE = {
    "skills": ["java", "spring boot", "kafka"],
    "domains": ["backend"],
    "preferred_roles": ["java software engineer", "backend engineer"],
    "locations": {"remote_us": True, "local": ["chicago"]},
    "employment_history": [{"employer": "Software Works"}],
}


class FilteringTests(unittest.TestCase):
    def test_sdet_and_swe_titles_are_profile_driven(self):
        jobs = [
            {"title": "Senior SDET", "url": "https://example/1"},
            {"title": "Senior Java Software Engineer", "url": "https://example/2"},
            {"title": "Engineering Manager", "url": "https://example/3"},
            {"title": "", "url": "https://example/4"},
        ]
        sdet = {"search": {"title_include": ["sdet", "test automation"], "title_exclude": ["manager"]}}
        swe = {"search": {"title_include": ["java", "backend"], "title_exclude": ["manager"]}}
        self.assertEqual([jobs[0]], filter_by_keywords(jobs, "", sdet))
        self.assertEqual([jobs[1]], filter_by_keywords(jobs, "", swe))


class ProfileAndScoringTests(unittest.TestCase):
    def test_profile_paths_are_isolated(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            for directory, name in ((first, "one"), (second, "two")):
                Path(directory, "config.json").write_text(json.dumps({
                    "candidate": {"name": name},
                    "paths": {"journal": "data/journal.xlsx"}
                }), encoding="utf-8")
            dir_one, config_one = load_profile_config(first)
            dir_two, config_two = load_profile_config(second)
            self.assertNotEqual(
                configured_path(dir_one, config_one, "journal", "journal.xlsx"),
                configured_path(dir_two, config_two, "journal", "journal.xlsx"),
            )

    def test_candidate_specific_scoring(self):
        description = (
            "We need Java Selenium JUnit test automation experience for a remote "
            "Senior SDET building reliable automated test suites and quality systems."
        )
        job = {"title": "Senior SDET", "location": "Remote USA"}
        config = {"scoring": {"skill_vocabulary": ["java", "selenium", "junit", "spring boot", "kafka"]}}
        sdet_score, sdet_details = calculate_match_score(job, description, "", SDET, config)
        swe_score, swe_details = calculate_match_score(job, description, "", SWE, config)
        self.assertGreater(sdet_score, swe_score)
        self.assertIn("selenium", sdet_details["verified_matches"])
        self.assertIn("selenium", swe_details["missing_qualifications"])

    def test_missing_description_is_unknown_and_retryable(self):
        score, details = calculate_match_score({"title": "SDET"}, "", "", SDET, {})
        ats, ats_details = calculate_ats_score("", "", SDET)
        self.assertIsNone(score)
        self.assertEqual("Unknown", details["fit_indicator"])
        self.assertIsNone(ats)
        self.assertIn("unavailable", ats_details["reason"].lower())


class ValidationAndSafetyTests(unittest.TestCase):
    def _entry(self):
        return {
            "url": "https://example/job",
            "company": "Example",
            "title": "Senior SDET",
            "tailored_summary": "Automation engineer. Builds reliable tests.",
            "tailored_strengths": ["Automation"],
            "tailored_highlights": [{
                "header": "Quality Labs | Senior SDET | 2021–Present",
                "bullets": ["Built Java Selenium suites that improved regression feedback through CI."],
            }],
            "ats_keywords_injected": ["java", "selenium"],
            "claimed_qualifications": ["java"],
            "cover_letter": "Dear Hiring Manager,\n\nI build verified automation systems.\n\nSincerely,\nCandidate",
        }

    def test_resume_validation_rejects_fabricated_qualification(self):
        entry = self._entry()
        entry["claimed_qualifications"].append("cissp")
        errors = validate_entry(entry, candidate=SDET, settings={"require_supported_keywords": True})
        self.assertTrue(any("unsupported claimed qualifications" in error for error in errors))

    def test_output_overwrite_protection(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "resume.pdf")
            path.write_text("existing", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                safe_output_path(path)


class JournalTests(unittest.TestCase):
    def test_journal_integrity_dedup_and_init_protection(self):
        try:
            from journal import add_jobs, init_journal
            from openpyxl import load_workbook
        except ImportError:
            self.skipTest("openpyxl is not installed")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "journal.xlsx")
            init_journal(path)
            with self.assertRaises(FileExistsError):
                init_journal(path)
            jobs = [{"title": "Senior SDET", "company": "Acme", "location": "Remote", "url": "https://example/jobs/123"}]
            self.assertEqual((1, 0), add_jobs(jobs, path))
            self.assertEqual((0, 1), add_jobs(jobs, path))
            workbook = load_workbook(path)
            self.assertEqual([], __import__("journal").validate_journal_rows(workbook["Jobs"]))


class WorkflowTests(unittest.TestCase):
    def test_synthetic_profile_journal_to_scoring_workflow(self):
        try:
            from journal import add_jobs, init_journal
            from openpyxl import load_workbook
            import run_scoring
        except ImportError:
            self.skipTest("openpyxl is not installed")
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)
            config = {
                "candidate": SDET,
                "scoring": {
                    "priority_thresholds": {"high": 75, "medium": 50},
                    "skill_vocabulary": ["java", "selenium", "junit"],
                },
                "paths": {
                    "journal": "journal.xlsx",
                    "master_profile": "MASTER_PROFILE.md",
                    "output": "output",
                },
            }
            (profile / "config.json").write_text(json.dumps(config), encoding="utf-8")
            (profile / "MASTER_PROFILE.md").write_text("Java Selenium JUnit automation", encoding="utf-8")
            output = profile / "output"
            output.mkdir()
            journal = profile / "journal.xlsx"
            init_journal(journal)
            url = "https://example/jobs/987"
            add_jobs([{"title": "Senior SDET", "company": "Acme", "location": "Remote USA", "url": url}], journal)
            description = "Senior SDET role requiring Java Selenium and JUnit for reliable automated regression suites."
            (output / "descriptions_cache.json").write_text(json.dumps({url: description}), encoding="utf-8")
            with patch.object(sys, "argv", ["run_scoring.py", "--profile-dir", str(profile)]):
                run_scoring.main()
            workbook = load_workbook(journal)
            row = list(workbook["Jobs"].iter_rows(min_row=2, values_only=True))[0]
            self.assertIsInstance(row[6], int)
            self.assertIn(row[10], {"Strong", "Moderate", "Weak"})


if __name__ == "__main__":
    unittest.main()

