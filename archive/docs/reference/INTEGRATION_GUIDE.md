# System Hardening Integration Guide

This guide shows how to integrate all Phase 1-4 hardening improvements into the PitchTracker application.

## Quick Start

### 1. Initialize Error Handling (Phase 2)

**In your main application initialization:**

```python
from app.events import get_error_bus, get_recovery_manager
from app.ui.error_notification import ErrorNotificationWidget, ErrorNotificationBridge

def initialize_error_handling(main_window):
    """Initialize error handling system."""
    # Get global error bus (auto-created)
    error_bus = get_error_bus()

    # Setup error recovery
    recovery_manager = get_recovery_manager()

    # Register custom recovery handlers
    recovery_manager.register_handler("stop_session", lambda event: stop_recording_session())
    recovery_manager.register_handler("shutdown", lambda event: graceful_shutdown())

    # Start recovery manager
    recovery_manager.start()

    # Add error notification widget to UI
    error_widget = ErrorNotificationWidget(main_window)
    error_bridge = ErrorNotificationBridge(error_widget)

    # Add to main window (example with QVBoxLayout)
    main_window.error_notification_layout.addWidget(error_widget)

    return error_bus, recovery_manager, error_widget, error_bridge
```

### 2. Start Resource Monitoring (Phase 3)

**Monitor CPU, memory, threads, and files:**

```python
from app.monitoring import get_resource_monitor

def initialize_monitoring():
    """Start resource monitoring."""
    monitor = get_resource_monitor()

    # Optionally adjust thresholds
    # (defaults are 2GB/4GB memory, 80%/95% CPU)

    # Start monitoring thread
    monitor.start()

    return monitor

def get_current_performance():
    """Get current performance metrics."""
    monitor = get_resource_monitor()
    metrics = monitor.get_current_metrics()

    print(f"CPU: {metrics.cpu_percent:.1f}%")
    print(f"Memory: {metrics.memory_mb:.0f}MB ({metrics.memory_percent:.1f}%)")
    print(f"Threads: {metrics.thread_count}")
    print(f"Open files: {metrics.open_files}")

    return metrics
```

### 3. Configure Resource Limits (Phase 3)

**Set system-wide resource limits:**

```python
from app.config import ResourceLimits, set_resource_limits

def configure_resource_limits():
    """Configure resource limits for the application."""
    limits = ResourceLimits(
        # Memory limits (MB)
        max_memory_mb=6000.0,  # 6GB for high-end systems
        warning_memory_mb=3000.0,  # 3GB warning

        # CPU limits (%)
        max_cpu_percent=90.0,
        warning_cpu_percent=75.0,

        # Disk space (GB)
        critical_disk_gb=10.0,  # Increase from default 5GB
        warning_disk_gb=50.0,  # Increase from default 20GB

        # Queue sizes
        detection_queue_size=10,  # Increase from default 6
        recording_queue_size=30,  # Increase from default 20

        # Timeouts (seconds)
        camera_open_timeout=15.0,  # Allow more time for cameras
        shutdown_timeout=60.0,  # Allow more time for shutdown
    )

    # Validate and set
    set_resource_limits(limits)

    return limits
```

### 4. Validate Configuration (Phase 4)

**Validate config at startup:**

```python
from app.validation import ConfigValidator

def validate_and_load_config(config):
    """Validate configuration before starting application."""
    validator = ConfigValidator()
    is_valid, issues = validator.validate(config)

    if not is_valid:
        # Show errors to user
        errors = [i for i in issues if i.severity == "error"]
        print("Configuration validation failed:")
        for error in errors:
            print(f"  ❌ {error.field}: {error.message}")
        return False

    # Show warnings
    warnings = [i for i in issues if i.severity == "warning"]
    if warnings:
        print("Configuration warnings:")
        for warning in warnings:
            print(f"  ⚠️ {warning.field}: {warning.message}")

    return True
```

### 5. Setup Graceful Shutdown (Phase 3)

**Register cleanup tasks:**

```python
from app.lifecycle import get_cleanup_manager

def register_cleanup_tasks(app_components):
    """Register cleanup tasks for graceful shutdown."""
    cleanup = get_cleanup_manager()

    # Critical tasks (must succeed)
    cleanup.register_cleanup(
        "stop_cameras",
        app_components.cameras.stop,
        timeout=5.0,
        critical=True
    )

    cleanup.register_cleanup(
        "stop_recording",
        app_components.recorder.stop_session,
        timeout=10.0,
        critical=True
    )

    cleanup.register_cleanup(
        "stop_detection",
        app_components.detection_pool.stop,
        timeout=5.0,
        critical=True
    )

    # Non-critical tasks (nice to have)
    cleanup.register_cleanup(
        "save_preferences",
        app_components.save_user_preferences,
        timeout=2.0,
        critical=False
    )

    cleanup.register_cleanup(
        "stop_monitoring",
        lambda: get_resource_monitor().stop(),
        timeout=2.0,
        critical=False
    )

    cleanup.register_cleanup(
        "stop_recovery",
        lambda: get_recovery_manager().stop(),
        timeout=2.0,
        critical=False
    )

    return cleanup

def perform_shutdown():
    """Execute graceful shutdown."""
    cleanup = get_cleanup_manager()

    print("Performing graceful shutdown...")
    success = cleanup.cleanup()

    if success:
        print("✅ Shutdown completed successfully")
        verification = cleanup.verify_cleanup()
        print(f"Remaining threads: {verification['threads_remaining']}")
    else:
        print("⚠️ Some critical cleanup tasks failed")

    return success
```

### 6. Camera Reconnection (Phase 3)

**Setup automatic camera reconnection:**

```python
from app.camera import CameraReconnectionManager, CameraState

def setup_camera_reconnection(camera_manager):
    """Setup automatic camera reconnection."""
    reconnection_mgr = CameraReconnectionManager(
        max_reconnect_attempts=5,
        base_delay=1.0,
        max_delay=30.0
    )

    # Register cameras
    reconnection_mgr.register_camera("left")
    reconnection_mgr.register_camera("right")

    # Set reconnection callback
    def try_reconnect(camera_id: str) -> bool:
        """Attempt to reconnect camera."""
        try:
            camera_manager.reconnect(camera_id)
            return True
        except Exception as e:
            print(f"Reconnection failed: {e}")
            return False

    reconnection_mgr.set_reconnect_callback(try_reconnect)

    # Set state change callback for UI updates
    def on_camera_state_change(camera_id: str, state: CameraState):
        """Handle camera state changes."""
        if state == CameraState.RECONNECTING:
            print(f"🔄 Attempting to reconnect {camera_id} camera...")
        elif state == CameraState.CONNECTED:
            print(f"✅ Camera {camera_id} reconnected successfully")
        elif state == CameraState.FAILED:
            print(f"❌ Camera {camera_id} reconnection failed permanently")

    reconnection_mgr.set_state_change_callback(on_camera_state_change)

    return reconnection_mgr

# In camera error handler
def on_camera_disconnected(camera_id: str):
    """Handle camera disconnection."""
    reconnection_mgr.report_disconnection(camera_id)
```

## Complete Integration Example

**Example main.py integration:**

```python
import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from configs.settings import load_config
from app.events import get_error_bus, get_recovery_manager
from app.monitoring import get_resource_monitor
from app.lifecycle import get_cleanup_manager
from app.validation import ConfigValidator
from app.config import configure_resource_limits
from app.ui.error_notification import ErrorNotificationWidget, ErrorNotificationBridge

class PitchTrackerApp(QMainWindow):
    """Main PitchTracker application with full hardening integration."""

    def __init__(self):
        super().__init__()

        # Phase 4: Validate configuration first
        self.config = load_config()
        if not self.validate_config():
            sys.exit(1)

        # Phase 3: Configure resource limits
        self.setup_resource_limits()

        # Phase 2: Initialize error handling
        self.setup_error_handling()

        # Phase 3: Start resource monitoring
        self.setup_monitoring()

        # Initialize application components
        self.init_components()

        # Phase 3: Setup graceful shutdown
        self.setup_cleanup()

        # Phase 3: Setup camera reconnection
        self.setup_camera_reconnection()

        # Setup UI
        self.setup_ui()

    def validate_config(self):
        """Validate configuration at startup."""
        validator = ConfigValidator()
        is_valid, issues = validator.validate(self.config)

        if not is_valid:
            errors = [i for i in issues if i.severity == "error"]
            self.show_error_dialog("Configuration Error", errors)
            return False

        warnings = [i for i in issues if i.severity == "warning"]
        if warnings:
            self.show_warning_dialog("Configuration Warnings", warnings)

        return True

    def setup_resource_limits(self):
        """Configure system resource limits."""
        configure_resource_limits()

    def setup_error_handling(self):
        """Initialize error bus and recovery."""
        self.error_bus = get_error_bus()
        self.recovery_manager = get_recovery_manager()

        # Register recovery handlers
        self.recovery_manager.register_handler("stop_session", self.stop_recording)
        self.recovery_manager.register_handler("shutdown", self.close)

        # Start recovery
        self.recovery_manager.start()

    def setup_monitoring(self):
        """Start resource monitoring."""
        self.resource_monitor = get_resource_monitor()
        self.resource_monitor.start()

    def setup_cleanup(self):
        """Register cleanup tasks."""
        self.cleanup_manager = get_cleanup_manager()

        # Register all cleanup tasks
        if hasattr(self, 'cameras'):
            self.cleanup_manager.register_cleanup(
                "stop_cameras", self.cameras.stop, timeout=5.0, critical=True
            )

        if hasattr(self, 'recorder'):
            self.cleanup_manager.register_cleanup(
                "stop_recording", self.recorder.stop_session, timeout=10.0, critical=True
            )

        if hasattr(self, 'detection_pool'):
            self.cleanup_manager.register_cleanup(
                "stop_detection", self.detection_pool.stop, timeout=5.0, critical=True
            )

        # Non-critical cleanup
        self.cleanup_manager.register_cleanup(
            "stop_monitoring", self.resource_monitor.stop, timeout=2.0, critical=False
        )
        self.cleanup_manager.register_cleanup(
            "stop_recovery", self.recovery_manager.stop, timeout=2.0, critical=False
        )

    def setup_camera_reconnection(self):
        """Setup automatic camera reconnection."""
        from app.camera import CameraReconnectionManager

        self.reconnection_mgr = CameraReconnectionManager()
        self.reconnection_mgr.register_camera("left")
        self.reconnection_mgr.register_camera("right")
        self.reconnection_mgr.set_reconnect_callback(self.try_reconnect_camera)

    def setup_ui(self):
        """Setup UI components."""
        # Add error notification widget
        self.error_widget = ErrorNotificationWidget(self)
        self.error_bridge = ErrorNotificationBridge(self.error_widget)

        # Add to layout (adjust based on your UI)
        # self.main_layout.insertWidget(0, self.error_widget)

    def closeEvent(self, event):
        """Handle application close with graceful shutdown."""
        success = self.cleanup_manager.cleanup()

        if success:
            event.accept()
        else:
            # Ask user if they want to force quit
            reply = self.ask_force_quit()
            if reply:
                event.accept()
            else:
                event.ignore()

def main():
    """Main entry point."""
    app = QApplication(sys.argv)
    window = PitchTrackerApp()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
```

## Integration Checklist

### Phase 1: Already Integrated ✅
- [x] Detection error handling (automatic)
- [x] Disk space monitoring (automatic in SessionRecorder)
- [x] Codec fallback (automatic in SessionRecorder)
- [x] Timeout cleanup (automatic in timeout_utils)

### Phase 2: Add to Main Application
- [ ] Initialize error bus: `get_error_bus()`
- [ ] Start recovery manager: `get_recovery_manager().start()`
- [ ] Add error notification widget to UI
- [ ] Register recovery handlers

### Phase 3: Add to Main Application
- [ ] Start resource monitor: `get_resource_monitor().start()`
- [ ] Configure resource limits: `set_resource_limits()`
- [ ] Setup camera reconnection manager
- [ ] Register cleanup tasks: `get_cleanup_manager().register_cleanup()`
- [ ] Call cleanup on shutdown: `cleanup_manager.cleanup()`

### Phase 4: Add to Main Application
- [ ] Validate config at startup: `ConfigValidator().validate(config)`
- [ ] Show validation errors/warnings to user

## Testing Integration

### 1. Test Error Notifications

```python
from app.events import publish_error, ErrorCategory, ErrorSeverity

# Publish test error
publish_error(
    category=ErrorCategory.CAMERA,
    severity=ErrorSeverity.WARNING,
    message="This is a test warning",
    source="IntegrationTest"
)

# Should see notification in UI
```

### 2. Test Resource Monitoring

```python
from app.monitoring import get_resource_monitor

monitor = get_resource_monitor()
metrics = monitor.get_current_metrics()
print(f"Current CPU: {metrics.cpu_percent}%")
print(f"Current Memory: {metrics.memory_mb}MB")
```

### 3. Test Graceful Shutdown

```python
from app.lifecycle import get_cleanup_manager

cleanup = get_cleanup_manager()
cleanup.register_cleanup("test_task", lambda: print("Cleanup executed!"))
success = cleanup.cleanup()
print(f"Cleanup successful: {success}")
```

## Common Patterns

### Pattern 1: Publish Error from Existing Code

```python
from app.events import publish_error, ErrorCategory, ErrorSeverity

try:
    risky_operation()
except Exception as e:
    publish_error(
        category=ErrorCategory.CAMERA,
        severity=ErrorSeverity.ERROR,
        message="Camera operation failed",
        source="CameraManager.open_camera",
        exception=e,
        camera_id="left"
    )
    raise  # Re-raise if needed
```

### Pattern 2: Subscribe to Specific Errors

```python
from app.events import get_error_bus, ErrorCategory

def on_disk_error(event):
    """Handle disk space errors."""
    if event.severity == ErrorSeverity.CRITICAL:
        stop_recording_immediately()

# Subscribe to disk space errors only
get_error_bus().subscribe(on_disk_error, category=ErrorCategory.DISK_SPACE)
```

### Pattern 3: Check Resource Limits

```python
from app.config import get_resource_limits

limits = get_resource_limits()

# Check before starting operation
if current_memory_mb >= limits.warning_memory_mb:
    print("Warning: High memory usage")

if current_memory_mb >= limits.max_memory_mb:
    print("Critical: Cannot start new operation")
    return False
```

## Performance Considerations

### Minimal Overhead
- Error bus: <1ms per event
- Resource monitor: 5-second intervals, <1% CPU
- Frame drop tracking: O(1) dictionary operations
- Total memory overhead: <20KB

### Best Practices
1. **Don't spam error bus** - Use throttling for repeated errors
2. **Use appropriate severity** - INFO for non-issues, CRITICAL sparingly
3. **Provide context** - Include relevant metadata in error events
4. **Clean up subscriptions** - Unsubscribe when components are destroyed
5. **Register cleanup early** - Before starting operations that need cleanup

## Troubleshooting

### Error Notifications Not Showing
- Check that `ErrorNotificationWidget` is added to UI
- Check that `ErrorNotificationBridge` is created
- Verify errors are being published with WARNING or higher severity

### Resource Monitor Not Working
- Check that `monitor.start()` was called
- Verify psutil is installed: `pip install psutil`
- Check logs for monitoring thread errors

### Cleanup Not Running
- Verify tasks are registered before shutdown
- Check timeout values aren't too short
- Look for exceptions in cleanup callbacks

### Camera Not Reconnecting
- Check that camera is registered: `reconnection_mgr.register_camera()`
- Verify reconnect callback is set and working
- Check max_reconnect_attempts hasn't been exceeded

## Next Steps

1. **Integrate error notifications into main UI**
2. **Add resource monitor status to status bar**
3. **Configure resource limits based on deployment environment**
4. **Register all cleanup tasks in main application**
5. **Test graceful shutdown thoroughly**
6. **Setup camera reconnection for production cameras**

See `docs/HARDENING_COMPLETE.md` for complete implementation details.
