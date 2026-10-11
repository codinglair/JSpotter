# Native Windows setup and workflow

## Prerequisites

Install Python 3.10 or newer and then run:

```powershell
py -m pip install -r requirements.txt
```

Docker, WSL, Bash, and Unix utilities are not required.

## Create private profiles

Copy the synthetic examples outside the tracked example directories:

```powershell
Copy-Item -Recurse .\profiles\sdet.example .\profiles\sdet
Copy-Item -Recurse .\profiles\swe.example .\profiles\swe
Copy-Item .\templates\theme.template.json .\profiles\sdet\theme.json
Copy-Item .\templates\theme.template.json .\profiles\swe\theme.json
```

Replace every sample fact in each `config.json` and `MASTER_PROFILE.md` with verified candidate information. Do not list qualifications the candidate cannot substantiate.

Initialize journals once:

```powershell
py .\scripts\journal.py --profile-dir .\profiles\sdet --init
py .\scripts\journal.py --profile-dir .\profiles\swe --init
```

Initialization refuses to replace an existing journal. `--force` is deliberately required to replace one.

## Search and extraction

Print the configured LinkedIn or Dice URLs and browser extraction JavaScript:

```powershell
py .\scripts\search_linkedin.py --profile-dir .\profiles\sdet
py .\scripts\search_dice.py --profile-dir .\profiles\swe
```

Use Hermes to visit the printed URLs and run the printed JavaScript. Save the resulting JSON inside the selected profile's `output` directory. Dice may open an Apply link only to identify the employer ATS URL. Never fill or submit an application without explicit user authorization.

Process a saved extract, update the journal, fetch descriptions, and score:

```powershell
.\scripts\run_profile.ps1 -ProfileDir .\profiles\sdet -ExtractFile .\profiles\sdet\output\linkedin_extract.json -Source linkedin -Python py
.\scripts\run_profile.ps1 -ProfileDir .\profiles\swe -ExtractFile .\profiles\swe\output\linkedin_extract.json -Source linkedin -Python py
```

Failed description retrieval leaves fit as `Unknown`, so a later scoring run retries it.

## Resume validation and generation

Hermes may use `templates\tailoring_prompt_template.md` with the selected profile's verified master profile. Validate and generate with:

```powershell
py .\scripts\validate_tailoring.py .\profiles\sdet\output\tailoring.json --profile-dir .\profiles\sdet
py .\scripts\generate_pdf.py .\profiles\sdet\output\tailoring.json --profile-dir .\profiles\sdet
```

Generation refuses to overwrite an existing artifact. Use `--overwrite` only after reviewing the destination. If `require_human_review` is enabled, a passing review JSON is mandatory.

## Tests

Tests use synthetic data and never access job sites:

```powershell
py -m unittest discover -s tests -v
```
