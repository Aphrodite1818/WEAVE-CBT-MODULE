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

python -m nuitka `
  --standalone `
  --assume-yes-for-downloads `
  --enable-plugin=pyside6 `
  --windows-console-mode=disable `
  --windows-uac-admin `
  --output-filename=WeaveCBT-Manager.exe `
  --output-dir="$OutputDirectory" `
  "$ManagerRoot\src\weave_cbt_manager\__main__.py"

$Dist = Get-ChildItem -Path $OutputDirectory -Directory -Filter "*.dist" | Select-Object -First 1
if (-not $Dist) { throw "Nuitka standalone output directory was not created." }
Write-Output $Dist.FullName
