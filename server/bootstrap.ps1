# Run once on the server in an Administrator PowerShell window.
$root = 'C:\anthousa'
New-Item -ItemType Directory -Force $root | Out-Null
$py = (Get-Command python).Source
& $py -m pip install -q shapely numpy
$pull = @'
$ErrorActionPreference = 'Continue'
$env:PYTHONUTF8 = '1'
$root = 'C:\anthousa'; $repo = 'tanxinhao2026-netizen/anthousa'
$sha = (Invoke-RestMethod "https://api.github.com/repos/$repo/commits/main" -Headers @{'User-Agent'='anthousa'}).sha
if ((Test-Path "$root\last_sha.txt") -and ((Get-Content "$root\last_sha.txt") -eq $sha)) { exit 0 }
Invoke-WebRequest "https://github.com/$repo/archive/refs/heads/main.zip" -OutFile "$root\pull.zip" -UseBasicParsing
Remove-Item "$root\pull" -Recurse -Force -ErrorAction SilentlyContinue
Expand-Archive "$root\pull.zip" "$root\pull" -Force
$src = (Get-ChildItem "$root\pull" | Select-Object -First 1).FullName
& 'PYEXE' -m pip install -q shapely numpy
Push-Location $src
& 'PYEXE' engine\build_all.py *> "$root\pull.log"
$ok = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $ok) { exit 1 }
robocopy $src "$root\city" /MIR /NFL /NDL /NJH /NJS | Out-Null
Set-Content "$root\last_sha.txt" $sha
'@
Set-Content "$root\pull.ps1" ($pull -replace 'PYEXE', $py) -Encoding UTF8
schtasks /Create /F /TN AnthousaPull /SC MINUTE /MO 10 /RU SYSTEM /TR "powershell -NoProfile -ExecutionPolicy Bypass -File C:\anthousa\pull.ps1"
schtasks /Run /TN AnthousaPull
