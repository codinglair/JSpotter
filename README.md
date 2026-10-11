# JSpotter

JSpotter is a profile-scoped job-search assistant for browser extraction, deterministic fit scoring, resume generation, and Excel tracking. It does not submit applications.

## Supported profiles

Each private profile directory contains:

- `config.json` — candidate facts, search rules, scoring vocabulary, thresholds, and paths
- `MASTER_PROFILE.md` — verified career narrative used for agent-assisted tailoring
- `journal.xlsx` — isolated tracking data
- `output/` — extracts, caches, reviews, and generated artifacts

Select a profile on every command with `--profile-dir`. Synthetic SDET and Java examples are available under `profiles/`.

## Windows quick start

See [docs/SETUP.md](docs/SETUP.md). The offline workflow is:

```powershell
py -m pip install -r requirements.txt
py scripts/journal.py --profile-dir .\profiles\sdet --init
py scripts/search_linkedin.py --profile-dir .\profiles\sdet
# Hermes/browser: visit the printed URL, run the printed extraction JavaScript,
# and save its JSON to .\profiles\sdet\output\linkedin_extract.json.
.\scripts\run_profile.ps1 -ProfileDir .\profiles\sdet -ExtractFile .\profiles\sdet\output\linkedin_extract.json -Source linkedin -Python py
```

Use `profiles\swe` for the Java profile. Never put private profiles under version control.

## Safety

- Existing journals and generated artifacts are not overwritten unless an explicit force/overwrite option is supplied.
- Missing descriptions remain unscored and retryable.
- Mandatory validation failures prevent PDF generation.
- JSpotter does not implement autonomous application submission. Opening an Apply link is only for discovering an employer ATS URL and must stop before form submission.

## Eligibility and scoring

Technical fit and application eligibility are separate:

- `Eligible` confirms compatibility with configured remote/local constraints. Normal High/Medium/Low priority applies.
- `Ineligible` records an explicit conflict such as required attendance or relocation outside accepted geography. Priority is `Ineligible`, while the numeric technical score is preserved.
- `Unverified` means the posting is ambiguous or lacks work-arrangement evidence. Priority is `Review`, never an automatic High recommendation.

The technical score is normalized over only the criteria that can be evaluated: `100 x earned applicable points / maximum applicable points`. The relative weights are required skills 50, preferred-role alignment 15, seniority 5, domain 15, and certifications 5. Unknown and explicitly not-applicable criteria are excluded; a known unmet requirement remains in the denominator. Location is not part of this score. If nothing is evaluable, the score is unknown.

Only skills stated in mandatory language are scored as required. Preferred skills are recorded separately, and ambiguous mentions affect confidence rather than becoming qualification gaps. Required skills are equally weighted within their component; this deliberately simple weighting is a current limitation.

Evidence confidence is stored separately as High, Medium, or Low. Required-skill evidence contributes two evidence points; role, seniority, domain, and certification evidence contribute one each. Fewer than two points is Low, two or three is Medium, and four or more is High when required skills are explicit. Ambiguous skill language lowers confidence by one level. Unspecified domain or certification requirements do not independently lower confidence. Low confidence forces `Review`; Medium and High confidence use the configured score thresholds after the eligibility gate.

Use `--rescore` after changing eligibility or scoring configuration. Existing journals are migrated idempotently by appending an `Evidence Confidence` column, preserving legacy column positions and application-history fields.

## Tests

```powershell
py -m unittest discover -s tests -v
```
