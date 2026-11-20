[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding = [Text.UTF8Encoding]::new($false)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$UbuntuDistribution = 'Ubuntu-24.04'
$ReservedLinuxUserNames = @(
    'root', 'daemon', 'bin', 'sys', 'sync', 'games', 'man', 'lp', 'mail',
    'news', 'uucp', 'proxy', 'www-data', 'backup', 'list', 'irc', '_apt',
    'nobody', 'systemd-network', 'systemd-timesync', 'messagebus', 'syslog'
)

function Invoke-Wsl {
    param(
        [Parameter(Mandatory = $true)][string] $Distribution,
        [Parameter(Mandatory = $true)][string] $Command,
        [string] $User = 'root'
    )

    # This file uses CRLF for Windows PowerShell 5 compatibility. Bash treats a
    # trailing CR as part of shell syntax (for example, "set -e\r"), so convert
    # multiline commands to Unix line endings before passing them to WSL.
    $normalizedCommand = $Command.Replace("`r`n", "`n").Replace("`r", "`n")
    & wsl.exe --distribution $Distribution --user $User -- bash -lc $normalizedCommand
    if ($LASTEXITCODE -ne 0) {
        throw "WSL内のコマンドが失敗しました (終了コード: $LASTEXITCODE)。"
    }
}

function Get-InstalledWslNames {
    $output = & wsl.exe --list --quiet 2>$null
    if ($LASTEXITCODE -ne 0) { return @() }

    return @($output | ForEach-Object {
        ($_ -replace [char]0, '').Trim()
    } | Where-Object { $_ })
}

function New-InitialPassword {
    $required = @(
        'ABCDEFGHJKLMNPQRSTUVWXYZ'[(Get-Random -Minimum 0 -Maximum 24)]
        'abcdefghijkmnopqrstuvwxyz'[(Get-Random -Minimum 0 -Maximum 25)]
        '23456789'[(Get-Random -Minimum 0 -Maximum 8)]
        '!@#%_-+='[(Get-Random -Minimum 0 -Maximum 8)]
    )
    $characters = 'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#%_-+='
    $passwordCharacters = [Collections.Generic.List[char]]::new()
    foreach ($character in $required) { $passwordCharacters.Add($character) }

    $randomBytes = New-Object byte[] 16
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
    foreach ($randomByte in $randomBytes) {
        $passwordCharacters.Add($characters[$randomByte % $characters.Length])
    }

    $shuffleBytes = New-Object byte[] $passwordCharacters.Count
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($shuffleBytes)
    $shuffled = for ($index = 0; $index -lt $passwordCharacters.Count; $index++) {
        [PSCustomObject]@{ Character = $passwordCharacters[$index]; Order = $shuffleBytes[$index] }
    }
    return -join ($shuffled | Sort-Object Order | ForEach-Object Character)
}

function ConvertFrom-SecureValue {
    param([Parameter(Mandatory = $true)][Security.SecureString] $SecureValue)

    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($SecureValue)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
}

function Select-LinuxCredentials {
    $automaticUser = ($env:USERNAME.ToLowerInvariant() -replace '[^a-z0-9_-]', '')
    if (-not $automaticUser) { $automaticUser = 'openfoam' }
    if ($automaticUser -notmatch '^[a-z_]') { $automaticUser = "user$automaticUser" }
    if ($automaticUser -in $ReservedLinuxUserNames) { $automaticUser = "user-$automaticUser" }
    $automaticPassword = New-InitialPassword

    Write-Host ''
    $customChoice = (Read-Host 'Linuxユーザー名とパスワードを手動入力しますか？ [y/N]').Trim()
    if ($customChoice -notmatch '^(?i:y|yes)$') {
        return [PSCustomObject]@{
            UserName        = $automaticUser
            Password        = $automaticPassword
            PasswordDisplay = $automaticPassword
            ModeLabel       = '自動設定'
        }
    }

    Write-Host ''
    Write-Host 'Linuxユーザー名は、小文字英字または「_」で始まる32文字以内の名前を指定してください。'
    do {
        $userName = (Read-Host 'Linuxユーザー名').Trim()
        $validUserName = $userName -match '^[a-z_][a-z0-9_-]{0,31}$' -and
            $userName -notin $ReservedLinuxUserNames
        if (-not $validUserName) {
            Write-Host '使用できない形式か、Linuxのシステムで予約されているユーザー名です。別の名前を入力してください。' -ForegroundColor Yellow
        }
    } until ($validUserName)

    Write-Host 'パスワードを入力してください。長さや文字種の制限はありません。'
    do {
        $securePassword = Read-Host 'パスワード' -AsSecureString
        $password = ConvertFrom-SecureValue $securePassword
        $validPassword = $password.Length -gt 0
        if (-not $validPassword) {
            Write-Host '空のパスワードは設定できません。' -ForegroundColor Yellow
            continue
        }

        $secureConfirmation = Read-Host 'パスワード（確認）' -AsSecureString
        $confirmation = ConvertFrom-SecureValue $secureConfirmation
        $passwordsMatch = $password -ceq $confirmation
        if (-not $passwordsMatch) {
            Write-Host 'パスワードが一致しません。もう一度入力してください。' -ForegroundColor Yellow
        }
    } until ($validPassword -and $passwordsMatch)

    return [PSCustomObject]@{
        UserName        = $userName
        Password        = $password
        PasswordDisplay = '（ユーザー入力済み・非表示）'
        ModeLabel       = '手動設定'
    }
}

function Set-WslUserPassword {
    param(
        [Parameter(Mandatory = $true)][string] $Distribution,
        [Parameter(Mandatory = $true)][string] $UserName,
        [Parameter(Mandatory = $true)][string] $Password
    )

    $processInfo = New-Object Diagnostics.ProcessStartInfo
    $processInfo.FileName = (Get-Command wsl.exe).Source
    $processInfo.Arguments = "--distribution $Distribution --user root -- openssl passwd -6 -stdin"
    $processInfo.UseShellExecute = $false
    $processInfo.CreateNoWindow = $true
    $processInfo.RedirectStandardInput = $true
    $processInfo.RedirectStandardOutput = $true
    $processInfo.RedirectStandardError = $true

    $process = New-Object Diagnostics.Process
    $process.StartInfo = $processInfo
    try {
        [void] $process.Start()
        # Write without WriteLine: adding CR/LF changes the password being hashed.
        $passwordBytes = [Text.UTF8Encoding]::new($false).GetBytes($Password)
        $process.StandardInput.BaseStream.Write($passwordBytes, 0, $passwordBytes.Length)
        $process.StandardInput.BaseStream.Flush()
        $process.StandardInput.Close()
        $passwordHash = $process.StandardOutput.ReadToEnd().Trim()
        $hashError = $process.StandardError.ReadToEnd().Trim()
        $process.WaitForExit()
        if ($process.ExitCode -ne 0) {
            throw "Linuxユーザーのパスワードハッシュ生成に失敗しました (終了コード: $($process.ExitCode)): $hashError"
        }
    }
    finally {
        $process.Dispose()
        if ($passwordBytes) {
            [Array]::Clear($passwordBytes, 0, $passwordBytes.Length)
        }
    }

    if (-not $passwordHash) {
        throw 'Linuxユーザーのパスワードハッシュを生成できませんでした。'
    }

    $setPasswordInfo = New-Object Diagnostics.ProcessStartInfo
    $setPasswordInfo.FileName = (Get-Command wsl.exe).Source
    $setPasswordInfo.Arguments = "--distribution $Distribution --user root -- chpasswd --encrypted"
    $setPasswordInfo.UseShellExecute = $false
    $setPasswordInfo.CreateNoWindow = $true
    $setPasswordInfo.RedirectStandardInput = $true
    $setPasswordInfo.RedirectStandardOutput = $true
    $setPasswordInfo.RedirectStandardError = $true

    $setPasswordProcess = New-Object Diagnostics.Process
    $setPasswordProcess.StartInfo = $setPasswordInfo
    try {
        [void] $setPasswordProcess.Start()
        # Keep the complete $6$salt$digest value away from WSL argument parsing.
        $credentialBytes = [Text.UTF8Encoding]::new($false).GetBytes("$UserName`:$passwordHash")
        $setPasswordProcess.StandardInput.BaseStream.Write($credentialBytes, 0, $credentialBytes.Length)
        $setPasswordProcess.StandardInput.BaseStream.Flush()
        $setPasswordProcess.StandardInput.Close()
        $setPasswordOutput = $setPasswordProcess.StandardOutput.ReadToEnd().Trim()
        $setPasswordError = $setPasswordProcess.StandardError.ReadToEnd().Trim()
        $setPasswordProcess.WaitForExit()
        if ($setPasswordProcess.ExitCode -ne 0) {
            throw "Linuxユーザーのパスワード設定に失敗しました (終了コード: $($setPasswordProcess.ExitCode)): $setPasswordError $setPasswordOutput"
        }
    }
    finally {
        $setPasswordProcess.Dispose()
        if ($credentialBytes) {
            [Array]::Clear($credentialBytes, 0, $credentialBytes.Length)
        }
    }
    $passwordHash = $null
}

function Select-OpenFoamVersion {
    param([string] $Repository, [string] $VersionPattern, [string] $PackageSuffix = '')
    $available = @()
    try {
        $response = Invoke-WebRequest -UserAgent 'curl/8.0' -UseBasicParsing -ErrorAction Stop -TimeoutSec 30 -Uri "$Repository/dists/noble/main/binary-amd64/Packages"
        $reader = [IO.StreamReader]::new($response.RawContentStream)
        try {
            $index = $reader.ReadToEnd()
        } finally {
            $reader.Dispose()
        }
        $pattern = "(?m)^Package: openfoam($VersionPattern)$PackageSuffix\r?$"
        $available = @([regex]::Matches($index, $pattern) |
            ForEach-Object { $_.Groups[1].Value } | Sort-Object { [int]$_ } -Descending -Unique)
        if ($available.Count -eq 0) { throw 'Empty package list' }
    } catch {
        Write-Warning '公式パッケージ一覧を取得できませんでした。インストールする版を入力してください。'
    }

    $prompt = 'バージョン'
    if ($available.Count -gt 0) {
        Write-Host "Ubuntu 24.04 で選択できる版: $($available -join ', ')"
        $prompt = "バージョン [最新版 $($available[0])]"
    }
    while ($true) {
        $version = (Read-Host $prompt).Trim()
        if (-not $version -and $available.Count -gt 0) { return $available[0] }
        if ($version -cmatch "^($VersionPattern)$" -and
            ($available.Count -eq 0 -or $version -in $available)) { return $version }
        Write-Host '配布元のリリース番号を数字で入力してください。' -ForegroundColor Yellow
    }
}

function Select-OpenFoamConfiguration {
    Write-Host ''
    Write-Host 'インストールするOpenFOAMの系統を選択してください。'
    Write-Host '  1. Foundation版（openfoam.org）'
    Write-Host '  2. Keysight版   （openfoam.com / OpenCFD）'

    do {
        $editionChoice = (Read-Host '選択 [1]').Trim()
        if (-not $editionChoice) { $editionChoice = '1' }
    } until ($editionChoice -in @('1', '2'))

    if ($editionChoice -eq '1') {
        Write-Host ''
        $version = Select-OpenFoamVersion 'https://dl.openfoam.org/ubuntu' '[1-9][0-9]?'

        return [PSCustomObject]@{
            Edition       = 'Foundation'
            EditionLabel  = 'Foundation版'
            Version       = $version
            VersionLabel  = $version
            BaseName      = "OpenFOAM-Foundation-$version"
            Package       = "openfoam$version"
            Environment   = "/opt/openfoam$version/etc/bashrc"
            ProjectSuffix = $version
        }
    }

    Write-Host ''
    $version = Select-OpenFoamVersion 'https://dl.openfoam.com/repos/deb' '[0-9]{2}(?:06|12)' '-default'

    return [PSCustomObject]@{
        Edition       = 'Keysight'
        EditionLabel  = 'Keysight版'
        Version       = $version
        VersionLabel  = "v$version"
        BaseName      = "OpenFOAM-Keysight-v$version"
        Package       = "openfoam$version-default"
        Environment   = "/usr/lib/openfoam/openfoam$version/etc/bashrc"
        ProjectSuffix = "v$version"
    }
}

try {
    if ($env:WSL_MANAGER_DPAPI) {
        $secure = ConvertTo-SecureString -String $env:WSL_MANAGER_DPAPI
        $credentials = @{ UserName = $env:WSL_MANAGER_USER; Password = (ConvertFrom-SecureValue $secure)
                          PasswordDisplay = '（GUIで入力済み）'; ModeLabel = 'GUI設定' }
        Remove-Item Env:WSL_MANAGER_DPAPI
        Remove-Item Env:WSL_MANAGER_USER
        $secure.Dispose()
        if ($credentials.UserName -cnotmatch '^[a-z_][a-z0-9_-]{0,31}$' -or
            $credentials.UserName -in $ReservedLinuxUserNames) { throw 'Linuxユーザー名が無効です。' }
    } else {
        $credentials = Select-LinuxCredentials
    }
    $configuration = Select-OpenFoamConfiguration
    $BaseName = $configuration.BaseName
    $OpenFoamPackage = $configuration.Package
    $OpenFoamEtc = $configuration.Environment
    $OpenFoamLabel = "$($configuration.EditionLabel) $($configuration.VersionLabel)"
    $projectSuffix = $configuration.ProjectSuffix

    $linuxUser = $credentials.UserName
    $initialPassword = $credentials.Password
    $passwordDisplay = $credentials.PasswordDisplay

    Write-Host ''
    Write-Host '============================================================'
    Write-Host " OpenFOAM      : $OpenFoamLabel"
    Write-Host " Linuxユーザー : $linuxUser（$($credentials.ModeLabel)）"
    Write-Host " 初期パスワード: $passwordDisplay" -ForegroundColor Cyan
    Write-Host '============================================================'
    Write-Host 'このパスワードはログインおよびsudoで使用します。安全な場所に控えてください。'
    Write-Host 'インストール後は「passwd」コマンドで変更できます。'
    Write-Host ''
    $confirmation = (Read-Host '続行するには Enter、中止するには Q を入力').Trim()
    if ($confirmation -match '^(?i:q|quit)$') {
        Write-Host 'インストールを中止しました。'
        exit 2
    }

    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        throw 'wsl.exe が見つかりません。管理者のターミナルで「wsl --install --no-distribution」を実行し、Windowsを再起動してから再実行してください。'
    }

    Write-Host '[1/7] WSLの状態を確認しています...'
    $helpText = ((& wsl.exe --help 2>&1) -join "`n") -replace [char]0, ''
    if ($helpText -notmatch '(?m)--name\b') {
        Write-Host 'カスタム名に対応するためWSLを更新します...'
        & wsl.exe --update
        if ($LASTEXITCODE -ne 0) {
            throw 'WSLの更新に失敗しました。管理者のターミナルで「wsl --update」を実行し、必要ならWindowsを再起動してください。'
        }
        $helpText = ((& wsl.exe --help 2>&1) -join "`n") -replace [char]0, ''
        if ($helpText -notmatch '(?m)--name\b') {
            throw '現在のWSLは「--name」に対応していません。Windowsを再起動してから、このバッチを再実行してください。'
        }
    }

    $statusOutput = & wsl.exe --status 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw 'WSLを起動できません。管理者のターミナルで「wsl --install --no-distribution」を実行し、Windowsを再起動してから再実行してください。'
    }

    Write-Host '[2/7] 既存のWSL名と重複しない名前を選んでいます...'
    $installedNames = Get-InstalledWslNames
    $distributionName = $BaseName
    $suffix = 2
    while ($installedNames -contains $distributionName) {
        $distributionName = "$BaseName-$suffix"
        $suffix++
    }
    Write-Host "使用する名前: $distributionName"

    Write-Host '[3/7] Ubuntu 24.04 LTSをインストールしています...'
    & wsl.exe --install $UbuntuDistribution --name $distributionName --version 2 --no-launch
    if ($LASTEXITCODE -ne 0) {
        throw "Ubuntuのインストールに失敗しました (終了コード: $LASTEXITCODE)。"
    }

    Write-Host "[4/7] Linuxユーザー「$linuxUser」とパスワードを設定しています..."
    $quotedUser = "'$linuxUser'"
    Invoke-Wsl $distributionName @"
set -e
if id -u $quotedUser >/dev/null 2>&1; then
    echo '指定されたLinuxユーザー名は既存のシステムユーザーと重複しています。' >&2
    exit 45
fi
useradd --create-home --shell /bin/bash $quotedUser
apt-get update
DEBIAN_FRONTEND=noninteractive apt-get install -y sudo ca-certificates wget openssl software-properties-common
usermod -aG sudo $quotedUser
"@
    Set-WslUserPassword -Distribution $distributionName -UserName $linuxUser -Password $initialPassword

    Write-Host "[5/7] $($configuration.EditionLabel)の公式リポジトリを設定しています..."
    if ($configuration.Edition -eq 'Foundation') {
        Invoke-Wsl $distributionName @'
set -e
add-apt-repository -y universe
wget -qO /etc/apt/trusted.gpg.d/openfoam.asc https://dl.openfoam.org/gpg.key
rm -f /etc/apt/sources.list.d/*dl_openfoam_org*list
add-apt-repository -y "http://dl.openfoam.org/ubuntu main dev"
apt-get update
'@
    }
    else {
        Invoke-Wsl $distributionName @'
set -e
add-apt-repository -y universe
wget -qO /tmp/openfoam-add-debian-repo.sh https://dl.openfoam.com/add-debian-repo.sh
bash /tmp/openfoam-add-debian-repo.sh
rm -f /tmp/openfoam-add-debian-repo.sh
apt-get update
'@
    }

    Write-Host "[6/7] $OpenFoamLabel をインストールしています（時間がかかります）..."
    Invoke-Wsl $distributionName @"
set -e
if ! apt-cache show '$OpenFoamPackage' >/dev/null 2>&1; then
    echo '選択したバージョンのパッケージ ($OpenFoamPackage) はUbuntu 24.04向けリポジトリにありません。' >&2
    exit 44
fi
DEBIAN_FRONTEND=noninteractive apt-get install -y '$OpenFoamPackage'
"@

    Write-Host '[7/7] 初期設定と動作確認をしています...'
    Invoke-Wsl $distributionName @"
set -e
grep -qxF '. $OpenFoamEtc' /home/$linuxUser/.bashrc || printf '\n. $OpenFoamEtc\n' >> /home/$linuxUser/.bashrc
mkdir -p /home/$linuxUser/OpenFOAM/$linuxUser-$projectSuffix/run
chown -R $linuxUser`:$linuxUser /home/$linuxUser
printf '[boot]\nsystemd=true\n\n[user]\ndefault=%s\n' $linuxUser > /etc/wsl.conf
bash -lc '. $OpenFoamEtc && test -n "`$WM_PROJECT_VERSION" && test -n "`$WM_PROJECT_DIR" && command -v blockMesh >/dev/null && blockMesh -help >/dev/null 2>&1'
"@

    & wsl.exe --terminate $distributionName 2>$null

    Write-Host ''
    Write-Host '============================================================'
    Write-Host " $OpenFoamLabel のWSL環境を作成しました。"
    Write-Host " WSL名      : $distributionName"
    Write-Host " Linuxユーザー: $linuxUser"
    Write-Host " 初期パスワード: $passwordDisplay"
    Write-Host " 起動コマンド : wsl -d $distributionName"
    Write-Host ' 初回ログイン後に「passwd」でパスワードを変更してください。'
    Write-Host '============================================================'

    Write-Host ''
    if ($env:WSL_MANAGER_RESULT) {
        [IO.File]::WriteAllText($env:WSL_MANAGER_RESULT, $distributionName)
        exit 0
    }
    $launchChoice = (Read-Host 'インストールしたWSLを今すぐ起動しますか？ [y/N]').Trim()
    if ($launchChoice -match '^(?i:y|yes)$') {
        Write-Host "WSL「$distributionName」を起動します。終了するにはLinux側で exit を実行してください。"
        & wsl.exe --distribution $distributionName
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "WSLは終了コード $LASTEXITCODE で終了しました。インストール自体は完了しています。"
        }
    }
    else {
        Write-Host "起動しませんでした。後で「wsl -d $distributionName」で起動できます。"
    }
    exit 0
}
catch {
    Write-Host ''
    Write-Host "エラー: $($_.Exception.Message)" -ForegroundColor Red
    if ($distributionName -and ((Get-InstalledWslNames) -contains $distributionName)) {
        Write-Host "作成途中のWSL「$distributionName」は調査・再利用のため削除していません。"
        Write-Host "不要なら次のコマンドで削除できます: wsl --unregister $distributionName"
    }
    exit 1
}
