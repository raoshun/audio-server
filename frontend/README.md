# frontend

Vue 3 + Vite で構成される Web UI。バンドル成果物（`dist`）をバックエンドがサーブする。

## 概要

- フロントエンドは `frontend/src/App.vue`（Vue 3）で実装される。
- スタイルは `frontend/style.css`（vanilla 時代の既存スタイル）を使用し、`App.vue` からインポートしてバンドルへ取り込む。
- データフローは家庭内サーバー専用で外部公開されないため、CDN には依存せずローカルにバンドルする。
- 既存の機能・API 契約（`/api/v1/search/music`、`/api/v1/tracks`、`/api/v1/albums`、`/api/v1/albums/{id}`、`/api/v1/track/stream/{id}`）は維持する。
- 再生キュー（順再生/ランダム再生）、再生中のトラックハイライト、アルバム開きエラー処理の動作を保持する。

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
| `frontend/dist/` | ビルド成果物（コミット済み）。バックエンドがサーブする。 |

## 依存

- `vue ^3.4.21`
- `vite ^5.2.0`
- `@vitejs/plugin-vue ^5.0.4`

## ビルド

CDN 依存を避けるため、Docker の node イメージでバンドルする。

```bash
# frontend/ のみを build context として Vite をビルドする
docker build -t dwe-frontend -f frontend/Dockerfile frontend/
```

ビルド成果物をローカル（`frontend/dist`）へ取り出す。runtime は Docker の bind-mount（`./:/app`）で `frontend/dist` をサーブするため、このディレクトリが存在しないとバックエンドが起動しない。

```bash
# イメージから dist をコピーし、ホストの frontend/dist へ取り出す
docker create --name extract dwe-frontend
docker cp extract:/app/dist ./frontend/dist
docker rm extract
```

ローカルで開発中に素早くビルドする場合は、node があれば直接実行できる。

```bash
cd frontend
npm install
npm run build
```

## 動作確認

- `make test` で Playwright テストを含む全テストを実行する。Playwright テストは live backend が `frontend/dist` をサーブしている必要があるため、ビルド成果物が存在することを前提とする。
- `make lint` で ruff とスキルチェックを実行する。

## 運用

- `frontend/dist` はコミット済みで、Docker 上のバックエンド（`backend/app/search_api.py` の `StaticFiles(directory="/app/frontend/dist", html=True)`）が `frontend/dist` をサーブする。
- `frontend/Dockerfile` の build context は `frontend/`。`dist` の出力先はホストの `frontend/dist`。
- bind-mount は read-only（`./:/app:ro`）のため、`frontend/dist` のファイルは読み取り可能（`644`）である必要がある。
- 依存を変更した場合は `frontend/Dockerfile` を再ビルドし、`frontend/dist` を再取り出した後、`make test` で検証する。
