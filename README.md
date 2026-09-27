# DWE Home Audio Server

このプロジェクトは、Navidrome で配信される DWE CD ライブラリの構成を実装し、
真実の情報源として MinIO を保持します。

## コア原則

システムは一方向のデータフローを厳守します:

MinIO → ローカルクローン → Navidrome

ローカルクローンは読み取り専用の再生キャッシュです。Navidrome はクローンに書き戻さず、
また MinIO に直接接続しません。

## ランタイム構成

本番データはホスト上の `/srv/dwe` に配置されます:

- /srv/dwe/music
- /srv/dwe/staging/incoming
- /srv/dwe/staging/validated
- /srv/dwe/staging/rejected
- /srv/dwe/navidrome/data
- /srv/dwe/sync/logs
- /srv/dwe/sync/state

## 含まれるもの

- Navidrome の Docker Compose 設定
- 安全な一方向同期スクリプト
- FLAC 品質チェック用検証スクリプト
- 検証済みファイルを MinIO バケットへプッシュするインポートヘルパー
- 将来の保守のためにワークスペーススキルに記載された運用ガイダンス

## 重要ルール

- MinIO が DWE オーディオライブラリのマスターコピーです。
- ローカルクローンは MinIO から生成され、使い捨て可能です。
- Navidrome は `/music:ro` からのみ読取ります。
- Navidrome から MinIO へ直接アクセスは行いません。
- ローカルクローンから MinIO への逆同期は行いません。
- 削除はドライランのレビューなしでは実行しません。
- MinIO のアクセスキーやシークレットキーなどの機密情報はコミットしません。

## クイックスタート

1. `.env.example` を `.env` にコピーし、ホストパスと認証情報を設定します。
2. Docker Compose を起動する前に、ホスト上に必要ディレクトリが存在することを確認します。
3. ステージング領域で DWE の FLAC ファイルを検証します。
4. 検証合格したファイルを `dwe-audio/audio` バケットへアップロードします。
5. 同期スクリプトをまずドライランで実行します。
6. ドライランの結果が正しければ、`--apply` オプションで本番同期を行います。
7. Navidrome を起動し、Web UI にライブラリが表示されることを確認します。

## MinIO が使用できない場合のローカルクローン検証

MinIO の供給が一時的に利用できなくても、既にクローンされたローカル音楽ディレクトリで検証できます。

```bash
mkdir -p /srv/dwe/music /srv/dwe/navidrome/data /srv/dwe/staging/{incoming,validated,rejected} /srv/dwe/sync/logs
cp .env.example .env
chmod +x scripts/*.sh
./scripts/local-verify.sh
docker compose up -d
curl -fsS http://127.0.0.1:4533/health
```

`PUID` と `PGID` は `/srv/dwe` を所有するホストユーザーに合わせて設定し、
コンテナがクローンされた音楽ライブラリに権限問題なくアクセスできるようにします。

## コマンド例

```bash
cp .env.example .env
chmod +x scripts/*.sh
./scripts/local-verify.sh
./scripts/validate-dwe.sh
./scripts/sync-dwe.sh
./scripts/sync-dwe.sh --apply
docker compose up -d
```

## アプリケーションの実行方法

サービスは `docker-compose.yml` で定義されています。典型的な作業フローは以下です:

1. **コンテナ起動** – Makefile がショートカットを提供します:

   ```bash
   make up
   ```

   必要に応じてビルドし、`backend`、`navidrome`、`lyrics` サービスをデタッチモードで実行します。

2. **UI へのアクセス** – FastAPI バックエンドがルートパスで静的フロントエンドを提供します。
   ローカルネットワーク上の任意のデバイスでブラウザを開き、以下にアクセスしてください:

   - 同一ホストでテストする場合 `http://localhost:8000/`
   - 他デバイス（例: スマートフォン）からは `http://<your‑host‑ip>:8000/`

   ページはレスポンシブで、追加設定なしでモバイルブラウザでも動作します。

3. **サービス停止** – 作業が終わったら次のコマンドで停止します:

   ```bash
   make down
   ```

これらのコマンドは内部で Docker Compose を呼び出し、`.env` に定義された環境変数を使用します。
`make up` を実行する前に必ず `.env` が正しく設定されていることを確認してください。

## プロジェクト構成

```text
dwe-audio-server/
├── .github/
│   └── skills/
│       └── dwe-home-audio-server/
│           └── SKILL.md
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── scripts/
│   ├── import-dwe.sh
│   ├── navidrome-scan.sh
│   ├── sync-dwe.sh
│   └── validate-dwe.sh
└── .env
```

開発ワークフローと運用手順は `.github/skills/dwe-home-audio-server/SKILL.md` に記載されています。

## 復旧手順

Navidrome が故障したり、ローカルクローンが破損した場合は次の手順で復旧します:

1. 必要に応じて Navidrome を停止します。
2. ローカルクローンを削除または再作成します。
3. MinIO からローカルクローンへの同期を再実行します。
4. Navidrome を再起動します。
5. スキャンをトリガーし、ライブラリが正しく反映されていることを検証します。

この手順により、MinIO が唯一の真実情報源であるモデルが保たれます。
