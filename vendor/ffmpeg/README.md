# 同梱 FFmpeg（LGPL ビルド）

このディレクトリには、アプリに同梱する FFmpeg 実行ファイルを置く。**GPL ビルドと `libx264` 入りのバイナリは置かない。**根拠は [requirements.md §5.2](../../docs/requirements.md)、配置方針は [design.md §3](../../docs/design.md)。

`ffmpeg` はライブラリとしてリンクせず、subprocess からのみ呼ぶ（requirements N-3）。

## 対象バージョン

| 項目 | 値 |
|------|-----|
| バージョン | **7.1.1**（git タグ `n7.1.1`） |
| ソース | <https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz> |
| ライセンス | LGPL v2.1 or later（`--enable-version3` を付けないため v3 のみのコンポーネントは入らない） |

バージョンとソース URL は [`build_flags.txt`](build_flags.txt) に書いてあり、ビルドスクリプトはそこから読む。上げるときは §バージョンを上げる を参照。

## configure フラグ

以下は [`build_flags.txt`](build_flags.txt) の内容そのまま。この 1 ファイルがビルドスクリプト・本 README・テストの共通の元になっている（テストが一致を検証する）。

<!-- BEGIN build_flags.txt -->

```text
# pixelart-converter: FFmpeg configure flags (LGPL, no GPL, no x264).
#
# This file is the single source of truth. scripts/build_ffmpeg_lgpl.sh reads
# it, vendor/ffmpeg/README.md embeds it, and tests/test_ffmpeg_build_flags.py
# asserts that no GPL-triggering flag ever appears here.
#
# Syntax: 'key=value' settings, '[section]' headers, '#' comments, and one
# configure flag per line. Flag order is preserved.

version=7.1.1
source_url=https://ffmpeg.org/releases/ffmpeg-7.1.1.tar.xz

[common]
--disable-gpl
--disable-nonfree
--disable-version3
--disable-autodetect
--disable-network
--disable-avdevice
--disable-doc
--disable-debug
--disable-programs
--enable-ffmpeg
--enable-ffprobe
--enable-zlib

[macos]
--enable-pthreads
--enable-videotoolbox
--enable-encoder=h264_videotoolbox

[windows]
--enable-w32threads
--enable-mediafoundation
--enable-encoder=h264_mf
```

<!-- END build_flags.txt -->

実際の configure は `[common]` + プラットフォーム別セクション、に `--prefix` を足したものになる。

```bash
./configure --prefix=<install-dir> \
  --disable-gpl --disable-nonfree --disable-version3 --disable-autodetect \
  --disable-network --disable-avdevice --disable-doc --disable-debug \
  --disable-programs --enable-ffmpeg --enable-ffprobe --enable-zlib \
  --enable-pthreads --enable-videotoolbox --enable-encoder=h264_videotoolbox
```

### なぜこのフラグなのか

| フラグ | 理由 |
|--------|------|
| `--disable-gpl` | GPL コンポーネントを一切引き込まない。既定値でもあるが、意図として明示する |
| `--disable-nonfree` | 再配布不可のビルドを作らない |
| `--disable-version3` | LGPL v2.1 or later に留める。v3 のみの外部ライブラリを混ぜない |
| `--disable-autodetect` | **これが本質。**ビルドマシンに `x264` 等が入っていても外部ライブラリを自動検出しない。必要なものだけ後続の `--enable-*` で足す |
| `--disable-network` | ローカルファイル変換のみなのでプロトコル群は不要 |
| `--disable-avdevice` | キャプチャデバイス入力は使わない |
| `--disable-doc` / `--disable-debug` | 成果物サイズを削る |
| `--disable-programs` → `--enable-ffmpeg` `--enable-ffprobe` | `ffplay` を作らない（SDL 依存を持ち込まない）。フレーム数取得に使う `ffprobe` は同じビルドから取る（design §5.3） |
| `--enable-zlib` | PNG 出力に必要。`--disable-autodetect` で落ちるので明示する |
| `--enable-videotoolbox` / `--enable-mediafoundation` | OS ベンダーの HW H.264 エンコーダー。GPL と特許を OS 側に委ねる（requirements §5.3） |
| `--enable-encoder=h264_videotoolbox` / `h264_mf` | エンコーダーが取れない環境で configure を失敗させ、静かに欠けたバイナリが出来るのを防ぐ |

`--enable-libx264` と `--enable-gpl` は**書かない**。`libopenh264` は T2-4 で **非採用**（プロファイル未検証、configure に含めない）。プローブで見えても EncoderResolver は選択しない。将来採用する場合のみ `--enable-libopenh264` を `[common]` に足す（BSD 系ライセンスなので LGPL のままでいられる）。

## ビルド手順

### macOS

```bash
scripts/build_ffmpeg_lgpl.sh --check-flags     # フラグ確認だけ（ビルドしない）
scripts/build_ffmpeg_lgpl.sh                   # 実際にビルドして vendor/ffmpeg/macos/ へ入れる
```

スクリプトは configure フラグに GPL / x264 系が混ざっていたら実行を拒否し、ビルド後の `ffmpeg -version` も検査する。ソースの展開とビルドには数 GB の空きが要るため、空き容量が足りないときも実行を止める。

### Windows

MSYS2 上で同じスクリプトを使う。手順は [`scripts/build_ffmpeg_lgpl_windows.md`](../../scripts/build_ffmpeg_lgpl_windows.md)。

## 検証

完了条件は「`ffmpeg -version` に libx264 が出ないこと」。

```bash
vendor/ffmpeg/macos/ffmpeg -version | grep -i -e libx264 -e '--enable-gpl'   # 何も出ないこと
vendor/ffmpeg/macos/ffmpeg -hide_banner -encoders | grep -i x264             # 何も出ないこと
vendor/ffmpeg/macos/ffmpeg -hide_banner -encoders | grep h264_videotoolbox   # 出ること
vendor/ffmpeg/macos/ffmpeg -L                                                # LGPL である旨が出ること
```

バイナリがある環境では `python -m unittest discover -s tests` の `test_ffmpeg_binary.py` が同じ検査を自動で行う（バイナリが無ければ skip）。

## 配置

```
vendor/ffmpeg/
  macos/ffmpeg          macos/ffprobe          # arm64（必要なら x86_64 と lipo で universal）
  windows/ffmpeg.exe    windows/ffprobe.exe
  README.md  build_flags.txt                   # ← git で追跡するのはこの 2 つと .gitkeep だけ
```

ビルドスクリプトは実行ファイルに加えて、ソースツリーの `COPYING.LGPLv2.1` / `LICENSE.md` と、ビルド元 URL・sha256・configure 行を書いた `BUILD-INFO.txt` を同じディレクトリに置く。

開発時はこのパスを、梱包後は PyInstaller の `_MEIPASS` 配下を見る。解決の実装は T2-2（`conversion/binary.py`）。システム PATH の `ffmpeg` にはフォールバックしない — ライセンスの分からないバイナリを拾わないため。

### バイナリをコミットしない理由

`vendor/ffmpeg/**` は `.gitignore` で無視し、README・`build_flags.txt`・`.gitkeep` だけを追跡している。実行ファイルはローカルまたは CI のビルド成果物として扱う。

1. **サイズ** — 1 プラットフォーム 30–70 MB。git 履歴に入れると clone が重くなり、後から消せない
2. **ライセンス出所** — コミットされたバイナリは誰がどのフラグでビルドしたか追えなくなる。手順（本 README + `build_flags.txt`）を追跡し、バイナリは毎回そこから再現する方が LGPL の説明責任を果たしやすい

## 公開ビルドを流用しない

| 入手先 | 状態 |
|--------|------|
| gyan.dev の "full" / "essentials" | GPL + libx264。**使用不可** |
| BtbN の win64 gpl ビルド | 名前のとおり GPL。**使用不可**（`*-lgpl-*` 版のみ検討可） |
| Homebrew の `ffmpeg` bottle | 既定で `--enable-gpl --enable-libx264`。**同梱不可**（ローカル開発の確認用途に留める） |
| evermeet.cx など汎用配布 | 多くが GPL。同梱するなら configuration 行を確認する |

LGPL 明記のビルドを使う場合でも、同梱前に必ず `ffmpeg -version` の configuration 行を確認し、そのビルドの入手元とバージョンを `BUILD-INFO.txt` に残す。

## ソース提供義務（LGPL）

LGPL のバイナリを配布する以上、対応するソースの入手方法を提供する義務がある（requirements N-5 / §5.2、tasks T6-2）。

- 同梱するバイナリと**同じバージョン・同じ改変状態**のソースを指すこと。上記の公式リリース URL をそのまま使い、パッチを当てたらパッチも配布する
- 配布物に本 README 相当の内容（バージョン、configure フラグ、ソース URL）とライセンス全文を含める
- FFmpeg 側のリンクが将来切れた場合に備え、リリース時のソース tarball をアーカイブしておく

## バージョンを上げる

1. `build_flags.txt` の `version` と `source_url` を更新する
2. 本 README の埋め込みブロックと「対象バージョン」表を同じ内容に更新する（テストが一致を検証するので、ずれると落ちる）
3. macOS / Windows で再ビルドし、`-version` の検証を通す
4. 配布済みバージョンのソース入手手段は残しておく
