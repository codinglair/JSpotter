import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from search_linkedin import COUNT_JS, EXTRACT_JS, dedupe_jobs


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


if __name__ == "__main__":
    unittest.main()
