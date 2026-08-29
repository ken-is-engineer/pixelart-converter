# pixelart-converter

GIF を入力とし、MP4 / JPEG / PNG / GIF へ変換するデスクトップアプリケーション。ピクセルアート向けに、リサイズ時の画質劣化を抑えることを前提とする。

**現状: 計画フェーズ。** 実装コードはまだ含まない。要件・設計・タスク分解のみを公開している。

## 技術スタック

- 言語 / GUI: Python + PySide6
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
