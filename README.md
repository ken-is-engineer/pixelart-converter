# pixelart-converter

GIF を入力とし、MP4 / JPEG / PNG / GIF へ変換するデスクトップアプリケーション。ピクセルアート向けに、リサイズ時の画質劣化を抑えることを前提とする。

## 開発環境

Python 3.11 以上が必要です。空のメインウィンドウを起動できます（変換機能は未実装）。

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python -m pixelart_converter
```

ヘッドレス（CI / オフスクリーン）でウィンドウ生成だけ確認する場合:

```bash
QT_QPA_PLATFORM=offscreen python -m pixelart_converter --smoke
```

または環境変数でも同じ動作になります。

```bash
PIXELART_SMOKE=1 QT_QPA_PLATFORM=offscreen python -m pixelart_converter
```

ウィンドウを出して直後に終了し、成功時の終了コードは 0 です。`python -m unittest discover -s tests` でも同じスモークを実行できます。

## 技術スタック

- 言語 / GUI: Python + PySide6（実行時依存は `PySide6-Essentials`。Addons は空ウィンドウでは不要）
- 変換エンジン: FFmpeg（subprocess 経由。ライブラリとして直接リンクしない）
- パッケージング: PyInstaller（macOS `.app` / Windows `.exe`）

## ドキュメント

| 文書 | 内容 |
|------|------|
| [docs/requirements.md](docs/requirements.md) | 機能要件、非機能要件、ライセンス方針 |
| [docs/design.md](docs/design.md) | アーキテクチャ、UI、変換パイプライン、同梱方針 |
| [docs/tasks.md](docs/tasks.md) | 実装フェーズと完了条件 |

## ライセンス

自社コードのライセンスは未選択（All Rights Reserved）。第三者コンポーネント（PySide6: LGPL v3、FFmpeg: LGPL ビルド、Pillow: MIT-CMU、PyInstaller: GPL + linking exception）の条件は [docs/requirements.md](docs/requirements.md) を参照。

FFmpeg は **LGPL ビルドのみ**を同梱する。`libx264` は組み込まない。
