"""Shared constants for the WEAVE CBT Manager."""

APP_NAME = "WEAVE CBT Manager"
APP_VERSION = "0.1.0"

DEFAULT_WEAVE_IMAGE = "ghcr.io/aphrodite1818/weave-cbt-module:deployment-test"
DEFAULT_WEAVE_API_BASE_URL = "https://api.weavecloudspace.com"
DEFAULT_POSTGRES_USER = "weave"
DEFAULT_POSTGRES_DB = "weave_cbt"
DEFAULT_SERVER_URL = "http://localhost"

RUNTIME_DIR_NAME = "WeaveCBT"
DEPLOYMENT_DIR_NAME = "runtime"
LOG_DIR_NAME = "logs"
BACKUP_DIR_NAME = "backups"
STATE_FILE_NAME = "manager-state.json"
ENV_FILE_NAME = ".env"
COMPOSE_FILE_NAME = "compose.yaml"
