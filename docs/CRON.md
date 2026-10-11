# Hermes automation on Windows

JSpotter preserves Hermes as the browser operator because LinkedIn and Dice extraction depends on an authenticated, interactive browser. Scheduling is optional; unattended application submission is prohibited.

A Hermes task should:

1. Run the appropriate search script with `--profile-dir`.
2. Visit only the printed search URLs.
3. Run the repository-provided extraction JavaScript.
4. Save JSON under that same profile's `output` directory.
5. Run `scripts\run_profile.ps1` for that profile and extract.
6. Report results from that profile's journal.
7. Stop before filling or submitting any application form.

Example local command after Hermes saves an extract:

```powershell
pwsh -NoProfile -File .\scripts\run_profile.ps1 -ProfileDir .\profiles\sdet -ExtractFile .\profiles\sdet\output\linkedin_extract.json -Source linkedin -Python py
```

Hermes configuration, browser selectors, authentication, and delivery channels can change independently of JSpotter. Test the browser step interactively after Hermes or either job site is updated.
