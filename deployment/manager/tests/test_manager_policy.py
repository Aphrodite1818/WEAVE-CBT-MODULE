from __future__ import annotations

import weave_cbt_manager.app as app_module
from weave_cbt_manager.build_metadata import BuildEnvironment, BuildMetadata


def metadata(environment: BuildEnvironment) -> BuildMetadata:
    return BuildMetadata(
        environment=environment,
        weave_api_base_url=(
            "https://api.weavecloudspace.com"
            if environment is BuildEnvironment.PROD
            else "https://weave-container-staging.up.railway.app"
        ),
        weave_image="ghcr.io/aphrodite1818/weave-cbt-module@sha256:" + ("0" * 64),
        cbt_version="0.1.0",
    )


def test_production_keeps_twenty_gb_disk_floor(monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_METADATA", metadata(BuildEnvironment.PROD))
    controller = app_module.ManagerController()
    assert controller.prerequisites.policy.minimum_free_disk_gb == 20.0


def test_staging_uses_acceptance_test_disk_floor(monkeypatch):
    monkeypatch.setattr(app_module, "BUILD_METADATA", metadata(BuildEnvironment.STAGING))
    controller = app_module.ManagerController()
    assert controller.prerequisites.policy.minimum_free_disk_gb == 4.0
