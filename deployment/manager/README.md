# Weave CBT Windows Manager

The Windows x64 installer bundles the native Qt manager and an Ubuntu WSL2 filesystem containing Docker Engine and Compose. Docker Desktop is not required. First setup downloads the application, PostgreSQL, Redis and Nginx images; later local operation uses the downloaded images.

## Requirements

- Windows 10 build 19041 or newer, or Windows 11, on an x64 processor.
- Hardware virtualization enabled and approximately 8 GB installed RAM (7.5 GB usable).
- Production requires at least 20 GB free on the drive that contains `%PROGRAMDATA%` for the runtime, images and school data. Staging/development builds temporarily allow 4 GB for installer acceptance testing; 4 GB is not a recommended production capacity.
- Administrator privileges and internet access for initial installation.
- Use the same Windows account for setup and subsequent server operation. WSL registrations belong to that account. Startup tasks run at that account's sign-in, not before sign-in.
- Keep the computer awake and signed in during exams. School clients must use the same Private or Domain network. Public networks are deliberately not exposed.
- Use separate computers for production and staging; they share a runtime name and storage location. The manager rejects a different channel or registered owner before setup.

## Setup and recovery

Open the manager and select **Set up this computer**. It prepares a current WSL runtime, resumes after a required Windows restart, generates a strong random database password, downloads the services, and verifies the migration and staff portal. The dashboard provides the staff portal and a copyable student address.

A failed setup can be retried. Existing `runtime.env` credentials are reused because PostgreSQL does not change the password of an initialized volume when its environment changes. If school data exists without its configuration, setup stops and requests restoration rather than replacing credentials.

The server runs in the dedicated `WeaveCBT` distribution. A detached, singleton WSL client keeps it alive after the manager closes. Windows port forwarding is refreshed on startup, repair and a healthy status refresh. WSL NAT address changes are detected and the manager replaces only forwarding rules it owns. Network discovery does not depend on internet connectivity. Only the web port is exposed on the selected physical LAN address; the database and Redis stay internal.

## Database administration

Normal setup does not require school staff to invent or manage a database password. WEAVE generates and stores the PostgreSQL credential in the protected local `runtime.env` file.

An elevated server administrator can open **Diagnostics and installation settings → Database administration** to deliberately reveal or copy the database name, username and generated password, or open an interactive PostgreSQL console. Credentials are read only on demand and are not persisted in Manager state or placed in command arguments. PostgreSQL remains private to the local WEAVE runtime; the Manager does not expose port 5432 to the school LAN.

Logs are in `%PROGRAMDATA%\WeaveCBT\logs`. The setup error page and dashboard provide an **Open logs** action. The manager serializes operations and prevents closing during an active operation. Uninstall retains school data. Permanent deletion requires typing `DELETE`.

## CI and releases

`.github/workflows/ci-cd.yml` builds and publishes the compiled application image, tests the exact image with Compose, exports the WSL rootfs, and builds production and staging installers. The installer pins the resolved image digest. A manual run can reuse a specified public image. Anonymous image pulls are verified before packaging.

The build generates the official multi-resolution Weave icon from the same vector paths and default colors as the frontend, embeds it in the manager EXE, and uses it for the installer and Windows shortcuts. Manager version is passed consistently into the binary and release manifest. Increase the CBT version when releasing application updates so existing installations discover them.

CI runs manager regression tests and a compiled Qt self-test. This is not a substitute for a clean Windows machine acceptance test covering WSL provisioning, reboot/resume, LAN access from a second computer, database-admin controls, and operation after closing the GUI. No physical-machine installation or reboot is performed by the unit tests.

## Local checks

Copy `src/weave_cbt_manager/generated_build.py.example` to `src/weave_cbt_manager/generated_build.py`, install `.[test]` in a Python 3.11 environment, then run:

```
python -m pytest -q
python -m weave_cbt_manager --self-test
python build/create_icon.py
```

For a standalone build, run `build/build-manager.ps1` with the environment, API URL, image, CBT version, manager version, and a new output directory. Inno Setup consumes the resulting distribution and rootfs archive. CI remains the release build authority.
