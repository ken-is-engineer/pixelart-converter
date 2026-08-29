# パッケージング

macOS の署名なしローカル `.app` から書く。Windows の `.exe` 梱包は T5-2。

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

システム設定の「このまま開く」でも同様。署名・公証は T5-4（本フェーズ必須ではない）。

変換には同梱 ffmpeg だけを使う。システム PATH の `ffmpeg` や Homebrew の GPL ビルドへは切り替えない。
