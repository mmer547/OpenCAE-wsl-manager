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

## OpenFOAM 環境の作成

x64 版 Windows、WSL 2、インターネット接続、環境を保存できる空き容量が必要です。アプリと同じフォルダーに `openfoam_setup.sh` を置いて起動してください。

1. **OpenFOAM 環境を作成** を押し、新しい登録名（初期値 `OpenFOAM-12`）と専用の空フォルダーを指定します。
2. 完了したら一覧でその名前を選択し、**ターミナル** を開きます。一般ユーザー `cae` の Bash で OpenFOAM Foundation 12 が読み込まれます。
3. 次のコマンドでバージョンとソルバーを確認できます。

```bash
echo "$WM_PROJECT_VERSION"
foamRun -help
```

バージョン表示の期待値は `12` です。環境を別の PC に移す場合は、一覧からエクスポートした tar を移行先で WSL 2 としてインポートします。

### 途中で失敗した場合

登録前の失敗は通信と空フォルダーを確認して作成を再実行します。登録後の失敗は **更新** で対象を確認し、PowerShell で以下を実行します。登録名は実際に指定した名前に読み替えてください。スクリプトの転送自体が失敗した場合は、アプリのフォルダーで `cmd /c "wsl -d OpenFOAM-12 -u root --exec tee /root/openfoam_setup.sh < openfoam_setup.sh > nul"` を先に実行してください。

```powershell
wsl -d OpenFOAM-12 -u root --exec bash /root/openfoam_setup.sh
# 上の処理が成功したら、次回起動時に既定ユーザーを反映する
wsl --terminate OpenFOAM-12
```
