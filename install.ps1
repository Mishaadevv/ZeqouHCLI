$ErrorActionPreference = "Stop"
$RepoArchiveUrl = "https://github.com/Mishaadevv/ZeqouHCLI/archive/refs/heads/main.zip"
$MinimumPythonVersion = [version]"3.10.0"
Write-Host "Installing Zeqou[H]CLI..." -ForegroundColor Cyan

$PythonCommand = $null
$PythonPrefix = @()
$PythonVersion = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try {
        $DetectedVersion = (& py -3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.0')" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and $DetectedVersion) { $PythonCommand = "py"; $PythonPrefix = @("-3"); $PythonVersion = [version]$DetectedVersion }
    } catch { }
}
if (-not $PythonCommand -and (Get-Command python -ErrorAction SilentlyContinue)) {
    try {
        $DetectedVersion = (& python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.0')" 2>$null | Select-Object -Last 1).Trim()
        if ($LASTEXITCODE -eq 0 -and $DetectedVersion) { $PythonCommand = "python"; $PythonPrefix = @(); $PythonVersion = [version]$DetectedVersion }
    } catch { }
}
if (-not $PythonCommand) { throw "Python 3.10 or newer was not found. Install it from https://www.python.org/downloads/windows/ and try again." }
if ($PythonVersion -lt $MinimumPythonVersion) { throw "Python $PythonVersion is too old. ZeqouHCLI requires Python 3.10 or newer." }
Write-Host "Using Python $PythonVersion" -ForegroundColor DarkGray

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
    if (-not $ProjectFile) { throw "Downloaded source did not contain pyproject.toml." }
    $ProjectRoot = $ProjectFile.DirectoryName
    Write-Host "Installing package and dependencies..."
    & $PythonCommand @PythonPrefix -m pip install --user --upgrade $ProjectRoot
    if ($LASTEXITCODE -ne 0) { throw "pip installation failed. Check your internet connection and Python installation." }
} finally {
    Remove-Item -LiteralPath $TempRoot -Recurse -Force -ErrorAction SilentlyContinue
}

# Important: on Windows the user Scripts path includes PythonXY; --user-base alone does not.
$ScriptsDirectory = (& $PythonCommand @PythonPrefix -c "import sysconfig; print(sysconfig.get_path('scripts', scheme='nt_user'))" 2>$null | Select-Object -Last 1).Trim()
if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($ScriptsDirectory)) { throw "Could not determine Python's user Scripts directory." }
$CliExecutable = Join-Path $ScriptsDirectory "zeqouhcli.exe"
if (-not (Test-Path -LiteralPath $CliExecutable)) { throw "Installation finished, but $CliExecutable was not found." }

$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
$UserEntries = @($UserPath -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$HasUserPath = $false
foreach ($Entry in $UserEntries) { if ($Entry.Trim().TrimEnd('\') -ieq $ScriptsDirectory.TrimEnd('\')) { $HasUserPath = $true; break } }
if (-not $HasUserPath) {
    $NewUserPath = if ([string]::IsNullOrWhiteSpace($UserPath)) { $ScriptsDirectory } else { $UserPath.TrimEnd(';') + ';' + $ScriptsDirectory }
    [Environment]::SetEnvironmentVariable("Path", $NewUserPath, "User")
}
$ProcessEntries = @($env:Path -split ';' | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
$HasProcessPath = $false
foreach ($Entry in $ProcessEntries) { if ($Entry.Trim().TrimEnd('\') -ieq $ScriptsDirectory.TrimEnd('\')) { $HasProcessPath = $true; break } }
if (-not $HasProcessPath) { $env:Path = $env:Path.TrimEnd(';') + ';' + $ScriptsDirectory }
Write-Host "Installation complete: " -NoNewline -ForegroundColor Green
& $CliExecutable --version
Write-Host "Run from any project directory: zeqouhcli" -ForegroundColor Cyan
Write-Host "If a newly opened terminal does not see the command, close and reopen it so it reloads PATH."
