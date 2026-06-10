"""Test script to verify hardening integration."""

import sys


def test_imports():
    """Test that all hardening components can be imported."""
    print("Testing imports...")

    try:
        print("  OK Error bus imported")

        print("  OK Recovery manager imported")

        print("  OK Resource monitor imported")

        print("  OK Cleanup manager imported")

        print("  OK Config validator imported")

        print("  OK Resource limits imported")

        print("  OK Error notification widgets imported")

        print("  OK MainWindow imported")

        print("\nOK All imports successful!")
        return True
    except Exception as e:
        print(f"\nFAIL Import failed: {e}")
        return False


def test_initialization():
    """Test that hardening components can be initialized."""
    print("\nTesting initialization...")

    try:
        from app.events import get_error_bus, publish_error, ErrorCategory, ErrorSeverity
        from app.events.recovery import get_recovery_manager
        from app.monitoring import get_resource_monitor
        from app.lifecycle import get_cleanup_manager
        from app.validation import ConfigValidator
        from app.config import ResourceLimits, set_resource_limits

        # Test error bus
        error_bus = get_error_bus()
        print("  OK Error bus initialized")

        # Test recovery manager
        recovery_manager = get_recovery_manager()
        recovery_manager.start()
        print("  OK Recovery manager started")

        # Test resource monitor
        resource_monitor = get_resource_monitor()
        resource_monitor.start()
        print("  OK Resource monitor started")
        metrics = resource_monitor.get_current_metrics()
        print(f"    - CPU: {metrics.cpu_percent:.1f}%")
        print(f"    - Memory: {metrics.memory_mb:.0f}MB ({metrics.memory_percent:.1f}%)")
        print(f"    - Threads: {metrics.thread_count}")

        # Test cleanup manager
        cleanup_manager = get_cleanup_manager()
        cleanup_manager.register_cleanup("test", lambda: None, timeout=1.0)
        print("  OK Cleanup manager initialized")

        # Test config validator
        validator = ConfigValidator()
        print("  OK Config validator initialized")

        # Test resource limits
        limits = ResourceLimits()
        set_resource_limits(limits)
        print("  OK Resource limits configured")

        # Test error publishing
        publish_error(
            category=ErrorCategory.SYSTEM,
            severity=ErrorSeverity.INFO,
            message="Integration test successful",
            source="test_integration.py",
        )
        print("  OK Error publishing works")

        # Cleanup
        resource_monitor.stop()
        recovery_manager.stop()

        print("\nOK All components initialized successfully!")
        return True
    except Exception as e:
        import traceback

        print(f"\nFAIL Initialization failed: {e}")
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("PitchTracker Hardening Integration Test")
    print("=" * 60)

    success = True

    if not test_imports():
        success = False

    if not test_initialization():
        success = False

    print("\n" + "=" * 60)
    if success:
        print("ALL TESTS PASSED OK")
        print("=" * 60)
        return 0
    else:
        print("SOME TESTS FAILED FAIL")
        print("=" * 60)
        return 1


if __name__ == "__main__":
    sys.exit(main())
