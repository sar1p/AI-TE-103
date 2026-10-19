# Download a new copy into Downloads, then use the same launcher as ZIP users.
[CmdletBinding()]
param(
    [string]$Destination = (Join-Path $env:USERPROFILE 'Downloads\AI-TE-103'),
    [string]$Python,
    [switch]$SetupOnly,
    [switch]$Verify,
    [switch]$NoBrowser,
    [ValidateRange(1024, 65525)][int]$Port = 8501
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

try {
    $destinationPath = [IO.Path]::GetFullPath($Destination)
    if (Test-Path -LiteralPath $destinationPath) {
        $item = Get-Item -LiteralPath $destinationPath -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Choose a normal, empty project location. This path is a file or directory link: $destinationPath"
        }
        foreach ($file in @('app.py', 'run.bat', 'requirements.txt', 'requirements-dev.txt', 'constraints.txt', 'tools\start_windows.ps1', 'expert_system\__init__.py', 'search_algorithm\__init__.py', 'fuzzy_logic\__init__.py', 'multi_agent_system\__init__.py', 'interface\fleet_session.py')) {
            if (-not (Test-Path -LiteralPath (Join-Path $destinationPath $file) -PathType Leaf)) {
                throw "The destination already exists but is not a complete current project: $destinationPath. Nothing was overwritten. Update that copy from GitHub, or move it aside before trying again."
            }
        }
        Write-Host "Using the existing project at $destinationPath"
        Write-Host 'Your files are preserved. This installer does not pull or overwrite an existing copy.'
    } else {
        $parent = Split-Path -Parent $destinationPath
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
        $git = Get-Command git -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        # A failed transfer must not occupy the final project location.
        $staging = [IO.Path]::GetFullPath((Join-Path $parent ('.AI-TE-103-download-' + [guid]::NewGuid().ToString('N'))))
        if ($git) {
            Write-Host "Cloning AI-TE-103 into $destinationPath..."
            & $git.Source clone https://github.com/sar1p/AI-TE-103.git $staging
            if ($LASTEXITCODE -ne 0) { throw 'Clone failed. Check your internet connection and the error above. Setup has not started.' }
            $source = $staging
        } else {
            Write-Host "Git was not found. Downloading the ZIP into $destinationPath..."
            [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
            New-Item -ItemType Directory -Path $staging | Out-Null
            $archive = Join-Path $staging 'project.zip'
            Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/sar1p/AI-TE-103/archive/refs/heads/main.zip' -OutFile $archive
            Expand-Archive -LiteralPath $archive -DestinationPath $staging
            $source = [IO.Path]::GetFullPath((Join-Path $staging 'AI-TE-103-main'))
            $stagingPrefix = [IO.Path]::GetFullPath($staging).TrimEnd('\') + '\'
            if (-not $source.StartsWith($stagingPrefix, [StringComparison]::OrdinalIgnoreCase) -or -not (Test-Path -LiteralPath (Join-Path $source 'app.py') -PathType Leaf)) {
                throw 'The project download is incomplete. Run the installer again with an internet connection.'
            }
            Remove-Item -LiteralPath $archive
        }
        $source = [IO.Path]::GetFullPath($source)
        $parentPrefix = [IO.Path]::GetFullPath($parent).TrimEnd('\') + '\'
        if (-not $source.StartsWith($parentPrefix, [StringComparison]::OrdinalIgnoreCase) -or -not $destinationPath.StartsWith($parentPrefix, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'The download location is outside the selected destination folder.'
        }
        foreach ($file in @('app.py', 'run.bat', 'requirements.txt', 'requirements-dev.txt', 'constraints.txt', 'tools\start_windows.ps1', 'expert_system\__init__.py', 'search_algorithm\__init__.py', 'fuzzy_logic\__init__.py', 'multi_agent_system\__init__.py', 'interface\fleet_session.py')) {
            if (-not (Test-Path -LiteralPath (Join-Path $source $file) -PathType Leaf)) { throw "The project download is incomplete (missing $file). Run the installer again." }
        }
        # Recheck the exact absolute destination before moving the new copy.
        if (Test-Path -LiteralPath $destinationPath) { throw "Another process created $destinationPath. Nothing was overwritten." }
        Move-Item -LiteralPath $source -Destination $destinationPath
        if (Test-Path -LiteralPath $staging) {
            # Only the empty ZIP staging parent remains; no recursive deletion.
            Remove-Item -LiteralPath $staging
        }
    }
    $launcher = Join-Path $destinationPath 'tools\start_windows.ps1'
    $options = @{ SetupOnly = $SetupOnly; Verify = $Verify; NoBrowser = $NoBrowser; Port = $Port }
    if ($Python) { $options.Python = $Python }
    & $launcher @options
    if ($LASTEXITCODE -ne 0) { throw 'Setup failed. Read the message above before retrying.' }
} catch {
    Write-Host ''
    Write-Host ('Installation stopped: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
}
