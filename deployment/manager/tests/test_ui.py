import os
import time
from types import SimpleNamespace
from unittest.mock import Mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import pytest
pytest.importorskip("PySide6")
from PySide6.QtWidgets import QApplication
from weave_cbt_manager.core.health import HealthSnapshot
from weave_cbt_manager.core.networking import NetworkAccessStatus
from weave_cbt_manager.state import ManagerState
from weave_cbt_manager.ui.main_window import MainWindow

@pytest.fixture(scope="module")
def application():
    return QApplication.instance() or QApplication([])

def drain(application, condition):
    deadline = time.monotonic() + 3
    while not condition() and time.monotonic() < deadline:
        application.processEvents()
        time.sleep(.005)
    assert condition()

def fake_controller():
    controller = Mock()
    controller.state = ManagerState()
    controller.installation_present.return_value = False
    controller.platform.lan_ip.return_value = "192.168.1.10"
    controller.network_access.return_value = NetworkAccessStatus(
        lan_ip="192.168.1.10",
        network_name="School Wi-Fi",
        interface_alias="Wi-Fi",
        interface_index=10,
        category="Private",
    )
    controller.prepare_infrastructure.return_value = SimpleNamespace(reboot_required=False)
    controller.install_application.return_value = HealthSnapshot(True, True, True, "Healthy")
    return controller

def test_setup_completes_without_manual_database_fields(application):
    controller = fake_controller()
    window = MainWindow(controller)
    window.show()
    drain(application, lambda: not window.busy and window.stack.currentWidget() == window.pages[window.setup])
    assert not window.windowIcon().isNull()
    window.setup.install_button.click()
    drain(application, lambda: not window.busy and window.stack.currentWidget() == window.pages[window.dashboard])
    controller.install_application.assert_called_once()
    assert window.dashboard.open_button.isEnabled()
    assert window.dashboard.lan_url == "http://192.168.1.10/student"
    window.close()

def test_failed_setup_has_working_retry_and_logs_controls(application):
    controller = fake_controller()
    controller.prepare_infrastructure.side_effect = RuntimeError("Internet unavailable")
    window = MainWindow(controller)
    window.show()
    drain(application, lambda: not window.busy and window.stack.currentWidget() == window.pages[window.setup])
    window.setup.install_button.click()
    drain(application, lambda: not window.busy and window.installing.retry_button.isVisible())
    assert "Internet unavailable" in window.installing.activity.toPlainText()
    assert window.installing.logs_button.isVisible()
    controller.prepare_infrastructure.side_effect = None
    window.installing.retry_button.click()
    drain(application, lambda: not window.busy and window.stack.currentWidget() == window.pages[window.dashboard])
    assert controller.prepare_infrastructure.call_count == 2
    window.close()

def test_unhealthy_server_does_not_advertise_an_available_student_link(application):
    controller = fake_controller()
    window = MainWindow(controller)
    window.show()
    drain(application, lambda: not window.busy and window.stack.currentWidget() == window.pages[window.setup])
    window.dashboard.set_network_access(controller.network_access.return_value)
    window.dashboard.set_health(HealthSnapshot(True, False, False, "Database unavailable"), "192.168.1.10")
    assert not window.dashboard.open_button.isEnabled()
    assert not window.dashboard.copy_button.isEnabled()
    assert not window.dashboard.lan_url
    window.close()

