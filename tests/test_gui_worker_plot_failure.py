from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path


class _BoundSignal:
    def __init__(self):
        self._callbacks = []

    def connect(self, callback):
        self._callbacks.append(callback)

    def emit(self, *args):
        for callback in list(self._callbacks):
            callback(*args)


class _SignalDescriptor:
    def __init__(self, *_args, **_kwargs):
        self._storage_name = None

    def __set_name__(self, _owner, name):
        self._storage_name = f"_{name}_bound_signal"

    def __get__(self, instance, _owner):
        if instance is None:
            return self
        if self._storage_name not in instance.__dict__:
            instance.__dict__[self._storage_name] = _BoundSignal()
        return instance.__dict__[self._storage_name]


class _FakePipe:
    def __init__(self, lines):
        self._lines = iter(lines)

    def readline(self):
        return next(self._lines, "")

    def close(self):
        pass


class _FakeProcess:
    def __init__(self):
        self.stdout = _FakePipe(["Finished 1 model runs\n"])
        self.stderr = _FakePipe([])
        self.returncode = 0

    def wait(self):
        return self.returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.returncode = -9


def _install_qtcore_stub(monkeypatch):
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.QObject = type("QObject", (), {})
    qtcore.QRunnable = type("QRunnable", (), {"__init__": lambda self: None})
    qtcore.Signal = _SignalDescriptor
    qtcore.Slot = lambda *args, **kwargs: (lambda func: func)

    pyside6 = types.ModuleType("PySide6")
    pyside6.QtCore = qtcore

    monkeypatch.setitem(sys.modules, "PySide6", pyside6)
    monkeypatch.setitem(sys.modules, "PySide6.QtCore", qtcore)


def _import_worker_with_qt_stub(monkeypatch):
    monkeypatch.delitem(sys.modules, "gui.core.worker", raising=False)
    try:
        import PySide6.QtCore  # noqa: F401
    except ImportError:
        _install_qtcore_stub(monkeypatch)
    return importlib.import_module("gui.core.worker")


def test_post_analysis_plot_failure_does_not_change_success_exit_code(monkeypatch, tmp_path):
    worker_mod = _import_worker_with_qt_stub(monkeypatch)

    monkeypatch.setattr(
        worker_mod.ESLWorker,
        "_resolve_unified_rust_binary",
        staticmethod(lambda: Path("/tmp/esl-psc")),
    )
    monkeypatch.setattr(worker_mod.subprocess, "Popen", lambda *_args, **_kwargs: _FakeProcess())
    monkeypatch.setattr(
        worker_mod.ESLWorker,
        "_run_inprocess_plot",
        lambda self, mode, command_args: False,
    )

    worker = worker_mod.ESLWorker([
        "--output_dir", str(tmp_path),
        "--output_file_base_name", "demo",
        "--make_sps_plot",
    ])
    outputs = []
    finished_codes = []
    worker.signals.output.connect(outputs.append)
    worker.signals.finished.connect(finished_codes.append)

    worker.run()

    assert finished_codes == [0]
    assert any("Plot generation failure did not mark" in line for line in outputs)
