# Windows での LGPL FFmpeg ビルド

ロジックを二重に持たないよう、Windows でも [`build_ffmpeg_lgpl.sh`](build_ffmpeg_lgpl.sh) をそのまま使う。MSYS2 が bash を提供するので、PowerShell 用の別スクリプトは用意していない。フラグの出所は [`vendor/ffmpeg/build_flags.txt`](../vendor/ffmpeg/build_flags.txt) の `[common]` + `[windows]`。

## 前提

1. [MSYS2](https://www.msys2.org/) をインストールする
2. **MSYS2 MINGW64** シェル（`msys2.exe` ではなく `mingw64.exe`）を開く
3. ツールチェーンを入れる

```bash
pacman -S --needed base-devel git curl diffutils \
  mingw-w64-x86_64-toolchain mingw-w64-x86_64-nasm
```

`x264` 関連（`mingw-w64-x86_64-x264` など）は入れない。仮に入っていても `--disable-autodetect` で拾わないが、環境から消しておく方が確実。

## ビルド

```bash
cd /c/path/to/pixelart-converter
scripts/build_ffmpeg_lgpl.sh --check-flags --platform windows   # フラグ確認だけ
scripts/build_ffmpeg_lgpl.sh --platform windows                 # ビルドして vendor/ffmpeg/windows/ へ
```

MSYS2 の `uname -s` は `MINGW64_NT-...` なので `--platform` は省略してもよいが、明示した方が事故がない。

Media Foundation を有効にするため、`mfapi.h` / `mfidl.h` を含む mingw-w64 のヘッダが必要になる。`--enable-mediafoundation` で configure が失敗する場合は toolchain パッケージの更新（`pacman -Syu`）を先に試す。

## 検証

```bash
vendor/ffmpeg/windows/ffmpeg.exe -version | grep -i -e libx264 -e '--enable-gpl'   # 何も出ないこと
vendor/ffmpeg/windows/ffmpeg.exe -hide_banner -encoders | grep h264_mf             # 出ること
```

`h264_mf` は実機の GPU / ドライバに依存する。configure が通っても実行時に使えないことがあるため、短いテストエンコードでの確認は T2-3（EncoderResolver）で行う。

## 依存 DLL

MINGW64 でビルドした `ffmpeg.exe` は `libwinpthread-1.dll` などに動的リンクすることがある。`ldd vendor/ffmpeg/windows/ffmpeg.exe` で `/mingw64/bin` 配下への依存が残っていないか確認し、残る場合は該当 DLL を同じディレクトリへ置くか、静的リンクするようツールチェーン側を調整する。PyInstaller での同梱は Phase 5（T5-2）。
