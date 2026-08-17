"""Regression coverage for prompt resource-monitor shutdown."""

from app.monitoring.resource_monitor import ResourceMonitor


def test_resource_monitor_stop_wakes_sleeping_thread() -> None:
    monitor = ResourceMonitor(check_interval=60.0)
    monitor.start()

    monitor.stop()

    assert monitor._monitor_thread is None
