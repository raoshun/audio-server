#!/usr/bin/env bash
set -Eeuo pipefail

docker compose run --rm navidrome scan --full || docker compose exec navidrome navidrome scan --full
