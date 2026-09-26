.PHONY: up down logs shell test lint verify sync sync-apply scan

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
	@printf "  lint          \tRun ruff linting on the backend code\n"
	@printf "  verify        \tRun local verification script\n"
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

lint:
	# Use the test service (read‑write mount) for linting so fixes can be applied.
	# Disable ruff cache because the container file system may be read‑only in other services.
	$(DC) exec $(TEST_SERVICE) ruff check . --no-cache --fix

# -------------------------------------------------
# 補助タスク
# -------------------------------------------------
verify:
	./scripts/local-verify.sh

sync:
	./scripts/sync-dwe.sh               # デフォルトは dry‑run

sync-apply:
	./scripts/sync-dwe.sh --apply       # 本番適用

scan:
	./scripts/navidrome-scan.sh         # Navidrome のフルスキャン