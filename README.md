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

## Tests

```powershell
py -m unittest discover -s tests -v
```
