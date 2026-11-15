# Windows installer: copies the kit's skills into Claude Code's skills folder (%USERPROFILE%\.claude\skills by default).
#
# Easiest: double-click install.cmd in this folder. Or, in PowerShell from this folder:
#   powershell -ExecutionPolicy Bypass -File .\install.ps1 [-Target <folder>]
#
# Copies internship-application, internship-tracker, job-kit-setup (with templates\) and CAPABILITIES.md.
# Existing copies are moved to <target>\..\skills-backup\<name>-YYYYMMDD-HHMMSS, never deleted (outside the skills
# folder, so Claude doesn't load two skills with the same name). Works in Windows PowerShell 5.1 and PowerShell 7.
param(
    [string]$Target = (Join-Path (Join-Path $HOME '.claude') 'skills')
)
$ErrorActionPreference = 'Stop'

$Here = $PSScriptRoot
$Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
New-Item -ItemType Directory -Force -Path $Target | Out-Null
$Target = (Resolve-Path -LiteralPath $Target).Path   # a relative -Target becomes a full path
$Backup = Join-Path (Split-Path $Target -Parent) 'skills-backup'

foreach ($skill in @('internship-application', 'internship-tracker', 'job-kit-setup')) {
    $dest = Join-Path $Target $skill
    if (Test-Path -LiteralPath $dest) {
        New-Item -ItemType Directory -Force -Path $Backup | Out-Null
        $old = Join-Path $Backup "$skill-$Stamp"
        Move-Item -LiteralPath $dest -Destination $old
        Write-Host "Moved your old $skill to $old"
    }
    Copy-Item -LiteralPath (Join-Path $Here $skill) -Destination $dest -Recurse
    # Each skill gets its own copy of the shared library, so it works on its own.
    $scripts = Join-Path $dest 'scripts'
    if (Test-Path -LiteralPath $scripts) {
        Copy-Item -LiteralPath (Join-Path (Join-Path $Here 'lib') 'jobkit') -Destination (Join-Path $scripts 'jobkit') -Recurse
    }
    Get-ChildItem -LiteralPath $dest -Recurse -Directory -Filter '__pycache__' | Remove-Item -Recurse -Force
}

# The setup skill reads the templates from its own folder once installed.
Copy-Item -LiteralPath (Join-Path $Here 'templates') -Destination (Join-Path (Join-Path $Target 'job-kit-setup') 'templates') -Recurse
Copy-Item -LiteralPath (Join-Path $Here 'CAPABILITIES.md') -Destination (Join-Path $Target 'CAPABILITIES.md') -Force

Write-Host "Installed into $Target"
Write-Host 'Next: pip install openpyxl pypdf python-docx, install Tectonic and Poppler (see README), then ask Claude: "Set me up".'
