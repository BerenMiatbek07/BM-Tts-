param(
    [string]$ProjectRoot = (Split-Path -Parent $PSScriptRoot),
    [string]$OutputRoot = "$env:USERPROFILE\Downloads\BM_Voice_Studio_Windows_v5.6.4_PERSONAL"
)

$ErrorActionPreference = 'Stop'
$python = (Get-Command python.exe).Source
$spec = Join-Path $ProjectRoot 'BM_Text_to_Voice.spec'
$work = Join-Path $ProjectRoot 'build_windows'
$dist = Join-Path $ProjectRoot 'dist_windows'
$projectFull = [IO.Path]::GetFullPath($ProjectRoot).TrimEnd('\')
$workFull = [IO.Path]::GetFullPath($work)
$distFull = [IO.Path]::GetFullPath($dist)
if (-not $workFull.StartsWith($projectFull + '\') -or -not $distFull.StartsWith($projectFull + '\')) {
    throw 'Unsafe Windows build paths.'
}

if (-not (Test-Path -LiteralPath $spec)) {
    throw "PyInstaller spec not found: $spec"
}

Remove-Item -LiteralPath $workFull -Recurse -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $distFull -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $OutputRoot | Out-Null

$env:KIVY_NO_CONSOLELOG = '1'
$env:KIVY_LOG_LEVEL = 'warning'
& $python -m PyInstaller --log-level WARN --noconfirm --clean --workpath $work --distpath $dist $spec
if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed: $LASTEXITCODE" }

$exe = Join-Path $dist 'BM_Text_to_Voice.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw "EXE not created: $exe" }

$target = Join-Path $OutputRoot 'BM_Voice_Studio_v5.6.4_PERSONAL.exe'
Copy-Item -LiteralPath $exe -Destination $target -Force

$hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $target).Hash
Write-Output "WINDOWS_EXE_OK:$target"
Write-Output "SHA256:$hash"
