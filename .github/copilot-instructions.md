# Project Development Instructions

## Environment Policy

- Docker Compose is the canonical development environment.
- Do not create or use a local Python virtual environment (venv).
- Do not install Python packages on the host system.
- Do not run pip install, uv pip install, or poetry install
  on the host system.
- Python commands must run inside the designated Docker container.
- Use Docker Compose commands to build, run, test, and lint.

## Required Workflow

1. Inspect the existing Dockerfile and docker-compose.yaml.
2. Identify the appropriate service for the task.
3. Check the existing development and test commands.
4. Execute commands inside the Docker environment.
5. Verify changes using the project's existing test and lint commands.

## Restrictions

- Do not modify Docker configuration unless explicitly requested.
- Do not introduce alternative local development environments.
- Do not create venv, .venv, or other host-side environment directories.
- If the Docker environment is unavailable, report the issue
  instead of switching to a host-side Python environment.