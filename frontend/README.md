# frontend

Vue 3 + Vite で構成される Web UI。バンドル成果物（`dist`）をバックエンドがサーブする。

## 概要

- フロントエンドは `frontend/src/App.vue`（Vue 3）で実装される。
- スタイルは `frontend/style.css`（vanilla 時代の既存スタイル）を使用し、`App.vue` からインポートしてバンドルへ取り込む。
- データフローは家庭内サーバー専用で外部公開されないため、CDN には依存せずローカルにバンドルする。
- 既存の機能・API 契約（`/api/v1/search/music`、`/api/v1/tracks`、`/api/v1/albums`、`/api/v1/albums/{id}`、`/api/v1/track/stream/{id}`、`/api/v1/lyrics/{track_id}`）は維持する。
- 再生キュー（順再生/ランダム再生）、再生中のトラックハイライト、アルバム開きエラー処理の動作を保持する。
- 曲を選択すると暗転オーバーレイ（`.overlay`）上の中央再生ウィンドウ（`.player-modal`）を表示し、歌詞を持つ曲は `#timeupdate` に合わせて歌詞行を同期ハイライトする。
- 閉じるボタン（`#closeModalBtn`）は再生を停止してウィンドウを閉じる（`pause()` を呼び、キューを空にするため曲終了時の自動次曲送りも止まる）。
- 最小化ボタン（`#minimizeModalBtn`）は再生を継続したままウィンドウを「表示」と「閉じる」の2ボタンだけのバーへ切り替える。暗転（`.overlay`）は解かれるため、直前の画面から操作を再開できる。「表示」（`#showModalBtn`）で最小化前の画面へ戻せる。

## 構成

| ファイル | 用途 |
| --- | --- |
| `frontend/index.html` | Vue 3 のルートマウントポイントと Vite エントリーを定義する。 |
| `frontend/src/main.ts` | Vite エントリ（`createApp` で `App.vue` を `#app` へマウントする）。 |
| `frontend/src/App.vue` | UI コンポーネントと再生ロジックを保持する。 |
| `frontend/style.css` | 既存のスタイリング（バンドルへ取り込まれる）。 |
| `frontend/package.json` | Vue 3 + Vite の依存とスクリプトを定義する。 |
| `frontend/vite.config.js` | Vite のビルド設定（`dist` 出力、ミニファイ）を定義する。 |
| `frontend/Dockerfile` | node イメージで Vite をビルドし `dist` を出力する。 |
| `frontend/test.Dockerfile` | node イメージで Vitest を実行する（テスト専用）。 |
| `frontend/vitest.config.ts` | Vitest の実行環境（jsdom）とテスト対象を定義する。 |
| `frontend/tests/` | Vitest のユニットテスト（`App.spec.ts`）とセットアップ。 |
| `frontend/.dockerignore` | build context から `node_modules/` 等を除外する。 |
| `frontend/dist/` | ビルド成果物（コミット済み）。バックエンドがサーブする。 |

## 依存

- `vue ^3.4.21`
- `vite ^5.2.0`
- `@vitejs/plugin-vue ^5.0.4`
- テスト依存（devDependencies）: `@vue/test-utils ^2.5.1`、`jsdom ^25.0.1`、`vitest ^2.1.9`

ホストへ npm をインストールしないため、依存解決は `npm ci`（コンテナ内）で行う。
`package-lock.json` を変更した場合は必ずコミットする（`npm ci` は lockfile と
`package.json` の不一致で失敗する）。

## ビルド

CDN 依存を避けるため、Docker の node イメージでバンドルする。

```bash
# frontend/ のみを build context として Vite をビルドする
docker compose build frontend-test   # テストイメージ（Vitest）
docker build -t dwe-frontend -f frontend/Dockerfile frontend/
```

ビルド成果物をローカル（`frontend/dist`）へ取り出す。runtime は Docker の bind-mount（`./:/app`）で `frontend/dist` をサーブするため、このディレクトリが存在しないとバックエンドが起動しない。

```bash
# イメージから dist をコピーし、ホストの frontend/dist へ取り出す
docker create --name extract dwe-frontend
docker cp extract:/app/dist ./frontend/dist
docker rm extract
```

`App.vue` を変更した場合は dist を再生成し、コミット済みの `frontend/dist` を更新する
（バックエンドはコミット済みの dist をサーブするため、ソースだけ変更しても UI は変わらない）。

## テスト

ユニットテスト（Vitest）はホストへ npm をインストールせず、コンテナで実行する。

```bash
# frontend-test サービスで Vitest を単発実行する
make test-frontend
# 相当: docker compose run --rm frontend-test
```

- `frontend/test.Dockerfile` は `npm ci` で lockfile 準拠の依存を解決し、`npm run test`（`vitest run`）を実行する。
- `frontend/tests/setup.ts` は jsdom が未実装の `HTMLMediaElement.load()/play()` を no-op に差し替える（テスト出力をクリーンにするため）。
- Vitest は `fetch` をモック化するため backend への依存がなく、live backend を必要としない。

## 動作確認

- `make test` で Playwright テストを含む全テストを実行する。Playwright テストは live backend が `frontend/dist` をサーブしている必要があるため、ビルド成果物が存在することを前提とする。
- `make test-frontend` でフロントエンドのユニットテストを実行する。
- `make lint` で ruff、スキルチェック（`scripts/check_skills.py`）、共通コーディング規則のポリシーリンター（`scripts/policy_linter.py`）を実行する。
- `make verify` はビルド → pytest → Vitest → Lint を順に実行し、CI（`.github/workflows/ci.yml`）と同等のチェックをローカルで走らせる。

## 動作確認

- `make test` で Playwright テストを含む全テストを実行する。Playwright テストは live backend が `frontend/dist` をサーブしている必要があるため、ビルド成果物が存在することを前提とする。
- `make lint` で ruff とスキルチェックを実行する。

## 運用

- `frontend/dist` はコミット済みで、Docker 上のバックエンド（`backend/app/search_api.py` の `StaticFiles(directory="/app/frontend/dist", html=True)`）が `frontend/dist` をサーブする。
- `frontend/Dockerfile` の build context は `frontend/`。`dist` の出力先はホストの `frontend/dist`。
- bind-mount は read-only（`./:/app:ro`）のため、`frontend/dist` のファイルは読み取り可能（`644`）である必要がある。
- 依存を変更した場合は `frontend/Dockerfile` を再ビルドし、`frontend/dist` を再取り出した後、`make test` で検証する。
