# コード署名・公証（T5-4）

本フェーズ（Phase 5）では **署名なしのローカルビルドで十分** とする。Developer ID 署名・Apple 公証・Windows Authenticode は **後続タスク** として方針だけここに残す。署名用スクリプトや CI への組み込みは **本タスクでは実装しない**。

追跡用 issue: [#23 — Follow-up: code signing and notarization](https://github.com/ken-is-engineer/pixelart-converter/issues/23)

## 現状（T5-1〜T5-3）

| プラットフォーム | 状態 | ユーザー影響 |
|------------------|------|--------------|
| macOS | 署名なし `.app` | 同一 Mac のローカルビルドは多くの場合そのまま起動。他 Mac へ配布すると Gatekeeper が止めることがある（[packaging.md](packaging.md) の「署名なしで開く」参照） |
| Windows | 署名なし onedir `.exe` | SmartScreen が初回起動を止めることがある（[packaging.md](packaging.md) の Windows 節参照） |

開発・手動テスト・社内配布は上記のままで問題ない。公開配布（ダウンロードページ、GitHub Releases 等）を始める前に、後述の署名・公証を実装する。

## 将来方針

### macOS — Developer ID + 公証（notarization）

1. **Apple Developer Program** に登録し、**Developer ID Application** 証明書を取得する（Team ID が必要）。
2. ビルド後の `pixelart-converter.app` に `codesign` で署名する（ネストされたバイナリ・フレームワーク・同梱 ffmpeg を含む）。
3. **公証**: `notarytool` で `.app` または配布用 `.dmg` / `.zip` を Apple に提出し、ステープル（`stapler staple`）する。
4. **Hardened Runtime** と必要な **entitlements**（例: 動画エンコード用のメディア関連）を spec / 署名手順に反映する。
5. CI では macOS ランナー上で署名・公証を行う。**証明書・App 用パスワード・notary 資格情報はリポジトリに置かない**（GitHub Actions secrets 等）。

参考コマンドの方向性（実装は後続）:

```bash
# 例: アプリ署名（identity は環境変数や CI secret から渡す）
codesign --force --options runtime --sign "$APPLE_SIGNING_IDENTITY" dist/pixelart-converter.app

# 例: 公証提出（パスワードは keychain または notarytool の credentials store）
xcrun notarytool submit pixelart-converter.zip --apple-id "$APPLE_ID" --team-id "$APPLE_TEAM_ID" --password "$APPLE_APP_PASSWORD" --wait
xcrun stapler staple dist/pixelart-converter.app
```

### Windows — Authenticode

1. **コードサイニング証明書**（EV または Standard）を取得する。SmartScreen の信頼確立には EV が有利だが、コストと更新運用を見て選ぶ。
2. 配布物のエントリ `pixelart-converter.exe` および必要に応じて同梱 DLL に **Authenticode** 署名する（`signtool` 等）。
3. タイムスタンプサーバーを指定し、証明書失効後も署名が検証できるようにする。
4. CI では Windows ランナー上で署名する。**PFX / 証明書パスワードはリポジトリに置かない**（GitHub Actions secrets 等）。

参考コマンドの方向性（実装は後続）:

```powershell
# 例: signtool（証明書は CI secret から一時ファイルへ展開）
signtool sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /f $env:SIGNING_CERT_PFX /p $env:SIGNING_CERT_PASSWORD dist\pixelart-converter\pixelart-converter.exe
```

## リポジトリに含めないもの

- Apple: `.p12`、Developer ID 秘密鍵、App 専用パスワード、notary API キー（`.p8`）の平文
- Windows: `.pfx` / `.pvk`、証明書パスワード
- 上記を `.env` やスクリプトに直書きしたファイル

`.gitignore` で証明書拡張子を除外し、README / ビルド doc では「secrets は CI またはローカル keychain のみ」と明記する。

## 完了条件（T5-4）

- [x] 本ドキュメントに方針が書かれている
- [x] GitHub issue「Follow-up: code signing and notarization」が起票されている
- [ ] 署名・公証スクリプトの実装（**意図的に後続**）
- [ ] CI への secrets 連携（**意図的に後続**）

実装着手時は issue を参照し、`packaging/macos.spec`・`packaging/windows.spec` および `scripts/build_macos_app.sh` / `scripts/build_windows.ps1` の **ビルド成功後** に署名ステップを追加する想定。
