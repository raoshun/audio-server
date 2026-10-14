.PHONY: up down logs shell test test-frontend lint verify local-verify sync sync-apply scan

# -------------------------------------------------
# Help
# -------------------------------------------------
help:
	@printf "Available make commands:\n"
	@printf "  up            \tStart containers (build if needed)\n"
	@printf "  down          \tStop and remove containers\n"
	@printf "  logs          \tFollow logs of $(SERVICE)\n"
	@printf "  shell         \tOpen a shell in $(SERVICE)\n"
	@printf "  test          \tRun pytest in the test service\n"
	@printf "  test-frontend \tRun Vitest in the frontend-test service\n"
	@printf "  lint          \tRun ruff linting on the backend code\n"
	@printf "  verify        \tRun build, tests, frontend tests and lint (CI equivalent)\n"
	@printf "  local-verify  \tRun local clone verification script\n"
	@printf "  sync          \tRun sync dry‑run script\n"
	@printf "  sync-apply    \tRun sync script with --apply\n"
	@printf "  scan          \tRun Navidrome full scan script\n"

# -------------------------------------------------
# 基本操作
# -------------------------------------------------
SERVICE ?= backend
TEST_SERVICE ?= test

DC = docker compose

# -------------------------------------------------
# コンテナ操作
# -------------------------------------------------
up:
	$(DC) up -d --build

down:
	$(DC) down

logs:
	$(DC) logs -f $(SERVICE)

# -------------------------------------------------
# 開発シェル
# -------------------------------------------------
shell:
	$(DC) exec $(SERVICE) bash

# -------------------------------------------------
# テスト & lint
# -------------------------------------------------
test:
	$(DC) run --rm $(TEST_SERVICE) pytest -q

test-frontend:
	# フロントエンドのユニットテスト（Vitest）を Docker で実行する。
	# Node 依存はホストへインストールせず、frontend/test.Dockerfile で隔離する。
	$(DC) run --rm frontend-test

lint:
	# Use the test service (read‑write mount) for linting so fixes can be applied.
	# Disable ruff cache because the container file system may be read‑only in other services.
	$(DC) up -d --build $(TEST_SERVICE)
	$(DC) exec $(TEST_SERVICE) ruff check . --no-cache --fix
	# Also run the custom skill‑lint check for Japanese‑only SKILL.md files
	$(DC) exec $(TEST_SERVICE) python scripts/check_skills.py
	# 共通コーディング規則（MinIO直接書き込み・秘密平文・日本語コメント）を
	# backend と frontend のソース（JS/TS 含む）へ適用する。
	$(DC) exec $(TEST_SERVICE) python scripts/policy_linter.py

# -------------------------------------------------
# 補助タスク
# -------------------------------------------------
verify:
	# CI と同等のチェックを順に実行する（ビルド → テスト → フロントエンドテスト → Lint）。
	$(DC) build test frontend-test
	$(MAKE) test
	$(MAKE) test-frontend
	$(MAKE) lint

local-verify:
	# ローカル clone（read-only キャッシュ）の存在と整合性を確認する。
	./scripts/local-verify.sh

sync:
	./scripts/sync-dwe.sh               # デフォルトは dry‑run

sync-apply:
	./scripts/sync-dwe.sh --apply       # 本番適用

scan:
	./scripts/navidrome-scan.sh         # Navidrome のフルスキャン