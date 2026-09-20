from weave_cbt_manager.build_metadata import BuildEnvironment, BuildMetadata
from weave_cbt_manager.core.config import ConfigService, InstallationConfigInput, render_runtime_env


def test_runtime_config_encodes_database_url_and_preserves_literal_env_password():
    service = ConfigService(BuildMetadata(BuildEnvironment.PROD, "https://api.weavecloudspace.com", "ghcr.io/aphrodite1818/weave-cbt-module:sha-test", "0.1.0"))
    config = service.create_runtime_config(InstallationConfigInput("weave_cbt", "weave_admin", "Pass$word#'@2026"))
    assert "Pass%24word%23%27%402026" in config.database_url
    rendered = render_runtime_env(config)
    assert "WEAVE_IMAGE='ghcr.io/aphrodite1818/weave-cbt-module:sha-test'" in rendered
    assert "POSTGRES_PASSWORD='Pass$word#\\'@2026'" in rendered


def test_invalid_postgres_identifier_is_rejected():
    service = ConfigService(BuildMetadata(BuildEnvironment.PROD, "https://api.weavecloudspace.com", "repo/app:1", "0.1.0"))
    try:
        service.create_runtime_config(InstallationConfigInput("bad-name", "weave", "very-long-password"))
    except ValueError as exc:
        assert "database name" in str(exc)
    else:
        raise AssertionError("Expected invalid database name to be rejected")
