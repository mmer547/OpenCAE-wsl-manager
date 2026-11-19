# WSL Manager

Windows で WSL ディストリビューションを管理する日本語のデスクトップアプリです。

## 起動

Windows 10 / 11 に、現行の WSL と、Tcl/Tk を含む Windows 版 Python 3.9 以降を用意してください。ZIP を展開し、そのフォルダーで PowerShell から実行します。

```powershell
py -3 wsl_manager.py
```

WSL 自体を初めて有効にするときは、管理者の PowerShell で `wsl --install --no-distribution` を実行し、Windows の案内に従って再起動してください。

## 操作

- **インストール** で配布名を選択または入力します。インストール後に対象を選択し、**ターミナル** から初回セットアップを行えます。
- **インポート** で登録名、tar アーカイブ、空の保存先フォルダー、WSL バージョンを指定します。
- **エクスポート** で選択した環境を tar に保存します。既存ファイルを保護するため、新しい保存名を指定してください。
- **削除** では対象の登録名を再入力します。登録を解除すると、その環境のファイルも削除されます。
- **停止**、**既定に設定** は一覧で選択した環境に適用されます。外部で状態を変更した場合は **更新** を押してください。

各操作の入力条件、対応する WSL コマンド、エラー時の動作、検証状況は [機能仕様書](SPECIFICATION.md) に記載しています。

## CAE 環境の作成

x64 版 Windows、WSL 2、インターネット接続、環境用の空き容量が必要です。配布物を同じフォルダーに展開してください。

1. 一覧の上にあるプルダウンでソフトを一つ選び、**CAE 環境を作成** を押します。
2. 新しい登録名と専用の空フォルダーを指定します。作成中は画面下部に処理状況が表示されます。
3. 完了したら一覧で対象を選び、**ターミナル** を開きます。一般ユーザー `cae` で利用できます。

| ソフト | 標準の登録名 | 再開に使うスクリプト |
| --- | --- | --- |
| OpenFOAM Foundation 12 | `OpenFOAM-12` | `openfoam_setup.sh` |
| OpenLB 1.9r0 | `OpenLB-1.9r0` | `openlb_setup.sh` |

### OpenLB のサンプルを実行する

セットアップ時に CPU 逐次実行の設定で OpenLB と二次元ポアズイユ流れのサンプルをビルドします。初回はコンパイルに時間がかかります。作成後にターミナルで以下を実行してください。

```bash
cd ~/olb-1.9r0/examples/laminar/poiseuille2d
./poiseuille2d
```

### OpenFOAM を確認する

```bash
echo "$WM_PROJECT_VERSION"
foamRun -help
```

バージョン表示の期待値は `12` です。

### 途中で失敗した場合

登録前の失敗は通信と空フォルダーを確認して再実行します。登録後の失敗は **更新** で対象を確認し、PowerShell で以下を実行します。最初の2行には実際の登録名と表のスクリプト名を指定します。

```powershell
$name = "OpenLB-1.9r0"
$script = "openlb_setup.sh"
wsl -d $name -u root --exec bash "/root/$script"
if ($LASTEXITCODE -eq 0) { wsl --terminate $name }
```

スクリプトの転送自体が失敗した場合は、アプリのフォルダーで `cmd /c "wsl -d $name -u root --exec tee /root/$script < $script > nul"` を実行してから再開します。
