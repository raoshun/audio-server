# Plan: UI改善 フロントエンドを Vue 3 へ移行

## 背景

`common-coding-rules` の Issue 中心ワークフローに従い、Issue #2（UI改善:現在の機能を維持したままフロントエンドにJSフレームワークを適用する）へ本計画を関連付ける。Issue は既に存在（OPEN）。

データフローは家庭内サーバー専用で外部公開されないため、CDN 依存を避けローカルにバンドルする。ユーザーはバンドル手段として Docker でバンドル（Dockerfile 設定変更は明示指示）、ビルドツールとして Vite を選択。

## 設計方針

- **言語品質**: コメントは原則日本語（`common-coding-rules`）。
- **Docker 運用方針**: Python 外のため、Node/npm のローカルインストールは許容。runtime は `frontend/dist` を bind-mount でサーブ（`docker-compose.yml` の `./:/app` で反映）。build は `frontend/Dockerfile` で isolation。
- **API 契約不変**: 既存バックエンドの HTTP エンドポイント・レスポンス型・Python ビジネスロジックは変更しない。`frontend/` のみ再実装。
- **Playwright セレクター維持**（重要・不可侵）: `#query`、`#searchBtn`、`#resultList li`（`data-id` 付き）、`.player`、`#player`（`:src` で `/api/v1/track/stream/{id}` を返す）。Vue テンプレートで同じ ID・クラス・属性・構造を保持。

## 実装範囲

1. **新設 `frontend/Dockerfile`**（node:20 ベース、build 専用 isolation）:
   - WORKDIR /app/src、`package.json` をコピーして依存インストール。
   - `src/main.ts` を Vite でバンドル。
   - dist を `dist` ディレクトリへ出力。
   - CMD: nginx（dist をサーブ）または `python -m http.server`。runtime は bind-mount で `frontend/dist` を上書き可能。
2. **新設 `frontend/package.json`**（Vite + Vue 3）: ビルド設定、バンドル先を `dist`。
3. **新設 `frontend/vite.config.js`**: 出力先 `dist`、バンドル構成。
4. **新設 `frontend/src/main.ts`**（Vue 3 App 実装）: 検索・全曲一覧・アルバム一覧・アルバムトラック一覧・順再生・ランダム再生・トラック単体再生・再生中のハイライト・アルバム開きエラー処理。
5. **更新 `frontend/index.html`**: `<div id="app">`（`#query`, `#searchBtn`, `#resultList li`(`data-id`)、`.player`、`#player` を Vue テンプレートで再現）。
6. **更新 `frontend/style.css`**: 既存スタイルを維持（`#player` の `src` 更新は runtime JS で対応）。
7. **更新 `frontend/README.md`**: Vite ビルド（`docker build -f frontend/Dockerfile`）と runtime の bind-mount（`frontend/dist`）の手順を明記。

## 検証

- **Lint / テスト**: `make lint`（Python + check_skills）、`make test`（`test_playwright.py` を含む）で全テスト通過を確認。
- **ビルド**: 作成した `frontend/Dockerfile` で Vite ビルドが正しく完了すること。

## Issue への反映

実装完了後、Issue #2 の完了条件チェックリストを更新し、Issue を CLOSE する。完了理由に実装内容・変更ファイル・検証方法を簡潔に付記。
