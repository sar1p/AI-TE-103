# Windows first-run setup and local application launcher.
[CmdletBinding()]
param(
    [string]$Python,
    [switch]$SetupOnly,
    [switch]$Verify,
    [switch]$NoBrowser,
    [ValidateRange(1024, 65525)][int]$Port = 8501
)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
# PS 7 and other parent processes can pass their module path to Windows PS 5.1.
# Include this process's built-in modules without changing the user's settings.
$env:PSModulePath = (Join-Path $PSHOME 'Modules') + [IO.Path]::PathSeparator + $env:PSModulePath
# Native failures are checked explicitly on both Windows PowerShell and PS 7.
if (Test-Path Variable:PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}
$projectRoot = [IO.Path]::GetFullPath((Split-Path -Parent $PSScriptRoot))
$environmentPath = Join-Path $projectRoot '.venv'
$environmentPython = Join-Path $environmentPath 'Scripts\python.exe'
$runtimePath = Join-Path $projectRoot '.runtime'
$mutex = $null
$ownsMutex = $false

function Assert-PlainDirectory([string]$Path) {
    $fullPath = [IO.Path]::GetFullPath($Path).TrimEnd('\')
    $rootPrefix = $projectRoot.TrimEnd('\') + '\'
    if ($fullPath -ne $projectRoot.TrimEnd('\') -and -not $fullPath.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Setup path is outside the project folder: $Path"
    }
    if (Test-Path -LiteralPath $Path) {
        $item = Get-Item -LiteralPath $Path -Force
        if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw "Use a normal project folder. This path is a file or directory link: $Path"
        }
    }
}

function Get-Python312([string]$Executable, [string[]]$Prefix = @()) {
    if (-not $Executable) { return $null }
    $managerAutoInstall = $env:PYTHON_MANAGER_AUTOMATIC_INSTALL
    try {
        # Discovery must not trigger a Python install manager's global install.
        $env:PYTHON_MANAGER_AUTOMATIC_INSTALL = 'false'
        $output = & $Executable @Prefix -c "import sys,sysconfig; sys.exit(1) if sys.version_info[:2] != (3,12) or sysconfig.get_platform() != 'win-amd64' else print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $output) {
            return [string](@($output)[-1])
        }
    } catch { } finally { $env:PYTHON_MANAGER_AUTOMATIC_INSTALL = $managerAutoInstall }
    return $null
}

function Find-Python312 {
    if ($Python) {
        $candidate = Get-Python312 $Python
        if (-not $candidate) { throw '-Python must point to a working 64-bit Python 3.12 executable.' }
        return $candidate
    }
    foreach ($name in @('python3.12', 'python', 'py', 'pymanager')) {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($command) {
            $prefix = @()
            if ($name -eq 'py' -or $name -eq 'pymanager') { $prefix = @('-3.12') }
            $candidate = Get-Python312 $command.Source $prefix
            if ($candidate) { return $candidate }
        }
    }
    foreach ($registry in @('HKCU:\Software\Python\PythonCore\3.12\InstallPath', 'HKLM:\Software\Python\PythonCore\3.12\InstallPath')) {
        if (Test-Path -LiteralPath $registry) {
            $install = (Get-Item -LiteralPath $registry).GetValue('')
            if ($install) {
                $candidate = Get-Python312 (Join-Path $install 'python.exe')
                if ($candidate) { return $candidate }
            }
        }
    }
    return Get-Python312 (Join-Path $runtimePath 'python312\python.exe')
}

function Get-EnvironmentPython {
    if (-not (Test-Path -LiteralPath (Join-Path $environmentPath 'pyvenv.cfg') -PathType Leaf)) { return $null }
    $candidate = Get-Python312 $environmentPython
    if (-not $candidate) { return $null }
    try {
        $prefix = & $candidate -c 'import sys; sys.exit(1) if sys.prefix == sys.base_prefix else print(sys.prefix)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $prefix -and [IO.Path]::GetFullPath([string](@($prefix)[-1])).TrimEnd('\') -eq $environmentPath.TrimEnd('\')) {
            return $candidate
        }
    } catch { }
    return $null
}

function Install-LocalPython {
    # Full runtime (not the embeddable distribution). Source and SHA256 are
    # published in https://www.python.org/ftp/python/index-windows.json.
    $url = 'https://www.python.org/ftp/python/3.12.10/python-3.12.10-amd64.zip'
    $expectedHash = '8649692de846c56a7189d6dae5c322ab20deb1b5908b6f39426b62a36f39415d'
    Assert-PlainDirectory $runtimePath
    New-Item -ItemType Directory -Path $runtimePath -Force | Out-Null
    $archive = Join-Path $runtimePath 'python-3.12.10-amd64.zip'
    if ((Test-Path -LiteralPath $archive) -and (Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        # Delete only this named archive, never an environment or user folder.
        Remove-Item -LiteralPath $archive
    }
    if (-not (Test-Path -LiteralPath $archive)) {
        Write-Host 'Python 3.12 was not found. Downloading a private copy for this project...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -UseBasicParsing -Uri $url -OutFile $archive
    }
    if ((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expectedHash) {
        throw 'The Python download is incomplete or has an unexpected checksum. Run again to retry.'
    }
    # Extract to a fresh folder so a failed earlier attempt cannot mix files.
    $staging = Join-Path $runtimePath ('extract-' + [guid]::NewGuid().ToString('N'))
    Assert-PlainDirectory $staging
    Expand-Archive -LiteralPath $archive -DestinationPath $staging
    $candidate = Get-Python312 (Join-Path $staging 'python.exe')
    if (-not $candidate) { throw 'The downloaded Python runtime could not start on this computer.' }
    $destination = Join-Path $runtimePath 'python312'
    Assert-PlainDirectory $destination
    if (Test-Path -LiteralPath $destination) {
        $backup = Join-Path $runtimePath ('python312-backup-' + [guid]::NewGuid().ToString('N'))
        Assert-PlainDirectory $backup
        Move-Item -LiteralPath $destination -Destination $backup
    }
    Move-Item -LiteralPath $staging -Destination $destination
    return Get-Python312 (Join-Path $destination 'python.exe')
}

function Get-DependencyStamp {
    $hashes = foreach ($name in @('requirements.txt', 'requirements-dev.txt', 'constraints.txt')) {
        (Get-FileHash -LiteralPath (Join-Path $projectRoot $name) -Algorithm SHA256).Hash
    }
    return 'windows-setup-v1:' + ($hashes -join ':')
}

function Test-Dependencies {
    try {
        $check = & $environmentPython -m pip check 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Host ($check -join "`n"); return $false }
        $imports = & $environmentPython -c "import streamlit,pytest; import expert_system,search_algorithm,fuzzy_logic,multi_agent_system; import interface.fleet_session; assert streamlit.__version__ == '1.65.0'; assert pytest.__version__ == '9.1.1'" 2>&1
        if ($LASTEXITCODE -ne 0) { Write-Host ($imports -join "`n"); return $false }
        return $true
    } catch {
        Write-Host $_.Exception.Message
        return $false
    }
}

function Get-FreePort {
    foreach ($number in $Port..($Port + 10)) {
        $listener = $null
        try {
            $listener = [Net.Sockets.TcpListener]::new([Net.IPAddress]::Loopback, $number)
            $listener.Start()
            return $number
        } catch [Net.Sockets.SocketException] {
            # Another application owns this port; try the next one.
        } finally {
            if ($listener) { $listener.Stop() }
        }
    }
    throw "Ports $Port through $($Port + 10) are busy. Close an old demo window and try again."
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or -not [Environment]::Is64BitOperatingSystem) {
        throw 'This launcher requires 64-bit Windows. See the README for Linux/macOS setup.'
    }
    Assert-PlainDirectory $projectRoot
    Assert-PlainDirectory $environmentPath
    foreach ($name in @(
        'app.py',
        'requirements.txt',
        'requirements-dev.txt',
        'constraints.txt',
        'expert_system\__init__.py',
        'search_algorithm\__init__.py',
        'fuzzy_logic\__init__.py',
        'multi_agent_system\__init__.py',
        'interface\fleet_session.py'
    )) {
        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot $name) -PathType Leaf)) {
            throw "The project is incomplete (missing $name). Extract the full ZIP and run run.bat inside it."
        }
    }
    Set-Location -LiteralPath $projectRoot
    $hasher = [Security.Cryptography.SHA256]::Create()
    try {
        $projectHash = [BitConverter]::ToString($hasher.ComputeHash([Text.Encoding]::UTF8.GetBytes($projectRoot.ToLowerInvariant()))).Replace('-', '')
    } finally { $hasher.Dispose() }
    $mutex = [Threading.Mutex]::new($false, ('Local\AI-TE-303-' + $projectHash))
    try { $ownsMutex = $mutex.WaitOne(0) } catch [Threading.AbandonedMutexException] { $ownsMutex = $true }
    if (-not $ownsMutex) { throw 'This copy is already setting up or running in another window. Use that window, or stop it with Ctrl+C before restarting.' }

    Write-Host ''
    Write-Host 'AI-TE-303 | Warehouse Operations'
    Write-Host "Project folder: $projectRoot"
    Write-Host '[1/3] Preparing Python 3.12...'
    $existingPython = Get-EnvironmentPython
    if ($Python) {
        # Validate an explicit override even when a reusable environment exists.
        $null = Find-Python312
    }
    if (-not $existingPython) {
        $basePython = Find-Python312
        if (-not $basePython) { $basePython = Install-LocalPython }
        if (-not $basePython) { throw 'Python setup failed. Run again with an internet connection.' }
        if (Test-Path -LiteralPath $environmentPath) {
            $backup = Join-Path $projectRoot ('.venv-backup-' + [guid]::NewGuid().ToString('N'))
            Assert-PlainDirectory $backup
            Write-Host "Keeping the old environment at: $backup"
            Move-Item -LiteralPath $environmentPath -Destination $backup
        }
        & $basePython -m venv $environmentPath
        if ($LASTEXITCODE -ne 0 -or -not (Get-EnvironmentPython)) {
            throw 'Environment creation failed. Check the message above and available disk space.'
        }
    }

    Write-Host '[2/3] Checking project libraries...'
    $stamp = Get-DependencyStamp
    $stampFile = Join-Path $environmentPath '.ai-te-303-ready'
    $installedStamp = ''
    if (Test-Path -LiteralPath $stampFile -PathType Leaf) { $installedStamp = (Get-Content -LiteralPath $stampFile -Raw).Trim() }
    if ($installedStamp -ne $stamp -or -not (Test-Dependencies)) {
        Write-Host 'Installing libraries. First setup needs internet and may take a few minutes...'
        & $environmentPython -m pip --disable-pip-version-check install --quiet -r (Join-Path $projectRoot 'requirements-dev.txt') -c (Join-Path $projectRoot 'constraints.txt')
        if ($LASTEXITCODE -ne 0) { throw 'Library installation failed. Check the error above, then run run.bat again. For WinError 206, move this project folder directly into Downloads first.' }
        if (-not (Test-Dependencies)) { throw 'The installed libraries did not pass their checks. Check the output above before starting the app.' }
        Set-Content -LiteralPath $stampFile -Value $stamp -Encoding ASCII
    } else {
        Write-Host 'The existing environment is ready; no installation is needed.'
    }
    if ($Verify) {
        Write-Host 'Running the project tests...'
        & $environmentPython -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw 'Project tests failed. The app has not been started. Check the test results above.' }
    }
    if ($SetupOnly) {
        Write-Host '[3/3] Setup complete. Double-click run.bat to open the app.'
    } else {
        $selectedPort = Get-FreePort
        $headless = 'false'
        if ($NoBrowser) { $headless = 'true' }
        Write-Host "[3/3] Opening http://127.0.0.1:$selectedPort"
        Write-Host 'Keep this window open. Press Ctrl+C here to stop the app.'
        # Streamlit opens the default browser only after its server has started.
        & $environmentPython -m streamlit run (Join-Path $projectRoot 'app.py') --server.address 127.0.0.1 --server.port $selectedPort --server.headless $headless --server.showEmailPrompt false --browser.gatherUsageStats false --logger.hideWelcomeMessage true
        if ($LASTEXITCODE -ne 0) { throw 'The app could not run. Check the message above, then try run.bat again.' }
    }
} catch {
    Write-Host ''
    Write-Host ('Setup stopped: ' + $_.Exception.Message) -ForegroundColor Red
    exit 1
} finally {
    if ($ownsMutex -and $mutex) { $mutex.ReleaseMutex() }
    if ($mutex) { $mutex.Dispose() }
}
