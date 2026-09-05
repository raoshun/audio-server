---
name: dwe-home-audio-server
description: "DWE 家庭用オーディオサーバーの構築・運用時に使う。MinIO を正本とし、ローカル clone へ一方向同期し、Navidrome を read-only でマウントする安全設計、検証、復旧、デプロイ手順を扱う。"
user-invocable: true
---

# DWE Home Audio Server

## 目的

家庭向けの DWE 音楽システムを構築し、音源の正式な保存先を MinIO に置き、再生用のローカル clone を生成して Navidrome に渡す。音源の流れは厳密に一方向に限定し、Navidrome から MinIO へ直接書き込むことを防ぐ。

## 必須アーキテクチャ

```text
MinIO -> local clone -> Navidrome -> client devices
```

### 所有権の境界

- MinIO = 正本 / マスターコピー
- Local clone = Navidrome が読むための read-only 参照層
- Navidrome = インデックスとストリーミングの役割のみ
- Local clone から MinIO への逆同期は禁止
- Navidrome から MinIO への直接アクセスは禁止
- Navidrome に音源フォルダへの書き込み権限を与えない

## 基本ルール

1. MinIO を唯一の正式な保存先として扱う。
2. Local clone は破棄して再構築可能なキャッシュとして扱う。
3. Navidrome の音源ディレクトリは read-only でマウントする。
4. まず `rclone copy` 等の安全な一方向同期を優先する。
5. 破壊的な削除前には必ず dry-run を行う。
6. MinIO が一時的に停止しても clone を壊さない。
7. 実運用中の MinIO バケットを勝手に削除・名称変更しない。

## 作業フロー

### 1. 環境調査

サービス作成前にホストを確認する。

```bash
uname -a
docker --version
docker compose version
df -h
docker ps
```

併せて既存の MinIO 環境を確認し、以下を把握する。

- コンテナ名
- ポート番号
- ネットワーク
- データ保存先
- バケット構成
- 認証方式

既存の MinIO を承認なく停止・再作成してはいけない。

### 2. 実行用ディレクトリを定義する

DWE 用のホストパスを整理する。

```text
/srv/dwe/
├── music/
├── staging/
│   ├── incoming/
│   ├── validated/
│   └── rejected/
├── navidrome/
│   ├── data/
│   └── config/
└── sync/
    ├── logs/
    └── state/
```

書き込みが必要なのは、ローカル clone と staging のみとする。Navidrome のデータ領域は音源と分離する。

### 3. MinIO 側の準備

専用バケットを使う。典型例は次の通り。

```text
dwe-audio/
├── audio/
├── metadata/
├── artwork/
├── manifests/
```

同期対象は `audio/` を基本とし、Local clone は Navidrome 用のキャッシュであって、正本ではない。

### 4. アップロード前の検証

staging フローを作る。

```text
incoming -> validated -> MinIO
rejected -> quarantine
```

アップロード前に確認する項目:

- FLAC として正常か
- 再生可能な duration か
- メタデータタグがあるか
- Track 数が期待通りか
- ファイル名が規則に従っているか

不正なファイルはそのままアップロードせずに rejected に退避する。

### 5. バリデーション済みファイルを MinIO に取り込む

検証済みファイルだけを MinIO のバケットへ格納する。CD リッピング直後のファイルをそのまま本番用 MinIO に置かない。

### 6. Local clone を構築する

MinIO からローカル clone へ同期する。最初は安全な copy ベースで進める。

```bash
rclone copy minio:dwe-audio/audio /srv/dwe/music --dry-run
```

確認後に適用する。

### 7. Navidrome にマウントする

Compose では read-only で mount する。

```yaml
volumes:
  - /srv/dwe/navidrome/data:/data
  - /srv/dwe/music:/music:ro
```

音源のフォルダは read-only。Navidrome が音源を書き換えられないようにする。

### 8. ライブラリ更新を反映する

clone 更新後、Navidrome にスキャンをかけて新しい曲が認識されるか確認する。

```bash
docker compose run --rm navidrome scan --full
```

### 9. 同期処理を記録する

同期ログに最低限以下を記録する。

- 開始時刻
- 終了時刻
- 追加ファイル数
- 更新ファイル数
- 削除ファイル数
- エラー
- 同期結果

ログ保存先:

```text
/srv/dwe/sync/logs/
```

### 10. 障害時の復旧

MinIO が止まっている場合:

- clone を変更しない
- 既存の再生可能な状態を維持する
- 後で同期をリトライする

Navidrome が壊れた場合:

- MinIO から clone を再生成する
- Navidrome を再起動する
- 再スキャンする

Local clone が削除・破損した場合:

- MinIO から再同期して再構築する
- Navidrome を再起動し、ライブラリを更新する

## 安全確認項目

同期やインポートの実行前に次を確認する。

- MinIO の認証情報が Git に含まれていないか
- bucket 名が正しいか
- 音源の保存パスが正しいか
- dry-run で意図しない削除対象が出ていないか
- 目的の保存先に書き込みが必要なプロセスだけがアクセスできるか
- Navidrome が read-only でマウントされているか

## 完了条件

MVP が完了したとみなす条件は次の通り。

- MinIO が正本である
- local clone は MinIO から再生成できる
- 逆同期が存在しない
- Navidrome は clone のみを参照する
- 音源 volume が read-only である
- MinIO が停止していても clone から再生できる
- MinIO に新しい DWE 音源を追加できる
- 同期後に Navidrome に新曲が表示される
- 認証情報が Git に入っていない
- 既存のホームサーバー環境を破壊していない

## 例示プロンプト

- 「DWE オーディオサーバーを MinIO を正本とした構成でセットアップして」
- 「MinIO から /srv/dwe/music への一方向同期が安全か確認して」
- 「Navidrome を read-only の clone だけ参照する構成にして」
- 「DWE FLAC の検証と MinIO へのアップロード手順を整理して」
- 「Local clone が壊れた場合の復旧手順をまとめて」

## 関連ワークスペースファイル

- [README.md](../../../README.md)
- [docker-compose.yml](../../../docker-compose.yml)
- [.env.example](../../../.env.example)
- [scripts/sync-dwe.sh](../../../scripts/sync-dwe.sh)
- [scripts/validate-dwe.sh](../../../scripts/validate-dwe.sh)
- [scripts/import-dwe.sh](../../../scripts/import-dwe.sh)
- [scripts/navidrome-scan.sh](../../../scripts/navidrome-scan.sh)
