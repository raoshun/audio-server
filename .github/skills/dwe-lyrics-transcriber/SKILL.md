---
name: dwe-lyrics-transcriber
description: "DWE 音楽サーバーへ、FLAC 音源から faster-whisper で英語音声を文字起こしし、Navidrome が認識できる .lrc 歌詞ファイルを生成する Docker 歌詞トランスクリプションサービスのドキュメントと作業フロー。"
---

# DWE 歌詞トランスクリプション Docker 実装仕様

## 1. 目的
既存の DWE 音楽サーバーに対して、FLAC 音源から `faster-whisper` を用いて英語音声を文字起こしし、Navidrome が認識できる `.lrc` ファイルを生成する Docker サービスを追加する。

## 2. 背景
* Navidrome は音源の再生はできるが、歌詞検索・表示機能を持たない。
* 歌詞情報は公式が無いことが多く、手作業で作成するのは非効率。
* 本サービスは **GPU を利用したローカル処理** を行い、ホスト側に Python 環境を構築しないことを前提とする。

## 3. 設計方針
### 3.1 ホスト側は Python 環境を作らない
* `venv`、`uv venv`、`pip install` 等は禁止。
* すべて Docker コンテナ内で実行し、`docker compose` が唯一の開発・実行手段となる。

### 3.2 GPU 利用
* NVIDIA GPU が利用可能な環境では CUDA GPU で `faster‑whisper` を実行する。
* デフォルトモデルは `large‑v3`、メモリ不足時は `medium` へ切替可能。
* 環境変数 `WHISPER_MODEL` でモデルサイズを変更できる。

## 4. Docker Compose 追加仕様
```yaml
  lyrics:
    build:
      context: .
      dockerfile: lyrics/Dockerfile
    container_name: dwe_lyrics
    restart: "no"
    environment:
      WHISPER_MODEL: ${WHISPER_MODEL:-large-v3}
      WHISPER_LANGUAGE: ${WHISPER_LANGUAGE:-en}
      WHISPER_COMPUTE_TYPE: ${WHISPER_COMPUTE_TYPE:-float16}
      WHISPER_DEVICE: ${WHISPER_DEVICE:-cuda}
      WHISPER_VAD_FILTER: ${WHISPER_VAD_FILTER:-true}
      WHISPER_BEAM_SIZE: ${WHISPER_BEAM_SIZE:-5}
      WHISPER_TEMPERATURE: ${WHISPER_TEMPERATURE:-0}
      FORCE: ${FORCE:-false}
      DRY_RUN: ${DRY_RUN:-false}
      DWE_MUSIC_DIR: /music
      DWE_LYRICS_DIR: /music
    volumes:
      - ${DWE_MUSIC_DIR:-/srv/dwe/music}:/music
      - ./lyrics:/app
      - ./models:/models
    working_dir: /app
    command: ["python", "-m", "lyrics"]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```
* `./models` は model cache 用ボリューム、`HF_HOME=/models` として使用。
* `DWE_MUSIC_DIR` はホスト側音源ディレクトリ。コンテナ内は `/music` とマウントされ、`.lrc` は同じディレクトリに生成される。

## 5. ファイル構成
```
lyrics/
├── __init__.py
├── __main__.py   # CLI 実装
├── Dockerfile    # CUDA + PyTorch + faster‑whisper + ffmpeg
└── requirements.txt
```
* `Dockerfile` は NVIDIA CUDA ランタイムベースに `pip install -r requirements.txt` を実行し、`ffmpeg` をインストールして FLAC 読み込みを可能にする。

## 6. 処理フロー
```
FLAC
 │
 ▼
 faster‑whisper (model, language=en, device=cuda)
 │
 ▼
 segments (start, end, text)
 │
 ▼
 LRC フォーマット変換
 │
 ▼
 同名 .lrc を生成 (上書きは FORCE が true のときのみ)
```
### 6.1 LRC フォーマット
* `[MM:SS.xx]text` (centisecond 精度)。
* 時間は 00:03.21 のように 2 桁秒と小数部を保持。長時間は `HH:MM:SS.xx` ではなく `MM:SS.xx` を使用し、Navidrome 互換性を優先する。
* セグメントは Whisper が返す単位をそのまま 1 行の LRC とする（後段で行結合は実装しない）。

## 7. 設定・フラグ
| 環境変数 | デフォルト | 説明 |
|----------|------------|------|
| `WHISPER_MODEL` | `large-v3` | Whisper モデル名 |
| `WHISPER_LANGUAGE` | `en` | 言語コード |
| `WHISPER_DEVICE` | `cuda` | `cuda` または `cpu` |
| `WHISPER_COMPUTE_TYPE` | `float16` | `float16` / `float32` |
| `WHISPER_VAD_FILTER` | `true` | VAD フィルタ有効化 |
| `WHISPER_BEAM_SIZE` | `5` | ビームサイス |
| `WHISPER_TEMPERATURE` | `0` | サンプリング温度 |
| `FORCE` | `false` | 既存 .lrc があっても再生成 |
| `DRY_RUN` | `false` | 文字起こしだけ行いファイルは書き込まない |
| `ALLOW_CPU` | `false` | GPU が見えないときはエラー終了 (テスト用に `true` 可) |

## 8. CLI 仕様
* デフォルト実行で全 `.flac` を走査
```bash
docker compose run --rm lyrics
```
* ディレクトリ指定
```bash
docker compose run --rm lyrics /music/SomeAlbum
```
* 単一ファイル指定
```bash
docker compose run --rm lyrics /music/SomeAlbum/01\ -\ song.flac
```
* 強制再生成
```bash
docker compose run --rm lyrics --force
```
* Dry‑run
```bash
docker compose run --rm lyrics --dry-run
```
* `--help` は `python -m lyrics --help` と同等の出力を行う。

## 9. エラーハンドリング
* 1 曲の失敗で全体が止まらない。失敗はログに出力し、最後にサマリを表示。
* GPU が利用不可かつ `ALLOW_CPU=false` のときはエラー終了し、`ALLOW_CPU=true` を設定すると CPU フォールバック。

## 10. ロギング
* 基本は INFO レベルで処理概要、`--verbose` (環境変数 `VERBOSE=true`) で Whisper の認識結果全文を出力。
* エラーは STDERR に出力し、例外スタックトレースは抑制し要点だけ表示。

## 11. テスト方針
* ユニットテストは **外部依存をモック** して実装。
* テスト対象: 
  * `_format_timestamp` → 正しい `[MM:SS.xx]` 文字列
  * `_segment_to_lrc_line` → セグメント → LRC 行変換
  * ファイル探索ロジック (`_iter_flac_files`) のパターンマッチ
  * `FORCE`・`DRY_RUN` フラグの分岐
  * GPU 判定ロジック (`torch.cuda.is_available`) のモック
* 実際の Whisper 呼び出しはテストでモックし、サンプル `MockSegment` を使って期待出力を検証。
* Dockerfile のビルドは CI で確認し、`make lint` が 0 エラーで通過することを必須条件とする。

## 12. 既存実装の正本化
本リポジトリにすでに実装済みの以下のファイルは **正本** とし、変更は行わない。
* `lyrics/__main__.py` – CLI エントリポイント、モデルロード、FLAC スキャン、LRC 生成ロジック。
* `lyrics/Dockerfile` – CUDA ランタイムベース、`ffmpeg`、`faster-whisper` インストール。
* `docker-compose.yml` の `lyrics` サービス定義。
* `Makefile` の `lint` ターゲットは `test` コンテナ経由で `ruff` を実行し、0 エラーを保証。

## 13. 将来拡張 (MVP 後)
* Web から歌詞取得機能の復活は **廃止** し、代わりに **検索用 TXT** 生成オプション（`GENERATE_TXT=true`）を検討。
* SQLite FTS5 DB へのインデックスは別プロジェクトで実装予定。
* 詳細な行単位の LRC (word‑timestamp) は次フェーズで検討。

---
このスキルファイルはリポジトリに追加することで、実装方針・テスト計画の公式リファレンスとなります。