# DWE Home Audio Server

This project implements the architecture defined for a DWE CD library served through Navidrome while keeping MinIO as the source of truth.

## Core principle

The system follows a strict one-way data path:

MinIO -> local clone -> Navidrome

The local clone is a read-only playback cache. Navidrome never writes back to the clone and never connects directly to MinIO.

## Runtime structure

Production data lives on the host under /srv/dwe:

- /srv/dwe/music
- /srv/dwe/staging/incoming
- /srv/dwe/staging/validated
- /srv/dwe/staging/rejected
- /srv/dwe/navidrome/data
- /srv/dwe/sync/logs
- /srv/dwe/sync/state

## What is included

- Navidrome Docker Compose
- safe one-way sync script
- validation script for FLAC quality checks
- import helper for pushing validated files to a MinIO bucket
- operational guidance captured in the workspace skill for future maintenance

## Important rules

- MinIO is the master copy of the DWE audio library.
- Local clone is generated from MinIO and is disposable.
- Navidrome reads from /music:ro only.
- No direct MinIO access from Navidrome.
- No reverse sync from local clone back to MinIO.
- No deletion without dry-run review.
- Do not commit secrets such as MinIO access keys and secret keys.

## Quick start

1. Copy `.env.example` to `.env` and fill in the proper host paths and credentials.
2. Ensure the host directories exist before launching Docker Compose.
3. Validate your DWE FLAC files in staging.
4. Upload validation-passed files to the MinIO bucket under `dwe-audio/audio`.
5. Run the sync script in dry-run mode first.
6. If the dry run looks correct, run the sync with the `--apply` flag.
7. Start Navidrome and verify the library appears in the web UI.

## Local clone verification without MinIO

If the MinIO source is temporarily unavailable, the system can still be validated against an already-cloned local music directory.

```bash
mkdir -p /srv/dwe/music /srv/dwe/navidrome/data /srv/dwe/staging/{incoming,validated,rejected} /srv/dwe/sync/logs
cp .env.example .env
chmod +x scripts/*.sh
./scripts/local-verify.sh
docker compose up -d
curl -fsS http://127.0.0.1:4533/health
```

`PUID` and `PGID` should match the host user that owns `/srv/dwe` so the container can read the cloned music library without permission issues.

## Commands

```bash
cp .env.example .env
chmod +x scripts/*.sh
./scripts/local-verify.sh
./scripts/validate-dwe.sh
./scripts/sync-dwe.sh
./scripts/sync-dwe.sh --apply
docker compose up -d
```

## Project layout

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

The developer workflow and operational procedures are defined in the workspace skill at `.github/skills/dwe-home-audio-server/SKILL.md`.

## Recovery flow

If Navidrome is broken or the local clone gets damaged:

1. Stop Navidrome if needed.
2. Delete or recreate the local clone.
3. Re-run the MinIO to local clone sync.
4. Restart Navidrome.
5. Trigger a scan and validate the library again.

This preserves the source-of-truth model because MinIO never depends on Navidrome data.
