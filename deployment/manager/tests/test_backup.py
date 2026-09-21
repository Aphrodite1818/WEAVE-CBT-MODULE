from pathlib import PurePosixPath
from unittest.mock import Mock
import pytest
from weave_cbt_manager.core.backup import BackupService
from weave_cbt_manager.core.deployment import DeploymentPaths
from weave_cbt_manager.runtime.base import RuntimeCommandResult

def test_failed_dump_is_not_mistaken_for_a_valid_gzip_backup():
    runtime = Mock()
    runtime.execute.return_value = RuntimeCommandResult(1, "", "pg_dump failed")
    deployment = Mock(paths=DeploymentPaths())
    with pytest.raises(RuntimeError, match="pg_dump failed"):
        BackupService(runtime, deployment).create_database_backup()
    command = runtime.execute.call_args.args[0]
    assert command[:4] == ["bash", "-o", "pipefail", "-c"]
    assert command[4].startswith("umask 077;")

def test_damaged_backup_is_rejected_before_database_is_dropped():
    runtime = Mock()
    runtime.execute.return_value = RuntimeCommandResult(1, "", "invalid gzip")
    deployment = Mock(paths=DeploymentPaths())
    with pytest.raises(RuntimeError, match="before changing the database"):
        BackupService(runtime, deployment).restore_database_backup(PurePosixPath("/backup.sql.gz"))
    runtime.execute.assert_called_once_with(["gzip", "-t", "/backup.sql.gz"], timeout=120)
