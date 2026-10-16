"""Capture and check the local UX-01 HTML design using Qt's bundled Chromium.

Optional evidence tooling; not imported by the application. Never loads a remote
URL or executes camera/service actions. Run from the repository root.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QTWEBENGINE_CHROMIUM_FLAGS", "--disable-gpu --disable-gpu-compositing")
os.environ.setdefault("QT_QUICK_BACKEND", "software")
os.environ.setdefault("QT_OPENGL", "software")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile  # noqa: E402
from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: E402
from PySide6.QtPdf import QPdfDocument  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs/review/ux/target"
SCENARIOS = [
    (page, state, data, width, height)
    for width, height in ((1366, 768), (1024, 768), (800, 600))
    for page, state, data in (
        ("live", "Idle", "Empty"), ("live", "Ready", "Empty"),
        ("live", "Recording", "Populated"), ("live", "Paused", "Populated"),
        ("live", "Finalizing", "Populated"), ("live", "Error", "Populated"),
        ("live", "Recording", "Unavailable"), ("sessions", "Completed", "Populated"),
        ("sessions", "Idle", "Empty"), ("players", "Idle", "Empty"),
        ("players", "Recording", "Populated"), ("setup", "Idle", "Empty"),
        ("setup", "Recording", "Populated"),
        ("dialog-settings", "Recording", "Populated"),
        ("dialog-analytics", "Completed", "Populated"),
    )
]
METRICS = """JSON.stringify((()=>{
    const box=stage.getBoundingClientRect();
    const header=document.querySelector('.session-header').getBoundingClientRect();
    return {
      page:ui.page,state:ui.state,data:ui.data,
      width:box.width,height:box.height,x:box.x,y:box.y,
      page_scroll_width:content.scrollWidth,page_client_width:content.clientWidth,
      essential_controls_visible:[...document.querySelectorAll('.session-actions button:not([hidden])')]
        .every(b=>{const r=b.getBoundingClientRect();return r.left>=box.left&&r.right<=box.right&&r.bottom<=header.bottom;}),
      setup_edit_disabled:[...document.querySelectorAll('[data-dialog="setup"]')].every(b=>b.disabled)
    };
})())"""


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    app = QtWidgets.QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{filename}")
    profile = QWebEngineProfile(app)  # Memory-only browser profile.
    page = QWebEnginePage(profile, app)
    view = QWebEngineView()
    view.setPage(page)
    view.resize(1460, 1000)
    view.show()
    results = []
    failures = []
    index = 0

    def next_scenario():
        nonlocal index
        if index == len(SCENARIOS):
            check_interactions()
            return
        page_name, state, data, width, height = SCENARIOS[index]
        view.resize(width, height)
        fixture = {"page": "live" if page_name.startswith("dialog-") else page_name,
                   "state": state, "data": data}
        dialog_script = f"openDialog({json.dumps(page_name[7:])});" if page_name.startswith("dialog-") else ""
        script = f"""(()=>{{
            const dialog=document.getElementById('task-dialog');if(dialog.open)dialog.close();
            Object.assign(ui, {json.dumps(fixture)}); render();
            document.getElementById('fixture-data').value=ui.data;
            stage.style.setProperty('--viewport-width','{width}px');
            stage.style.setProperty('--viewport-height','{height}px');
            stage.classList.toggle('compact',{str(width <= 1024).lower()});
            document.getElementById('viewport').value='{width} × {height}';
            content.scrollTop=0;
            {dialog_script}
        }})();
        """

        def captured(raw):
            nonlocal index
            result = json.loads(raw)
            name = f"{page_name}-{state.lower()}-{data.lower()}-{width}x{height}.png"
            result["file"] = name
            if result["width"] != width or result["height"] != height:
                failures.append(f"Stage size mismatch: {name}")
            if result["page_scroll_width"] > result["page_client_width"]:
                failures.append(f"Unexpected page horizontal overflow: {name}")
            if not result["essential_controls_visible"]:
                failures.append(f"Essential actions outside stage: {name}")
            if page_name == "setup" and state == "Recording" and not result["setup_edit_disabled"]:
                failures.append(f"Setup edit buttons enabled during recording: {name}")
            result["device_pixel_ratio"] = view.devicePixelRatioF()
            # Native offscreen WebEngine grabs can miss compositor surfaces.
            # Print the layout to an in-memory vector page, then rasterize it.
            paper = QtGui.QPageSize(
                QtCore.QSizeF(width * 25.4 / 96, height * 25.4 / 96), QtGui.QPageSize.Unit.Millimeter)
            layout = QtGui.QPageLayout(
                paper, QtGui.QPageLayout.Orientation.Portrait, QtCore.QMarginsF(0, 0, 0, 0))

            def printed(pdf_bytes):
                nonlocal index
                buffer = QtCore.QBuffer()
                buffer.setData(pdf_bytes)
                buffer.open(QtCore.QIODevice.OpenModeFlag.ReadOnly)
                pdf = QPdfDocument()
                pdf.load(buffer)
                image = pdf.render(0, QtCore.QSize(width, height))
                if image.isNull() or not image.save(str(OUTPUT / name)):
                    failures.append(f"Target rasterization failed: {name}")
                pdf.close()
                buffer.close()
                results.append(result)
                index += 1
                if index % 15 == 0:
                    print(f"Rendered {index}/{len(SCENARIOS)} target examples", flush=True)
                QtCore.QTimer.singleShot(50, next_scenario)

            page.printToPdf(printed, layout)

        page.runJavaScript(script, lambda _ignored: QtCore.QTimer.singleShot(
            350, lambda: page.runJavaScript(METRICS, captured)))

    def check_interactions():
        script = """
            ui.state='Recording';ui.page='live';ui.data='Populated';render();
            document.querySelector('nav [data-page=sessions]').click();
            const navigationPreservedRecording=ui.state==='Recording'&&ui.page==='sessions';
            document.querySelector('nav [data-page=live]').click();
            document.getElementById('primary-action').click();
            const pauseWorks=ui.state==='Paused';
            document.querySelector('nav [data-page=setup]').click();
            const setupProtected=[...document.querySelectorAll('[data-dialog=setup]')].every(b=>b.disabled);
            document.querySelector('nav [data-page=sessions]').click();
            document.querySelector('[data-pitch="2"]').click();
            const selectionWorks=ui.pitch===2&&ui.state==='Paused';
            JSON.stringify({navigationPreservedRecording,pauseWorks,setupProtected,selectionWorks});
        """

        def finish(raw):
            checks = json.loads(raw)
            failures.extend(key for key, passed in checks.items() if not passed)
            report = {"schema_version": "ux_prototype_checks.v1", "prototype_only": True,
                      "renderer": "Qt WebEngine Chromium PDF / Qt PDF rasterization", "captures": results,
                      "interaction_checks": checks, "failures": failures}
            report["source_commit"] = subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
            (OUTPUT / "checks.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
            print(f"Target captures: {len(results)}; interaction checks: {checks}; failures: {failures}")
            view.close()
            app.exit(1 if failures else 0)

        page.runJavaScript(script, finish)

    def loaded(ok):
        if not ok:
            print("Could not load local prototype", file=sys.stderr)
            app.exit(1)
            return
        page.runJavaScript("""
            const captureStyle=document.createElement('style');
            captureStyle.textContent='.inspector,.prototype-note{display:none}.stage{margin:0;border-radius:0}';
            document.head.appendChild(captureStyle);
        """, lambda _ignored: QtCore.QTimer.singleShot(500, next_scenario))

    page.loadFinished.connect(loaded)
    page.load(QtCore.QUrl.fromLocalFile(str(ROOT / "docs/review/ux/workspace.html")))

    def timed_out():
        print(f"Target renderer timed out after {index}/{len(SCENARIOS)} examples", file=sys.stderr)
        app.exit(2)

    QtCore.QTimer.singleShot(90000, timed_out)
    status = app.exec()
    page.deleteLater()
    view.deleteLater()
    app.processEvents()
    return status


if __name__ == "__main__":
    raise SystemExit(main())
