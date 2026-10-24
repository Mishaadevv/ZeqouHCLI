$ErrorActionPreference = "Stop"

$RepoArchiveUrl = "https://github.com/Mishaadevv/ZeqouHCLI/archive/refs/heads/main.zip"
$MinimumPythonVersion = [version]"3.10.0"

Write-Host "Installing Zeqou[H]CLI..." -ForegroundColor Cyan

# Locate a usable Python 3 installation without requiring Git or administrator rights.
$PythonCommand = $null
$PythonPrefix = @()
$PythonVersion = $null

if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $DetectedVersion = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.0')" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and $DetectedVersion) {
            $PythonCommand = "py"
            $PythonPrefix = @("-3")
            $PythonVersion = [version]$DetectedVersion
        }
    } catch { }
}

if (-not $PythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
        $DetectedVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.0')" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and $DetectedVersion) {
            $PythonCommand = "python"
            $PythonPrefix = @()
            $PythonVersion = [version]$DetectedVersion
        }
    } catch { }
}

if (-not $PythonCommand) {
    throw "Python 3.10 or newer was not found. Install Python from https://www.python.org/downloads/windows/ and enable the Python launcher, then run this command again."
}
if ($PythonVersion -lt $MinimumPythonVersion) {
    throw "Python $PythonVersion is too old. ZeqouHCLI requires Python 3.10 or newer."
}
Write-Host "Using Python $PythonVersion" -ForegroundColor DarkGray

# Download the public source archive and install it locally; Git is not required.
$TempRoot = Join-Path ([System.IO.Path]::GetTempPath()) ("zeqouhcli-install-" + [guid]::NewGuid().ToString("N"))
$ZipPath = Join-Path $TempRoot "source.zip"
$ExtractPath = Join-Path $TempRoot "source"
New-Item -ItemType Directory -Path $TempRoot -Force | Out-Null

try {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    Write-Host "Downloading source from GitHub..."
    Invoke-WebRequest -Uri $RepoArchiveUrl -OutFile $ZipPath -UseBasicParsing
    Expand-Archive -LiteralPath $ZipPath -DestinationPath $ExtractPath -Force

    $ProjectFile = Get-ChildItem -Path $ExtractPath -Filter "pyproject.toml" -Recurse -File | Select-Object -First 1
    if (-not $ProjectFile) {
        throw "Downloaded source did not contain pyproject.toml. Check the repository URL and try again."
    }
    $ProjectRoot = $ProjectFile.DirectoryName

    Write-Host "Installing package and dependencies..."
    & $PythonCommand @PythonPrefix -m pip install --user --upgrade $ProjectRoot
    if ($LASTEXITCODE -ne 0) {
        throw "pip installation failed. Check your internet connection and Python installation."
    }
}
finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

$UserBase = (& $PythonCommand @PythonPrefix -m site --user-base | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or -not $UserBase) {
    throw "Could not determine Python's user installation directory."
}
$ScriptsDirectory = Join-Path $UserBase "Scripts"

# Add the Scripts directory to the user's permanent PATH and this PowerShell session.
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$UserPathEntries = @()
if (-not [string]::IsNullOrWhiteSpace($UserPath)) {
    $UserPathEntries = $UserPath -split ";"
}
$AlreadyInUserPath = $false
foreach ($Entry in $UserPathEntries) {
    if (-not [string]::IsNullOrWhiteSpace($Entry) -and $Entry.Trim().TrimEnd([char]'\') -ieq $ScriptsDirectory.TrimEnd([char]'\')) {
        $AlreadyInUserPath = $true
        break
    }
}
if (-not $AlreadyInUserPath) {
    $NewUserPath = if ([string]::IsNullOrWhiteSpace($UserPath)) { $ScriptsDirectory } else { $UserPath.TrimEnd(";") + ";" + $ScriptsDirectory }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
}

$ProcessPathEntries = $env:Path -split ";"
$AlreadyInProcessPath = $false
foreach ($Entry in $ProcessPathEntries) {
    if (-not [string]::IsNullOrWhiteSpace($Entry) -and $Entry.Trim().TrimEnd([char]'\') -ieq $ScriptsDirectory.TrimEnd([char]'\')) {
        $AlreadyInProcessPath = $true
        break
    }
}
if (-not $AlreadyInProcessPath) {
    $env:Path = if ([string]::IsNullOrWhiteSpace($env:Path)) { $ScriptsDirectory } else { $env:Path.TrimEnd(";") + ";" + $ScriptsDirectory }
}

$CliExecutable = Join-Path $ScriptsDirectory "zeqouhcli.exe"
if (Test-Path -LiteralPath $CliExecutable) {
    Write-Host ""
    Write-Host "Installation complete: " -NoNewline -ForegroundColor Green
    & $CliExecutable --version
} else {
    Write-Host "Installation completed. The CLI launcher was not found at its expected path." -ForegroundColor Yellow
}
Write-Host "The 'zeqouhcli' command is now added to your user PATH." -ForegroundColor Green
Write-Host "Run it from any project folder with: zeqouhcli" -ForegroundColor Cyan
Write-Host "No administrator rights or Git installation are required."
