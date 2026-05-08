param(
    [Parameter(Mandatory = $true)]
    [string]$Tag,

    [string]$ReleaseName = "",

    [switch]$FinalRelease,

    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Run-Command {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $true)]
        [string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed: $FilePath $($Arguments -join ' ')"
    }
}

function Get-GitHubToken {
    $credentialInput = "protocol=https`nhost=github.com`n`n"
    $credentialText = $credentialInput | git credential fill
    $credential = @{}

    foreach ($line in $credentialText) {
        if ($line -match "^(.*?)=(.*)$") {
            $credential[$matches[1]] = $matches[2]
        }
    }

    if (-not $credential["password"]) {
        throw "No GitHub token available from Git credential manager."
    }

    return $credential["password"]
}

function Ensure-Venv {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Python,

        [Parameter(Mandatory = $true)]
        [string]$VenvPython
    )

    $venvOk = $false
    if (Test-Path $VenvPython) {
        try {
            $version = & $VenvPython --version 2>$null
            $venvOk = ($LASTEXITCODE -eq 0 -and $version -match "Python 3\.11\.")
        } catch {
            $venvOk = $false
        }
    }

    if (-not $venvOk) {
        Write-Host "Recreating .venv from stable Python 3.11..."
        Run-Command $Python @("-m", "venv", "--clear", ".venv")
    }

    Run-Command $VenvPython @("-m", "pip", "install", "-r", "requirements.txt", "-r", "requirements-build.txt")
}

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$safeAreaRoot = (Split-Path $repoRoot -Parent)
$python = Join-Path $safeAreaRoot "Python3119\python.exe"
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$buildRoot = Join-Path $safeAreaRoot "builds"
$workRoot = Join-Path $safeAreaRoot "build_work"
$specRoot = Join-Path $safeAreaRoot "build_specs"
$distDir = Join-Path $buildRoot "visRV"
$assetName = "visRV_$Tag`_windows_onedir.zip"
$assetPath = Join-Path $buildRoot $assetName
$repoFullName = "bendermh/visRV"

if (-not $ReleaseName) {
    $ReleaseName = "visRV $Tag"
}

Set-Location $repoRoot

if (-not (Test-Path $python)) {
    throw "Stable Python not found at $python. Copy/install Python 3.11.9 there first."
}

$status = git status --porcelain
if ($status) {
    throw "Working tree is not clean. Commit or stash changes before releasing."
}

$branch = (git rev-parse --abbrev-ref HEAD).Trim()
if ($branch -ne "main") {
    throw "Release must be run from main. Current branch: $branch"
}

Ensure-Venv -Python $python -VenvPython $venvPython

$pythonVersion = & $venvPython --version
if ($pythonVersion -notmatch "Python 3\.11\.") {
    throw "Release build must use Python 3.11.x. Current: $pythonVersion"
}

Run-Command $venvPython @("-m", "py_compile", "visRV.py", "imu_controller.py", "imu_diagnostic.py", "vor.py", "vp.py", "okn.py", "smoothPursuit.py", "saccades.py", "display_utils.py", "deviceSelect.py", "calibration.py")
Run-Command $venvPython @("-c", "import xml.etree.ElementTree as ET; ET.parse(r'GUI\visVR.ui'); print('ui xml ok')")

if (-not $SkipBuild) {
    if (-not (Test-Path $buildRoot)) {
        New-Item -ItemType Directory -Path $buildRoot | Out-Null
    }

    Run-Command $venvPython @(
        "-m", "PyInstaller",
        "--onedir",
        "--console",
        "--clean",
        "--noupx",
        "--noconfirm",
        "--icon=$repoRoot\GUI\VR_icon.ico",
        "--name=visRV",
        "--distpath", $buildRoot,
        "--workpath", $workRoot,
        "--specpath", $specRoot,
        "--add-data", "$repoRoot\GUI;GUI",
        "--add-binary", "$repoRoot\.venv\Lib\site-packages\mbientlab\warble\*.dll;mbientlab/warble",
        "--add-binary", "$repoRoot\.venv\Lib\site-packages\mbientlab\metawear\*.dll;mbientlab/metawear",
        "visRV.py"
    )

    $requiredFiles = @(
        (Join-Path $distDir "visRV.exe"),
        (Join-Path $distDir "_internal\GUI\visVR.ui"),
        (Join-Path $distDir "_internal\mbientlab\metawear\MetaWear.Win32.dll"),
        (Join-Path $distDir "_internal\mbientlab\warble\warble.dll")
    )

    foreach ($file in $requiredFiles) {
        if (-not (Test-Path $file)) {
            throw "Build verification failed. Missing: $file"
        }
    }

    if (Test-Path $assetPath) {
        Remove-Item -LiteralPath $assetPath -Force
    }

    Compress-Archive -Path $distDir -DestinationPath $assetPath -Force
}

if (-not (Test-Path $assetPath)) {
    throw "Release asset not found: $assetPath"
}

$existingTag = git tag --list $Tag
if (-not $existingTag) {
    Run-Command "git" @("tag", "-a", $Tag, "-m", "visRV $Tag")
}

Run-Command "git" @("push", "origin", $Tag)

$token = Get-GitHubToken
$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$releaseBody = @"
Release candidate for visRV.

Windows onedir build included as a zip asset for real-session validation.
"@

$body = @{
    tag_name = $Tag
    target_commitish = "main"
    name = $ReleaseName
    body = $releaseBody
    draft = $false
    prerelease = (-not $FinalRelease.IsPresent)
} | ConvertTo-Json

$release = Invoke-RestMethod `
    -Method Post `
    -Uri "https://api.github.com/repos/$repoFullName/releases" `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"

$uploadUrl = ($release.upload_url -replace "\{.*$", "") + "?name=" + [Uri]::EscapeDataString((Split-Path $assetPath -Leaf))
$assetBytes = [System.IO.File]::ReadAllBytes($assetPath)
$uploadedAsset = Invoke-RestMethod `
    -Method Post `
    -Uri $uploadUrl `
    -Headers $headers `
    -Body $assetBytes `
    -ContentType "application/zip"

Write-Host "Release created: $($release.html_url)"
Write-Host "Asset uploaded: $($uploadedAsset.name) ($($uploadedAsset.size) bytes)"
