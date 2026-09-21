param(
    [Parameter(Mandatory=$true)][ValidateSet("dev","stg","prod")][string]$Environment,
    [Parameter(Mandatory=$true)][string]$ApiBaseUrl,
    [Parameter(Mandatory=$true)][string]$WeaveImage,
    [Parameter(Mandatory=$true)][string]$CbtVersion,
    [ValidatePattern('^\d+\.\d+\.\d+$')][string]$ManagerVersion = "0.1.11",
    [string]$OutputDirectory = "$PSScriptRoot\..\build-output"
)

$ErrorActionPreference = "Stop"
$ManagerRoot = (Resolve-Path "$PSScriptRoot\..").Path
$GeneratedBuild = Join-Path $ManagerRoot "src\weave_cbt_manager\generated_build.py"
$BootstrapEntry = Join-Path $ManagerRoot "build\manager_entry.py"
$OutputDirectory = [System.IO.Path]::GetFullPath($OutputDirectory)

@"
ENVIRONMENT = $(ConvertTo-Json -InputObject $Environment -Compress)
WEAVE_API_BASE_URL = $(ConvertTo-Json -InputObject $ApiBaseUrl -Compress)
WEAVE_IMAGE = $(ConvertTo-Json -InputObject $WeaveImage -Compress)
CBT_VERSION = $(ConvertTo-Json -InputObject $CbtVersion -Compress)
MANAGER_VERSION = $(ConvertTo-Json -InputObject $ManagerVersion -Compress)
"@ | Set-Content -Path $GeneratedBuild -Encoding UTF8

python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "pip upgrade failed." }
python -m pip install -e "$ManagerRoot" nuitka ordered-set zstandard
if ($LASTEXITCODE -ne 0) { throw "Manager dependency installation failed." }

if (Test-Path $OutputDirectory) { throw "Use a new output directory for this build: $OutputDirectory" }
New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
python "$ManagerRoot\build\create_icon.py"
if ($LASTEXITCODE -ne 0) { throw "Weave icon generation failed." }

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
  --windows-icon-from-ico="$ManagerRoot\resources\weave.ico" `
  --product-name="Weave CBT Manager" `
  --file-version="$ManagerVersion" `
  --product-version="$ManagerVersion" `
  --output-filename=WeaveCBT-Manager.exe `
  --output-dir="$OutputDirectory" `
  "$BootstrapEntry"

if ($LASTEXITCODE -ne 0) { throw "Nuitka Manager build failed." }

$Dist = Get-ChildItem -Path $OutputDirectory -Directory -Filter "*.dist" | Select-Object -First 1
if (-not $Dist) { throw "Nuitka standalone output directory was not created." }

$ManagerExe = Join-Path $Dist.FullName "WeaveCBT-Manager.exe"
if (-not (Test-Path $ManagerExe)) { throw "Compiled Manager executable was not created: $ManagerExe" }

Write-Output $Dist.FullName
