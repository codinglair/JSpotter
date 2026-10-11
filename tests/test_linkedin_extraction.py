import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from search_linkedin import COUNT_JS, EXTRACT_JS, apply_search_mode, dedupe_jobs, save_markdown


class LinkedInExtractionRegressionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = (ROOT / "tests" / "fixtures" / "linkedin_job_cards.html").read_text(encoding="utf-8")

    def test_extractor_targets_current_job_card_markup(self):
        self.assertIn("data-occludable-job-id=", self.fixture)
        for selector in (
            "li[data-occludable-job-id]",
            "a.job-card-list__title--link",
            ".artdeco-entity-lockup__subtitle",
            '.artdeco-entity-lockup__caption li span[dir="ltr"]',
        ):
            self.assertIn(selector, EXTRACT_JS)
        self.assertIn("getAttribute('aria-label')", EXTRACT_JS)
        self.assertIn("with verification", EXTRACT_JS)
        self.assertIn("card.dataset.occludableJobId", EXTRACT_JS)
        self.assertEqual("document.querySelectorAll('li[data-occludable-job-id]').length", COUNT_JS)

    def test_canonical_urls_deduplicate_and_titles_are_cleaned(self):
        jobs = [
            {
                "title": "Senior Java Engineer with verification",
                "company": "Acme Systems",
                "location": "Chicago, IL (Hybrid)",
                "url": "https://www.linkedin.com/jobs/view/senior-java-engineer-4212345678/?trackingId=one",
            },
            {
                "title": "Senior Java Engineer",
                "company": "Acme Systems",
                "location": "Chicago, IL (Hybrid)",
                "url": "https://www.linkedin.com/jobs/view/4212345678/?trackingId=two",
            },
        ]
        self.assertIn('data-occludable-job-id="4212345678"', self.fixture)
        self.assertIn('aria-label="Senior Java Engineer with verification"', self.fixture)
        self.assertIn("Acme Systems", self.fixture)
        self.assertIn("Chicago, IL (Hybrid)", self.fixture)

        actual = dedupe_jobs(jobs)

        self.assertEqual(1, len(actual))
        self.assertEqual("Senior Java Engineer", actual[0]["title"])
        self.assertEqual("https://www.linkedin.com/jobs/view/4212345678/", actual[0]["url"])

    def test_remote_input_context_fills_missing_mode(self):
        jobs = apply_search_mode(
            [
                {"title": "Remote job"},
                {"title": "Existing local job", "search_mode": "local"},
            ],
            "remote",
        )

        self.assertEqual("remote", jobs[0]["search_mode"])
        self.assertEqual("local", jobs[1]["search_mode"])

    def test_local_input_context_fills_missing_mode(self):
        jobs = apply_search_mode([{"title": "Local job"}], "local")

        self.assertEqual("local", jobs[0]["search_mode"])

    def test_mixed_input_without_context_preserves_modes_and_marks_missing_unknown(self):
        jobs = apply_search_mode(
            [
                {"title": "Local job", "search_mode": "local"},
                {"title": "Remote job", "search_mode": "remote"},
                {"title": "Missing mode"},
            ]
        )

        self.assertEqual(["local", "remote", "unknown"], [job["search_mode"] for job in jobs])

    def test_unspecified_input_stays_unknown_and_appears_in_markdown(self):
        jobs = apply_search_mode(
            [
                {
                    "title": "Unclassified job",
                    "company": "Acme Systems",
                    "location": "Remote",
                    "url": "https://www.linkedin.com/jobs/view/4212345679/",
                }
            ]
        )
        self.assertEqual("unknown", jobs[0]["search_mode"])

        with tempfile.TemporaryDirectory() as temp_dir:
            report = save_markdown(jobs, "2026-10-11", Path(temp_dir))
            contents = report.read_text()

        self.assertIn("## Unknown (1 jobs)", contents)
        self.assertIn("Unclassified job", contents)


if __name__ == "__main__":
    unittest.main()
