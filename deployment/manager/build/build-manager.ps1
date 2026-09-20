param(
    [Parameter(Mandatory=$true)][ValidateSet("dev","stg","prod")][string]$Environment,
    [Parameter(Mandatory=$true)][string]$ApiBaseUrl,
    [Parameter(Mandatory=$true)][string]$WeaveImage,
    [Parameter(Mandatory=$true)][string]$CbtVersion,
    [string]$OutputDirectory = "$PSScriptRoot\..\build-output"
)

$ErrorActionPreference = "Stop"
$ManagerRoot = (Resolve-Path "$PSScriptRoot\..").Path
$GeneratedBuild = Join-Path $ManagerRoot "src\weave_cbt_manager\generated_build.py"
$BootstrapEntry = Join-Path $ManagerRoot "build\manager_entry.py"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

@"
ENVIRONMENT = "$Environment"
WEAVE_API_BASE_URL = "$ApiBaseUrl"
WEAVE_IMAGE = "$WeaveImage"
CBT_VERSION = "$CbtVersion"
"@ | Set-Content -Path $GeneratedBuild -Encoding UTF8

python -m pip install --upgrade pip
python -m pip install -e "$ManagerRoot" nuitka ordered-set zstandard

if (Test-Path $OutputDirectory) { Remove-Item $OutputDirectory -Recurse -Force }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null

# Compile a normal bootstrap script which imports weave_cbt_manager by its
# package name. Compiling package/__main__.py directly can lose package context
# and make relative imports fail before the GUI can appear.
python -m nuitka `
  --standalone `
  --assume-yes-for-downloads `
  --enable-plugin=pyside6 `
  --include-package=weave_cbt_manager `
  --windows-console-mode=disable `
  --windows-uac-admin `
  --output-filename=WeaveCBT-Manager.exe `
  --output-dir="$OutputDirectory" `
  "$BootstrapEntry"

if ($LASTEXITCODE -ne 0) { throw "Nuitka Manager build failed." }

$Dist = Get-ChildItem -Path $OutputDirectory -Directory -Filter "*.dist" | Select-Object -First 1
if (-not $Dist) { throw "Nuitka standalone output directory was not created." }

$ManagerExe = Join-Path $Dist.FullName "WeaveCBT-Manager.exe"
if (-not (Test-Path $ManagerExe)) { throw "Compiled Manager executable was not created: $ManagerExe" }

Write-Output $Dist.FullName
