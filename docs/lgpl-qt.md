# Qt / PySide6 と LGPL 動的リンク（T6-3）

PySide6（Qt）は **LGPL v3** ライセンスである。自社コードをプロプライエタリのまま配布するには、Qt を **動的リンク** し、利用者が Qt ライブラリを差し替え可能な状態を維持する必要がある（[requirements.md](requirements.md) §5.1）。

## 自社コードは Qt をコンパイル時にリンクしない

このプロジェクトは **Python のみ** で、ネイティブ拡張や C/C++ ソースは持たない。GUI は実行時に `import PySide6` で PySide6-Essentials（Qt バインディング）を読み込む。自社コードが Qt を **静的リンク** したり、ビルド時に Qt ヘッダへリンクしたりすることはない。

## onedir + COLLECT が Qt を共有ライブラリとして同梱する

PyInstaller の **onedir** 方式（`packaging/macos.spec` / `packaging/windows.spec`）では:

1. `EXE(..., exclude_binaries=True)` — 実行ファイル本体だけを作り、バイナリ類は別に集める
2. `COLLECT(exe, a.binaries, ...)` — PySide6 / Qt の `.dylib`（macOS）や `.dll`（Windows）を **共有ライブラリのまま** バンドルへコピーする
3. macOS では `BUNDLE(coll, ...)` で `.app` にまとめる

PyInstaller は PySide6 パッケージから Qt の共有ライブラリを収集し、onedir フォルダ（macOS では `.app/Contents/Frameworks/` 等）に配置する。Qt は自社バイナリに **埋め込まれ（静的リンク）ない**。

## 利用者による Qt ライブラリの差し替え（理論上）

onedir 成果物では Qt / PySide6 の `.dylib` / `.dll` がファイルとして存在するため、**理論上** 利用者は LGPL の範囲で同名の共有ライブラリを差し替えられる。差し替え後もアプリが起動・動作するかは、ABI 互換性に依存する。

| 方式 | Qt 共有ライブラリの扱い | 差し替えのしやすさ |
|------|---------------------------|-------------------|
| **onedir（採用）** | `COLLECT` で `.dylib` / `.dll` がバンドル内に個別ファイルとして残る | ファイルを置き換え可能 |
| **onefile（不採用）** | 単一実行ファイル内にアーカイブされ、起動時に一時ディレクトリへ展開 | 差し替えが困難。LGPL 上の「差し替え可能」要件を満たしにくい |

onefile を採用しない理由の一つが、この LGPL 動的リンク前提の維持である（起動時間・AV 誤検知の理由は [packaging.md](packaging.md) を参照）。

## 梱包後の確認（pending）

**現時点ではビルド済み `.app` / onedir フォルダが存在しない** ため、梱包後の実物に対する次の確認は **未実施（pending）** である:

- バンドル内に `Qt6Core` / `libshiboken` / `PySide6` 関連の `.dylib` / `.dll` が個別ファイルとして存在すること
- 自社実行ファイル（`pixelart-converter` / `.exe`）がそれら共有ライブラリへ **動的** に依存していること（`otool -L` / `dumpbin /dependents` 等）
- 静的リンクされた Qt シンボルが自社バイナリに含まれていないこと

ffmpeg および空きディスクの条件が揃い、PyInstaller ビルドが成功した時点で上記を実施する。それまでは、spec・ビルドスクリプト・本ドキュメントおよび `tests/test_dynamic_linking_packaging.py` で **onedir / 非 onefile / 非静的リンク方針** を CI 上で固定する。

## 関連ファイル

| ファイル | 役割 |
|----------|------|
| `packaging/macos.spec` | onedir + `COLLECT` + `BUNDLE` |
| `packaging/windows.spec` | onedir + `COLLECT` |
| `scripts/build_macos_app.sh` | `--onefile` なしで PyInstaller 実行 |
| `scripts/build_windows.ps1` | 同上 |
| `tests/test_dynamic_linking_packaging.py` | spec / ビルドスクリプトの onedir 固定テスト |
