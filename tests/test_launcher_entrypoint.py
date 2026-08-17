"""Tests that supported launch commands resolve to one application entry point."""

from __future__ import annotations

import launcher


def test_launcher_parses_backend_and_config() -> None:
    args = launcher.parse_args(["--backend", "sim", "--config", "configs/default.yaml"])

    assert args.backend == "sim"
    assert str(args.config).endswith("configs\\default.yaml") or str(args.config).endswith(
        "configs/default.yaml"
    )


def test_legacy_qt_entrypoint_delegates_to_launcher(monkeypatch) -> None:
    import ui.qt_app as qt_app

    called = []
    monkeypatch.setattr(qt_app, "launcher_main", lambda: called.append(True))

    qt_app.main()

    assert called == [True]
