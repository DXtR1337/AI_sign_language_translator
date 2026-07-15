[CmdletBinding()]
param(
    [string]$Python = "python"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ScriptsDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepositoryRoot = Split-Path -Parent $ScriptsDirectory
$PatchDirectory = Join-Path $RepositoryRoot "third_party\protobuf"
$WheelDirectory = Join-Path $RepositoryRoot "third_party\wheels"
$PureWheelName = "protobuf-4.25.9+aislt.cve20260994.1-py3-none-any.whl"
$WindowsWheelName = "protobuf-4.25.9+aislt.cve20260994.1-cp310-abi3-win_amd64.whl"
$ExpectedSdistHash = "b0dc7e7c68de8b1ce831dacb12fb407e838edbb8b6cc0dc3a2a6b4cbf6de9cff"
$ExpectedPureWheelHash = "ee988f1e7649e5500b9ef14906bef0757b91f271572067819a75384c4f6b7c0c"
$ExpectedUpstreamWindowsWheelHash = "3683c05154252206f7cb2d371626514b3708199d9bcf683b503dabf3a2e38e06"
$ExpectedWindowsWheelHash = "c3e1802c5b81b5164b895a4fa552551e6aece856ec7aa9e8b93c38ac1d8fa4b3"
$SdistUrl = "https://files.pythonhosted.org/packages/source/p/protobuf/protobuf-4.25.9.tar.gz"
$PyPiMetadataUrl = "https://pypi.org/pypi/protobuf/4.25.9/json"
$TemporaryRoot = Join-Path $env:TEMP ("aislt-protobuf-build-" + [guid]::NewGuid().ToString("N"))
$PreviousSourceDateEpoch = $env:SOURCE_DATE_EPOCH

function Assert-LastExitCode {
    param([string]$Operation)

    if ($LASTEXITCODE -ne 0) {
        throw "$Operation failed with exit code $LASTEXITCODE"
    }
}

$PythonVersion = (& $Python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')").Trim()
Assert-LastExitCode "Checking the Python version"
if ($PythonVersion -ne "3.10") {
    throw "Rebuilding the deterministic protobuf wheels requires Python 3.10; got $PythonVersion"
}

try {
    New-Item -ItemType Directory -Path $TemporaryRoot | Out-Null
    $SdistPath = Join-Path $TemporaryRoot "protobuf-4.25.9.tar.gz"
    Invoke-WebRequest -UseBasicParsing -Uri $SdistUrl -OutFile $SdistPath

    $SdistHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $SdistPath).Hash.ToLowerInvariant()
    if ($SdistHash -ne $ExpectedSdistHash) {
        throw "Unexpected protobuf sdist hash: $SdistHash"
    }

    & $Python -c "import sys, tarfile; tarfile.open(sys.argv[1], 'r:gz').extractall(sys.argv[2])" $SdistPath $TemporaryRoot
    Assert-LastExitCode "Extracting the protobuf sdist"

    $SourceDirectory = Join-Path $TemporaryRoot "protobuf-4.25.9"
    foreach ($PatchName in @(
        "CVE-2026-0994.patch",
        "local-version.patch",
        "pure-python-wheel.patch"
    )) {
        $PatchPath = Join-Path $PatchDirectory $PatchName
        if ($PatchName -eq "pure-python-wheel.patch") {
            & git -c core.autocrlf=false -c core.eol=lf -C $SourceDirectory `
                apply --unidiff-zero --check $PatchPath
            Assert-LastExitCode "Checking $PatchName"
            & git -c core.autocrlf=false -c core.eol=lf -C $SourceDirectory `
                apply --unidiff-zero $PatchPath
        } else {
            & git -c core.autocrlf=false -c core.eol=lf -C $SourceDirectory `
                apply --check $PatchPath
            Assert-LastExitCode "Checking $PatchName"
            & git -c core.autocrlf=false -c core.eol=lf -C $SourceDirectory `
                apply $PatchPath
        }
        Assert-LastExitCode "Applying $PatchName"
    }

    $BuildEnvironment = Join-Path $TemporaryRoot "build-venv"
    & $Python -m venv $BuildEnvironment
    Assert-LastExitCode "Creating the build environment"

    $IsWindowsPlatform = [Environment]::OSVersion.Platform -eq [PlatformID]::Win32NT
    $BuildPython = if ($IsWindowsPlatform) {
        Join-Path $BuildEnvironment "Scripts\python.exe"
    } else {
        Join-Path $BuildEnvironment "bin/python"
    }

    & $BuildPython -m pip install --quiet --upgrade "pip==26.1.2" "setuptools==83.0.0" "wheel==0.47.0"
    Assert-LastExitCode "Installing pinned build tools"

    New-Item -ItemType Directory -Force -Path $WheelDirectory | Out-Null
    $OutputPureWheel = Join-Path $WheelDirectory $PureWheelName
    if (Test-Path -LiteralPath $OutputPureWheel) {
        Remove-Item -LiteralPath $OutputPureWheel -Force
    }

    $env:SOURCE_DATE_EPOCH = "1735689600"
    & $BuildPython -m pip wheel --no-deps --no-build-isolation --no-cache-dir --wheel-dir $WheelDirectory $SourceDirectory
    Assert-LastExitCode "Building the patched protobuf wheel"

    $PureWheelHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $OutputPureWheel).Hash.ToLowerInvariant()
    if ($PureWheelHash -ne $ExpectedPureWheelHash) {
        throw "Unexpected portable wheel hash: $PureWheelHash"
    }

    Write-Host "Verified portable wheel: $OutputPureWheel"
    Write-Host "SHA-256: $PureWheelHash"

    $Metadata = Invoke-RestMethod -UseBasicParsing -Uri $PyPiMetadataUrl
    $UpstreamWheel = @($Metadata.urls | Where-Object {
        $_.filename -eq "protobuf-4.25.9-cp310-abi3-win_amd64.whl"
    })
    if ($UpstreamWheel.Count -ne 1) {
        throw "Could not resolve exactly one official Windows wheel from PyPI"
    }
    if ($UpstreamWheel[0].digests.sha256 -ne $ExpectedUpstreamWindowsWheelHash) {
        throw "PyPI reports an unexpected Windows wheel hash"
    }

    $UpstreamWheelPath = Join-Path $TemporaryRoot $UpstreamWheel[0].filename
    Invoke-WebRequest -UseBasicParsing -Uri $UpstreamWheel[0].url -OutFile $UpstreamWheelPath
    $UpstreamWheelHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $UpstreamWheelPath
    ).Hash.ToLowerInvariant()
    if ($UpstreamWheelHash -ne $ExpectedUpstreamWindowsWheelHash) {
        throw "Unexpected upstream Windows wheel hash: $UpstreamWheelHash"
    }

    $WindowsWheelDirectory = Join-Path $TemporaryRoot "windows-wheel"
    New-Item -ItemType Directory -Path $WindowsWheelDirectory | Out-Null
    & $Python -c "import sys, zipfile; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" `
        $UpstreamWheelPath $WindowsWheelDirectory
    Assert-LastExitCode "Extracting the official Windows wheel"

    foreach ($PatchName in @("CVE-2026-0994.patch", "local-version.patch")) {
        $PatchPath = Join-Path $PatchDirectory $PatchName
        & git -c core.autocrlf=false -c core.eol=lf -C $WindowsWheelDirectory `
            apply --check $PatchPath
        Assert-LastExitCode "Checking $PatchName for the Windows wheel"
        & git -c core.autocrlf=false -c core.eol=lf -C $WindowsWheelDirectory `
            apply $PatchPath
        Assert-LastExitCode "Applying $PatchName to the Windows wheel"
    }

    $OutputWindowsWheel = Join-Path $WheelDirectory $WindowsWheelName
    if (Test-Path -LiteralPath $OutputWindowsWheel) {
        Remove-Item -LiteralPath $OutputWindowsWheel -Force
    }
    & $Python (Join-Path $ScriptsDirectory "repack_patched_wheel.py") `
        $WindowsWheelDirectory $OutputWindowsWheel
    Assert-LastExitCode "Repacking the patched Windows wheel"

    $WindowsWheelHash = (
        Get-FileHash -Algorithm SHA256 -LiteralPath $OutputWindowsWheel
    ).Hash.ToLowerInvariant()
    if ($WindowsWheelHash -ne $ExpectedWindowsWheelHash) {
        throw "Unexpected patched Windows wheel hash: $WindowsWheelHash"
    }

    Write-Host "Verified optimized Windows wheel: $OutputWindowsWheel"
    Write-Host "SHA-256: $WindowsWheelHash"
}
finally {
    if ($null -eq $PreviousSourceDateEpoch) {
        Remove-Item Env:SOURCE_DATE_EPOCH -ErrorAction SilentlyContinue
    } else {
        $env:SOURCE_DATE_EPOCH = $PreviousSourceDateEpoch
    }

    if (Test-Path -LiteralPath $TemporaryRoot) {
        $ResolvedTemporaryRoot = [IO.Path]::GetFullPath($TemporaryRoot)
        $ResolvedTempBase = [IO.Path]::GetFullPath($env:TEMP).TrimEnd("\") + "\"
        if (-not $ResolvedTemporaryRoot.StartsWith(
            $ResolvedTempBase,
            [StringComparison]::OrdinalIgnoreCase
        )) {
            throw "Refusing to remove non-temporary path: $ResolvedTemporaryRoot"
        }
        Remove-Item -LiteralPath $ResolvedTemporaryRoot -Recurse -Force
    }
}
