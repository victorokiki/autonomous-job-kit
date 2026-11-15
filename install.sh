#!/usr/bin/env bash
# Copy the kit's skills into Claude Code's skills folder (~/.claude/skills by default). Mac and Linux.
# On Windows, double-click install.cmd (it runs install.ps1).
# Usage: ./install.sh [target-folder]
# Copies: internship-application, internship-tracker, job-kit-setup (with templates/), and CAPABILITIES.md.
# Existing copies are moved to <target>/../skills-backup/<name>-YYYYMMDD-HHMMSS, never deleted. (Outside the skills
# folder, so Claude doesn't load two skills with the same name.)
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
TARGET="${1:-$HOME/.claude/skills}"
STAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP="$(dirname "$TARGET")/skills-backup"
mkdir -p "$TARGET"

for skill in internship-application internship-tracker job-kit-setup; do
  if [ -e "$TARGET/$skill" ]; then
    mkdir -p "$BACKUP"
    mv "$TARGET/$skill" "$BACKUP/$skill-$STAMP"
    echo "Moved your old $skill to $BACKUP/$skill-$STAMP"
  fi
  cp -R "$HERE/$skill" "$TARGET/$skill"
  # Each skill gets its own copy of the shared library, so it works on its own.
  if [ -d "$TARGET/$skill/scripts" ]; then
    cp -R "$HERE/lib/jobkit" "$TARGET/$skill/scripts/jobkit"
  fi
  find "$TARGET/$skill" -name '__pycache__' -type d -prune -exec rm -rf {} +
done

# The setup skill reads the templates from its own folder once installed.
cp -R "$HERE/templates" "$TARGET/job-kit-setup/templates"
cp "$HERE/CAPABILITIES.md" "$TARGET/CAPABILITIES.md"

echo "Installed into $TARGET"
echo "Next: pip install openpyxl pypdf python-docx, install Tectonic and Poppler (see README), then ask Claude: \"Set me up\"."
