# 手動テスト観点（T6-4）

変換パイプライン・UI・梱包の確認項目。各項目に **検証方法**（単体テストで argv / モックまで固定できるか、実 ffmpeg / 実 `.app` / Windows 実機が必要か）と **状態** を付ける。

**凡例**

| 記号 | 意味 |
|------|------|
| ✅ automated | 単体テストでカバー済み（CI で再現可能） |
| ⏳ pending | 未実施。下記 GitHub issue を参照 |
| — | 本チェックアウトでは実施不可（ffmpeg 未ビルド・空き 2 GB・Windows なし） |

**このマシンでのウォークスルー（2026-08-29）:** `python -m unittest discover -s tests` → 158 passed, 4 skipped。`vendor/ffmpeg/macos/ffmpeg` なし、空きディスク ~2 GB、Windows 環境なし。視覚・エンコード・梱包後確認はすべて pending。UI / argv / エラー分類 / キャンセル / オプション排他は automated。

## 未達の追跡 issue（グループ化）

| テーマ | Issue |
|--------|-------|
| 同梱 FFmpeg ビルド + 変換の目視・再生確認 | [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) |
| macOS `.app` ビルドと Python なし起動 | [#29](https://github.com/ken-is-engineer/pixelart-converter/issues/29) |
| Windows onedir + Defender 一次確認 | [#30](https://github.com/ken-is-engineer/pixelart-converter/issues/30) |
| 梱包後 Qt 動的リンク・差し替え確認 | [#31](https://github.com/ken-is-engineer/pixelart-converter/issues/31) |

コード署名・公証は [#23](https://github.com/ken-is-engineer/pixelart-converter/issues/23)（T5-4）。本チェックリストでは重複起票しない。

---

## 1. 出力形式 — MP4

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 1.1 | ループ回数（N 回再生） | argv: **unit** / 再生: **ffmpeg + HW エンコーダー** | ✅ automated / ⏳ visual | `tests/test_mp4_command.py`, `test_mp4_service.py`, `test_main_window_options.py` |
| 1.2 | 秒数指定（不足分は GIF ループ） | argv: **unit** / 長さ: **ffmpeg + HW** | ✅ automated / ⏳ visual | `tests/test_mp4_command.py`（`-stream_loop -1` + `-t`） |
| 1.3 | ループ回数と秒数の排他（モデル・UI） | **unit** | ✅ automated | `tests/test_models.py`, `test_main_window_options.py` |
| 1.4 | HW エンコーダーで書き出し（VideoToolbox / MF） | **real ffmpeg + 実 HW** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | エンコーダー選択は `tests/test_encoder.py` でモック済み |
| 1.5 | 出力 MP4 がプレイヤーで指定周回・秒数どおり | **real ffmpeg + 目視・再生** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | — |

## 2. 出力形式 — JPEG / PNG

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 2.1 | 単一フレーム（インデックス指定） | argv: **unit** / 画素: **ffmpeg** | ✅ automated / ⏳ visual | `tests/test_single_frame_command.py`, `test_single_frame_service.py` |
| 2.2 | 範囲外インデックスは FFmpeg 前に失敗 | **unit** | ✅ automated | `test_single_frame_service.py`, `test_multi_frame_service.py` |
| 2.3 | 複数インデックス・範囲・全フレーム連番（`stem_%03d`） | argv: **unit** / ファイル列: **ffmpeg** | ✅ automated / ⏳ visual | `tests/test_multi_frame_command.py` |
| 2.4 | 連番ファイルが欠けず出力される | **real ffmpeg + ファイル列確認** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | — |

## 3. 出力形式 — GIF 再エンコード

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 3.1 | palettegen / paletteuse と vsync passthrough | argv: **unit** | ✅ automated | `tests/test_command.py` |
| 3.2 | リサイズ後もアニメーションし色化けが著しくない | **real ffmpeg + 目視** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | — |

## 4. 共通変換オプション

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 4.1 | リサイズ既定 = neighbor（scale=flags=neighbor） | argv: **unit** / 画素: **ffmpeg** | ✅ automated / ⏳ visual | `tests/test_command.py` |
| 4.2 | 片方寸法のみ指定でアスペクト比維持 | argv: **unit** | ✅ automated | `tests/test_command.py` |
| 4.3 | メタデータ削除（`-map_metadata -1`） | argv: **unit** / EXIF 等: **ffmpeg** | ✅ automated / ⏳ visual | `tests/test_command.py` |
| 4.4 | メタデータ保持時は `-map_metadata` なし | **unit** | ✅ automated | `tests/test_command.py` |
| 4.5 | サイズ維持・縮小でピクセル境界が崩れない | **real ffmpeg + 目視** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | T3-1 完了条件 |

## 5. 進捗・キャンセル

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 5.1 | 進捗コールバックが UI スレッドで更新 | **unit**（モック worker） | ✅ automated | `tests/test_progress_cancel_service.py`, `test_main_window_convert.py` |
| 5.2 | キャンセルでプロセス停止・一時出力削除 | **unit**（Popen モック） | ✅ automated | `tests/test_progress_cancel_service.py` |
| 5.3 | キャンセル後 UI に cancelled 表示 | **unit**（offscreen Qt） | ✅ automated | `tests/test_main_window_convert.py` |
| 5.4 | 長時間変換中の実キャンセル（GUI 操作） | **real ffmpeg + .app または dev** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | ロジックは automated |

## 6. エンコーダー / ffmpeg 失敗

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 6.1 | MP4: HW なし → `encoder_unavailable`、GPL ffmpeg へフォールバックしない | **unit**（モック） | ✅ automated | `tests/test_service.py`, `tests/test_encoder.py` |
| 6.2 | 同梱 ffmpeg 欠如 → 分類済みエラー（PATH の ffmpeg は使わない） | **unit** | ✅ automated | `tests/test_binary.py`, `tests/test_service.py` |
| 6.3 | エラーメッセージが UI に表示 | **unit** | ✅ automated | `tests/test_main_window_convert.py`, `tests/test_service.py` |
| 6.4 | 非 MP4 で ffmpeg 欠如 | **unit** | ✅ automated | `tests/test_service.py` |
| 6.5 | 実機で HW なし Mac / 無 ffmpeg 環境の挙動 | **real .app、クリーン環境** | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28), [#29](https://github.com/ken-is-engineer/pixelart-converter/issues/29) | — |

## 7. UI

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 7.1 | GIF 入力のプレビュー（メタデータ・ニアレスト拡大・硬いピクセル縁） | **unit**（offscreen + テスト GIF） | ✅ automated | `tests/test_main_window_preview.py` |
| 7.2 | 出力形式に応じたコントロール出し分け（MP4 排他、JPEG/PNG フレーム、GIF 簡素化） | **unit** | ✅ automated | `tests/test_main_window_options.py` |
| 7.3 | 複数出力時の連番ファイル名ヒント | **unit** | ✅ automated | `tests/test_main_window_output_hint.py` |
| 7.4 | 変換が GUI スレッドをブロックしない | **unit**（QThread モック） | ✅ automated | `tests/test_main_window_convert.py` |
| 7.5 | 実ウィンドウでのプレビュー・変換操作（目視） | **real .app または dev + ffmpeg** | ⏳ [#29](https://github.com/ken-is-engineer/pixelart-converter/issues/29) | offscreen は automated |

## 8. 同梱バイナリ解決

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 8.1 | vendor / `_MEIPASS` / 環境変数 override の優先順 | **unit** | ✅ automated | `tests/test_binary.py` |
| 8.2 | PATH 上の decoy ffmpeg を使わない | **unit** | ✅ automated | `tests/test_binary.py`, `tests/test_service.py` |
| 8.3 | ビルド済み ffmpeg が LGPL・libx264 なし | **real binary**（存在時のみ） | ⏳ [#28](https://github.com/ken-is-engineer/pixelart-converter/issues/28) | `tests/test_ffmpeg_binary.py` は binary があるとき自動実行（現状 skip） |
| 8.4 | configure フラグ・バージョン固定 | **unit** | ✅ automated | `tests/test_ffmpeg_build_flags.py` |

## 9. 梱包・配布（Phase 5 / 6）

| # | 観点 | 検証方法 | 状態 | 根拠 / 備考 |
|---|------|----------|------|-------------|
| 9.1 | onedir spec・ビルドスクリプト（onefile 禁止、ffmpeg datas） | **unit** | ✅ automated | `tests/test_macos_packaging.py`, `test_windows_packaging.py`, `test_dynamic_linking_packaging.py` |
| 9.2 | 空き不足 / ffmpeg 欠如でビルド拒否 | **unit**（スクリプト dry） | ✅ automated | packaging テスト |
| 9.3 | macOS `.app` ビルド・Python なしで全形式変換 | **Mac 5 GB+・ffmpeg・PyInstaller** | ⏳ [#29](https://github.com/ken-is-engineer/pixelart-converter/issues/29) | `docs/packaging.md` |
| 9.4 | Windows onedir ビルド・Python なしで全形式変換 | **Windows 実機 / CI** | ⏳ [#30](https://github.com/ken-is-engineer/pixelart-converter/issues/30) | — |
| 9.5 | Windows Defender 等 AV 一次スキャン | **Windows 実機** | ⏳ [#30](https://github.com/ken-is-engineer/pixelart-converter/issues/30) | T5-3 |
| 9.6 | 梱包後 Qt `.dylib` / `.dll` が個別ファイル・動的リンク | **built .app / onedir** | ⏳ [#31](https://github.com/ken-is-engineer/pixelart-converter/issues/31) | `docs/lgpl-qt.md` |
| 9.7 | 第三者ライセンス同梱・ヘルプメニュー | **unit** | ✅ automated | `tests/test_third_party_licenses.py`, `test_main_window_licenses.py` |
| 9.8 | コード署名・公証 | 将来 | — | [#23](https://github.com/ken-is-engineer/pixelart-converter/issues/23) |

---

## サマリー

| 区分 | 件数（概算） | 状態 |
|------|--------------|------|
| ✅ automated（単体テスト） | 35 | 2026-08-29 ウォークスルーで確認 |
| ⏳ pending（実 ffmpeg / 目視 / 梱包） | 14 | issue #28–#31 に集約 |
| — 署名（別 issue） | 1 | #23 |

### 再実行手順

```bash
# 単体テスト（automated 項目の一括確認）
source .venv/bin/activate
pip install -e .
python -m unittest discover -s tests

# 同梱 ffmpeg がある場合（#28）
scripts/build_ffmpeg_lgpl.sh
python -m unittest tests.test_ffmpeg_binary -v
# 続けて代表 GIF で各形式を手動変換・目視

# macOS .app（#29）
scripts/build_macos_app.sh
open dist/pixelart-converter.app

# Windows onedir + Defender（#30）— Windows 上で
# scripts/build_windows.ps1 の後 dist/pixelart-converter/ をスキャン

# Qt 動的リンク（#31）— ビルド成果物に対して otool -L / dumpbin / 差し替え試験
```
