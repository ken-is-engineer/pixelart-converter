# パッケージング

macOS の署名なしローカル `.app` と Windows の onedir `.exe` フォルダ。

## Chosen mode: onedir

PyInstaller の **onedir**（`COLLECT`；macOS は `BUNDLE` で `.app`）を採用する。`packaging/macos.spec` と `packaging/windows.spec` は onefile ではなく onedir で書かれている。

| 観点 | onedir を選んだ理由 |
|------|---------------------|
| 起動時間 | onefile は起動時に一時ディレクトリへ展開するため、onedir の方が起動が速い |
| Qt / LGPL | PySide6 の `.dylib` / `.dll` を動的リンクのまま同梱しやすく、LGPL 上の扱いが明確。詳細は [lgpl-qt.md](lgpl-qt.md) |
| Windows AV | onefile の「展開 → 実行」パターンはウイルス対策ソフトの誤検知が起きやすい。onedir の方がリスクが低い（一次判断） |

**ウイルス誤検知の確認:** 本タスク（T5-3）では Windows 実機上での AV スキャンは未実施（開発環境が macOS のため）。`dist/pixelart-converter/` をビルドした Windows マシンで、Defender 等による一次確認は **pending** とする。

## macOS（署名なし・ローカル起動）

成果物は **onedir** の `pixelart-converter.app`（PyInstaller の `COLLECT` + `BUNDLE`）。onefile にはしない。GUI は `python -m pixelart_converter` と同じ `src/pixelart_converter/__main__.py`。同梱 ffmpeg は `vendor/ffmpeg/macos/ffmpeg` を `_MEIPASS/vendor/ffmpeg/macos/` へ入れる。Qt は **PySide6-Essentials**（フルの PySide6 メタパッケージは不要）。

### このマシンではまだ .app を作れない

T5-1 の成果は spec・ビルドスクリプト・本ドキュメントである。**変換が通る `.app` 自体は、このチェックアウトではまだ作れない。** 理由は次の二つで、両方揃うまで PyInstaller を走らせない。

1. `vendor/ffmpeg/macos/ffmpeg` が未ビルド（`scripts/build_ffmpeg_lgpl.sh`。バイナリは git に入れない）
2. 空きディスクが 5 GB 未満。PyInstaller / Qt の展開でディスクを埋め尽くすので、空きを確保するまで `pip install pyinstaller` も実行しない

クリーンな Mac で Python なしに変換が通る、が完了条件だが、上記が解消されるまでブロックされている。

### ビルド（空きと ffmpeg があるマシンで）

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install pyinstaller
scripts/build_ffmpeg_lgpl.sh          # vendor/ffmpeg/macos/ffmpeg を作る
scripts/build_macos_app.sh            # dist/pixelart-converter.app
```

`scripts/build_macos_app.sh` は ffmpeg が無いとき、または空きが 5 GB 未満のとき、PyInstaller を起動せずに失敗する。閾値は `PIXELART_APP_MIN_FREE_MB`（既定 5120）。

### 署名なしで開く（Gatekeeper）

Developer ID 署名も公証もしていない。同じ Mac で今ビルドした `.app` は、多くの場合そのまま開く。

```bash
open dist/pixelart-converter.app
```

別の Mac へコピーした場合、Gatekeeper が「開発元を確認できない」と止める。そのときは Finder で **Control-クリック → 開く** を一度行う。quarantine 属性が付いているときは次でも外せる。

```bash
xattr -dr com.apple.quarantine dist/pixelart-converter.app
```

システム設定の「このまま開く」でも同様。署名・公証の将来方針は [signing.md](signing.md)（T5-4。本フェーズ必須ではない）。

変換には同梱 ffmpeg だけを使う。システム PATH の `ffmpeg` や Homebrew の GPL ビルドへは切り替えない。

## Windows（onedir フォルダ）

成果物は **onedir** の `dist/pixelart-converter/`（PyInstaller の `COLLECT`）。onefile にはしない。GUI は `python -m pixelart_converter` と同じ `src/pixelart_converter/__main__.py`。同梱 ffmpeg は `vendor/ffmpeg/windows/ffmpeg.exe` を `_MEIPASS/vendor/ffmpeg/windows/` へ入れる。Qt は **PySide6-Essentials**（フルの PySide6 メタパッケージは不要）。

### この Mac では .exe を作れない

T5-2 の成果は spec・ビルドスクリプト・本ドキュメントである。**変換が通る Windows バンドル自体は、この macOS チェックアウトでは作れない。** PyInstaller はターゲット OS 上でビルドする必要がある。Windows 実機または Windows CI で `scripts/build_windows.ps1` を走らせる。

クリーンな Windows で Python なしに変換が通る、が完了条件だが、次が揃うまでブロックされている。

1. `vendor/ffmpeg/windows/ffmpeg.exe` が未ビルド（MSYS2 MINGW64 で `scripts/build_ffmpeg_lgpl.sh --platform windows`。バイナリは git に入れない）
2. 空きディスクが 5 GB 未満。PyInstaller / Qt の展開でディスクを埋め尽くすので、空きを確保するまで `pip install pyinstaller` も実行しない

### ビルド（Windows 実機または CI で）

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .
pip install pyinstaller
# MSYS2 MINGW64 で scripts/build_ffmpeg_lgpl.sh --platform windows
scripts\build_windows.ps1            # dist\pixelart-converter\
```

`scripts/build_windows.ps1` は ffmpeg が無いとき、または空きが 5 GB 未満のとき、PyInstaller を起動せずに失敗する。閾値は `PIXELART_APP_MIN_FREE_MB`（既定 5120）。

### 起動

```powershell
dist\pixelart-converter\pixelart-converter.exe
```

署名していないため SmartScreen が初回起動を止めることがある。**詳細情報 → 実行** で通す。コード署名の将来方針は [signing.md](signing.md)（T5-4。本フェーズ必須ではない）。

MINGW64 でビルドした ffmpeg が `libwinpthread-1.dll` 等に依存している場合、同じ `vendor/ffmpeg/windows/` ディレクトリへ DLL を置いてから PyInstaller を走らせる（`scripts/build_ffmpeg_lgpl_windows.md` 参照）。

変換には同梱 ffmpeg だけを使う。システム PATH の `ffmpeg` や GPL 入りの配布ビルドへは切り替えない。
