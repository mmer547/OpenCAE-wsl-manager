$ErrorActionPreference = 'Stop'

$repositoryRoot = Split-Path -Parent $PSScriptRoot
$installerPath = Join-Path $repositoryRoot 'install-openfoam-wsl.ps1'
$launcherPath = Join-Path $repositoryRoot 'install-openfoam-wsl.bat'
$readmePath = Join-Path $repositoryRoot 'README.md'

foreach ($requiredPath in @($installerPath, $launcherPath, $readmePath)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required file is missing: $requiredPath"
    }
}

$bytes = [IO.File]::ReadAllBytes($installerPath)
$hasUtf8Bom = $bytes.Length -ge 3 -and
    $bytes[0] -eq 0xEF -and
    $bytes[1] -eq 0xBB -and
    $bytes[2] -eq 0xBF
if (-not $hasUtf8Bom) {
    throw 'install-openfoam-wsl.ps1 must use UTF-8 with BOM for Windows PowerShell 5.'
}

$tokens = $null
$parseErrors = $null
[void][Management.Automation.Language.Parser]::ParseFile(
    $installerPath,
    [ref] $tokens,
    [ref] $parseErrors
)
if ($parseErrors.Count -gt 0) {
    $messages = $parseErrors | ForEach-Object Message
    throw "PowerShell parse errors:`n$($messages -join "`n")"
}

$launcher = [IO.File]::ReadAllText($launcherPath)
if ($launcher -notmatch [regex]::Escape('install-openfoam-wsl.ps1')) {
    throw 'The BAT launcher does not reference install-openfoam-wsl.ps1.'
}
if ($launcher -notmatch [regex]::Escape('if "%OPENFOAM_EXIT%"=="2"')) {
    throw 'The BAT launcher must distinguish a user cancellation from success.'
}

$installer = [IO.File]::ReadAllText($installerPath)
if ($installer -notmatch [regex]::Escape('$Command.Replace("`r`n", "`n").Replace("`r", "`n")')) {
    throw 'Multiline Bash commands must be normalized to LF before being passed to WSL.'
}
if ($installer -notmatch [regex]::Escape('$userName -notin $ReservedLinuxUserNames')) {
    throw 'Manually entered Linux usernames must reject reserved system names.'
}
if ($installer -match [regex]::Escape('if ! id -u $quotedUser')) {
    throw 'An existing Linux system user must never be reused as the interactive user.'
}
if ($installer -notmatch [regex]::Escape('exit 45')) {
    throw 'Linux user creation must fail when the requested username already exists.'
}
if ($installer -notmatch '(?m)^\s*exit 2\s*$') {
    throw 'A user cancellation must return its dedicated exit code.'
}
if ($installer -notmatch [regex]::Escape('$process.StandardInput.BaseStream.Write($passwordBytes, 0, $passwordBytes.Length)')) {
    throw 'The password hashing process must write UTF-8 bytes without a newline.'
}
if ($installer -match [regex]::Escape('$Password | & wsl.exe')) {
    throw 'Do not pipe the password through Windows PowerShell; it appends CR/LF.'
}
if ($installer -notmatch [regex]::Escape('chpasswd --encrypted')) {
    throw 'The complete password hash must be sent to chpasswd through standard input.'
}
if ($installer -match [regex]::Escape('usermod --password $passwordHash')) {
    throw 'Do not pass a crypt hash through WSL arguments; dollar delimiters can be lost.'
}

Write-Host 'Static checks passed.'
