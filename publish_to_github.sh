#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
repo="uhrensohn86/heimenergie-integration"
if ! command -v gh >/dev/null || ! command -v git >/dev/null; then
  echo 'Fehler: Offizielles gh und git fehlen.' >&2; exit 1
fi
if [[ -e .git ]]; then
  echo 'Stopp: Ordner enthält bereits .git. Bitte zuerst Repo-Zustand prüfen.' >&2; exit 1
fi
if gh repo view "$repo" >/dev/null 2>&1; then
  echo "Stopp: GitHub-Repository $repo existiert bereits." >&2; exit 1
fi
python -m compileall -q custom_components/heimenergie
python tests/basic_check.py
grep -q '"domain": "heimenergie"' custom_components/heimenergie/manifest.json
if grep -RIlE '(BEGIN PRIVATE KEY|ghp_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+)' custom_components tests README.md PRIVACY.md; then
  echo 'Stopp: Verdächtige Zugangsdaten im Projekt.' >&2; exit 1
fi
printf 'NEUES öffentliches Repository %s erstellen und diesen Code veröffentlichen? [ja/NEIN]: ' "$repo"
read -r answer
if [[ "$answer" != ja ]]; then echo 'Abgebrochen.'; exit 0; fi
gh auth status >/dev/null
git init -b main
git add README.md PRIVACY.md LICENSE hacs.json custom_components tests .gitignore publish_to_github.sh
git diff --cached --check
git commit -m 'Initial HeimEnergie backend v0.2.0-alpha'
gh repo create "$repo" --public --source=. --remote=origin --push
printf '\nGitHub: https://github.com/%s\n' "$repo"
