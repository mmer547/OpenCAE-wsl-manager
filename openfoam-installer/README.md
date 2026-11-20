# OpenFOAM WSL インストーラー

> [!WARNING]
> 現在テスト中です。重要なデータが入った既存WSLとは分けて使用し、表示されたWSL名を確認してください。不具合報告へパスワードを記載しないでください。

`install-openfoam-wsl.bat` をダブルクリックすると、Ubuntu 24.04 LTS のWSL環境を新規作成し、選択したOpenFOAMをインストールします。`install-openfoam-wsl.ps1`は対話処理の本体なので、BATと同じフォルダーに置いたまま使用してください。

## 主な機能

- Foundation版とKeysight版（OpenCFD）の選択
- OpenFOAMバージョンの指定とパッケージ存在確認
- 既存WSLと衝突しない名前の自動採番
- Linuxユーザー名・パスワードの自動設定または手動入力
- インストール後の共通動作確認
- インストール完了後の任意起動

## 使い方

1. GitHubの「Code」からZIPをダウンロードして展開するか、リポジトリをcloneします。
2. `install-openfoam-wsl.bat`と`install-openfoam-wsl.ps1`が同じフォルダーにあることを確認します。
3. `install-openfoam-wsl.bat`をダブルクリックします。
4. 画面の案内に従ってユーザー設定、配布元、バージョンを選択します。

インストーラーは既存WSLを登録解除しません。途中で失敗した場合も、作成途中のWSLは調査のため残します。

起動後、次の2項目を対話形式で指定できます。

最初に、Linuxユーザー名とパスワードを手動入力するか確認します。

- Enter、`n`、`N`: 現在の自動設定を使用します。Windowsユーザー名を基にしたLinuxユーザー名と、20文字のランダム初期パスワードを設定します。
- `y`、`Y`、`yes`: Linuxユーザー名とパスワードを入力します。パスワードは確認のため2回入力し、画面には表示しません。

`root`や`daemon`など、Linuxでシステム用途に予約されているユーザー名は指定できません。自動設定の名前が予約名と重なる場合は、`user-`を付けた名前を使用します。

手動パスワードには長さや文字種の制限を設けていません。コロン（`:`）を含むパスワードも使用できます。ただし「パスワードなし」を防ぐため、空文字だけは設定できません。入力間違いを防ぐ確認入力は行います。

1. 配布元
   - Foundation版（openfoam.org）
   - Keysight版（openfoam.com / OpenCFD）
2. 配布元を選ぶと Ubuntu 24.04（amd64）向けの公式パッケージ一覧を取得します。Enter で一覧中の最新版、番号入力で指定版をインストールします。一覧を取得できない場合は番号を手入力できます。
   - Foundation版: `14`、`13`、`12`、`11`など
   - Keysight版: `2606`、`2512`、`2506`、`2412`など

入力したバージョンのパッケージがUbuntu 24.04向け公式リポジトリに存在するか、インストール前に確認します。

既存のWSL名は変更しません。例えばFoundation版14では`OpenFOAM-Foundation-14`、Keysight版v2606では`OpenFOAM-Keysight-v2606`を使用します。同名が既に存在する場合は、末尾に`-2`、`-3`のような連番を付けて空いている名前を自動的に選びます。

## 前提条件

- Windows 10 21H2以降、またはWindows 11
- WSL 2が利用可能であること
- インターネット接続
- OpenFOAMとParaView用の十分な空き容量

WSL自体が未導入の場合は、管理者として開いたターミナルで次を実行し、Windowsを再起動してください。

```powershell
wsl --install --no-distribution
```

## 起動

完了画面に表示された名前を指定します。例えば次のように起動します。

```powershell
wsl -d OpenFOAM-Foundation-14
```

OpenFOAMの環境設定はログイン時に自動で読み込まれます。Linuxユーザーには`sudo`権限を設定し、実行時にはパスワードを要求します。

Linuxユーザーには、インストールごとに生成した20文字のランダム初期パスワードを設定します。インストール開始前と完了時に対話画面へ表示されるので、安全な場所に控えてください。`sudo`実行時にもこのパスワードが必要です。

初回ログイン後は、次のコマンドでパスワードを変更することを推奨します。

```bash
passwd
```

インストール完了時には、OpenFOAM環境の読み込み、`WM_PROJECT_VERSION`、`WM_PROJECT_DIR`、および`blockMesh -help`を使って動作確認します。この確認方法はFoundation版とKeysight版の両方に対応しています。

インストール完了後、作成したWSLをすぐに起動するか確認します。`y`または`yes`を入力した場合だけ起動し、Enterまたは`n`では起動しません。デフォルトはNoです。

インストール中に失敗した場合、作成途中のWSLは自動削除しません。既存環境が削除されることはありません。

## 開発時の確認

インストールを実行しない静的チェックをWindows PowerShellで実行できます。

```powershell
.\tests\Test-Static.ps1
```

GitHub Actionsでも同じ検査を実行します。

## 不具合報告

WindowsとWSLのバージョン、選択した配布元・OpenFOAMバージョン、エラー全文を添えてください。パスワードやその他の機密情報は削除してください。詳しくは[CONTRIBUTING.md](CONTRIBUTING.md)を参照してください。

### 作成済みユーザーのパスワードを再設定する

パスワードが一致しない場合は、Windows側のPowerShellからrootとして`passwd`を起動できます。`<WSL名>`と`<Linuxユーザー名>`を実際の値へ置き換えてください。

```powershell
wsl -d <WSL名> -u root -- passwd <Linuxユーザー名>
```

新しいパスワードを2回入力した後、WSLを再起動します。

```powershell
wsl --terminate <WSL名>
wsl -d <WSL名>
```

## ライセンスと商標

このインストーラー自体のライセンスは公開前に決定予定です。OpenFOAM本体には各配布元のライセンスが適用されます。本プロジェクトはOpenFOAM Foundation、OpenCFD、Keysight Technologies、Canonical、Microsoftの公式プロジェクトではありません。
