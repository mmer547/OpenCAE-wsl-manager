# WSL Manager

Windows で WSL ディストリビューションを管理する日本語のデスクトップアプリです。

## 起動

Windows 10 / 11 に、現行の WSL と、Tcl/Tk を含む Windows 版 Python 3.9 以降を用意してください。ZIP を展開し、そのフォルダーで PowerShell から実行します。

```powershell
py -3 wsl_manager.py
```

WSL 自体を初めて有効にするときは、管理者の PowerShell で `wsl --install --no-distribution` を実行し、Windows の案内に従って再起動してください。

## 操作

- **インストール** で配布名を選択または入力します。同じ画面で Linux ユーザー名、パスワード、確認用パスワードを入力します。完了後は **ターミナル** でそのユーザーとして起動できます。
- **インポート** で登録名、tar アーカイブ、空の保存先フォルダー、WSL バージョンを指定します。
- **エクスポート** で選択した環境を tar に保存します。既存ファイルを保護するため、新しい保存名を指定してください。
- **削除** では対象の登録名を再入力します。登録を解除すると、その環境のファイルも削除されます。
- **停止**、**既定に設定** は一覧で選択した環境に適用されます。外部で状態を変更した場合は **更新** を押してください。

各操作の入力条件、対応する WSL コマンド、エラー時の動作、検証状況は [機能仕様書](SPECIFICATION.md) に記載しています。

## CAE 環境の作成

x64 版 Windows、WSL 2、インターネット接続、環境用の空き容量が必要です。ZIP はフォルダー構成を保ったまま展開してください。各ソフトのセットアップスクリプトは `scripts/cae/` にあります。

1. 必要なソフトすべてにチェックを入れ、**CAE 環境を作成** を押します。
2. 作成画面で Linux ユーザー名（初期値 `cae`）、パスワード、確認用パスワードを入力します。**OpenFOAM（配布元・版を選択）** を含まない場合は、同じ画面で新しい登録名と空の保存先フォルダーも指定します。
3. 選択したソフトが同じ環境に順にインストールされます。完了したら一覧で対象を選び、**ターミナル** を開きます。指定した Linux ユーザーで利用できます。

| ソフト | 標準の登録名 | 再開に使うスクリプト |
| --- | --- | --- |
| OpenFOAM Foundation（最新版） | `OpenFOAM-Foundation` | `openfoam_foundation_setup.sh` |
| OpenFOAM Keysight（最新版） | `OpenFOAM-Keysight` | `openfoam_keysight_setup.sh` |
| OpenLB 1.9r0 | `OpenLB-1.9r0` | `openlb_setup.sh` |
| Salome-Meca 2025.1 | `Salome-Meca-2025` | `salome_meca_setup.sh` |
| CalculiX | `CalculiX` | `calculix_setup.sh` |
| OpenCourant | `OpenCourant` | `opencourant_setup.sh` |
| OpenModelica | `OpenModelica` | `openmodelica_setup.sh` |
| FreeCAD | `FreeCAD` | `freecad_setup.sh` |
| TreeFOAM | `TreeFOAM` | `treefoam_setup.sh` |
| Netgen | `Netgen` | `netgen_setup.sh` |
| Gmsh | `Gmsh` | `gmsh_setup.sh` |
| ParaView | `ParaView` | `paraview_setup.sh` |
| Elmer FEM | `Elmer-FEM` | `elmer_setup.sh` |
| SU2 | `SU2` | `su2_setup.sh` |
| Code_Saturne | `Code-Saturne` | `code_saturne_setup.sh` |
| MBDyn | `MBDyn` | `mbdyn_setup.sh` |

### OpenFOAM の配布元・バージョンを選ぶ

**OpenFOAM（配布元・版を選択） → CAE 環境を作成** を選びます。

1. GUI で Linux ユーザー名とパスワードを入力して作成を開始すると、専用コンソールが開きます。
2. Foundation または Keysight（OpenCFD）を選びます。配布元を選ぶと Ubuntu 24.04（amd64）向けの公式パッケージ一覧を取得します。Enter で一覧中の最新版、番号入力で指定版をインストールします。一覧を取得できない場合は番号を手入力できます。
3. 続行すると Ubuntu 24.04 LTS の WSL 2 を作成します。登録名が重複すると `-2`、`-3` と自動採番されます。設定したユーザーで sudo を使えます。
4. OpenFOAM の検証が完了すると、マネージャーが同じ登録名の環境に残りのソフトを自動で導入します。

保存場所は WSL が管理します。自動で最新版を入れるには、メイン画面の **OpenFOAM Foundation（最新版）** または **OpenFOAM Keysight（最新版）** にチェックを入れます。両方を選ぶと同じ環境に導入し、通常のターミナルでは先に設定した版を読み込みます。[対話インストーラーの詳細](openfoam-installer/README.md)

### Salome-Meca の取得と起動

ダイアログの **公式配布ページ** を開き、2025 版の Linux 用 Singularity イメージ（約 5.34 GB）を選びます。配布元から取得した SIF ファイルの HTTPS 直接リンクを貼り付けるか、**参照** で取得済みの `.sif` を選択します。Windows 上のキャッシュと WSL 内のコピーに、それぞれイメージ 1 個分の空き容量が必要です。[公式配布ページ](https://open-simulation-center.org/en/downloads/code_aster/SALOME_MECA/2025)

通信が切れた場合は最大 5 回自動で再接続します。取得が止まったら、同じソフトを選んで **CAE 環境を作成** をもう一度実行してください。リンクの期限が切れた場合は新しい直接リンクを指定します。配布元が範囲取得に対応していれば保存済みの位置から再開します。取得状況は MiB 単位で画面下部に表示されます。

ダウンロードが完了してから WSL を登録します。完了したイメージも Windows の `%LOCALAPPDATA%\WSL-Manager\Salome-Meca` に保持されます。構築後は WSLg 対応の Windows でその環境の **ターミナル** を開き、次を実行します。

```bash
cd ~
salome-meca --soft
```

### OpenLB のサンプルを実行する

セットアップ時に CPU 逐次実行の設定で OpenLB と二次元ポアズイユ流れのサンプルをビルドします。初回はコンパイルに時間がかかります。作成後にターミナルで以下を実行してください。

```bash
cd ~/olb-1.9r0/examples/laminar/poiseuille2d
./poiseuille2d
```

### OpenFOAM を確認する

```bash
echo "$WM_PROJECT_VERSION"
blockMesh -help
```

両方を導入した場合、Keysight 版の設定ファイルは `/usr/lib/openfoam/openfoam<版番号>/etc/bashrc`、Foundation 版は `/opt/openfoam<版番号>/etc/bashrc` です。

### 途中で失敗した場合

登録前の失敗は通信と空フォルダーを確認して再実行します。ユーザー設定が完了する前に失敗した場合は、別の登録名と空フォルダーを指定して新規作成できます。ユーザー設定後にソフトの導入が失敗した場合は **更新** で対象を確認し、PowerShell で以下を実行します。最初の行には実際の登録名を指定します。完了済みのスクリプトをスキップして残りを順に実行します。

```powershell
$name = "CAE-Workspace"
wsl -d $name -u root --exec bash /root/resume.sh
if ($LASTEXITCODE -eq 0) { wsl --terminate $name }
```

旧版で作成した環境は、表にあるスクリプトを個別に実行します（例 `wsl -d OpenLB-1.9r0 -u root --exec bash /root/openlb_setup.sh`）。

## 追加の CAE ソフトを使う

一覧から対象を選んで **CAE 環境を作成** を押します。作成後はその環境の **ターミナル** を開きます。以下の入力ファイル名は自分の解析ケースに読み替えてください。GUI の表示には WSLg が必要です。

| ソフト | 導入内容 | 起動例 |
| --- | --- | --- |
| CalculiX | Ubuntu の CCX と CGX | `ccx -i model` |
| OpenCourant | 公式 Linux x86-64 版（2026-10-11、OpenMP） | `starter_linux64_gf -version`、`engine_linux64_gf -version` |
| OpenModelica | 公式 stable 版のコンパイラ、OMEdit、標準ライブラリ | `OMEdit` または `omc --version` |
| FreeCAD | FreeCAD メンテナーの stable PPA 版 | `freecad` |
| TreeFOAM | TreeFoam 3.38 日本語版、OpenFOAM Foundation 12、ParaView | `treefoam` |
| Netgen | Ubuntu のメッシュ生成 GUI と Python バインディング | `netgen` |
| Gmsh | Ubuntu パッケージ | `gmsh` |
| ParaView | Ubuntu パッケージ | `paraview` |
| Elmer FEM | Elmer CSC の Ubuntu 24.04 用 PPA | `ElmerSolver case.sif` |
| SU2 | 公式 8.6.0 OpenMP 版 | `SU2_CFD case.cfg` |
| Code_Saturne | 公式 9.0.2 ソース、Qt5 GUI | `code_saturne gui` |
| MBDyn | 公式 Git ソース（767fd42e） | `mbdyn -f model.mbd` |

Code_Saturne と MBDyn は WSL 内でコンパイルするため、初回の環境作成に時間がかかります。長いビルドの途中でエラーが出た場合も、上記の「途中で失敗した場合」の手順で再実行できます。

TreeFOAM のケース用フォルダーは `~/OpenFOAM/run` です。PyFoam を使うログ監視と DEXCS 拡張はこの構成の対象外です。TreeFOAM の再開時には、同じ環境の `/root/openfoam_setup.sh` も使用します。
