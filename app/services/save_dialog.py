"""Thread-safe boundary around LogoMock's local Windows Save As dialog."""
from dataclasses import dataclass
from pathlib import Path
from queue import Queue
from threading import current_thread, main_thread
import tkinter as tk
from tkinter import filedialog


def _trace(message: str) -> None:
    print(f'[save-dialog] {message}', flush=True)


@dataclass
class SaveDialogRequest:
    initial_name: str
    response: Queue


class SaveDialogBroker:
    """Pass a server-thread save request to the launcher's Tk main thread."""

    def __init__(self):
        self._requests = Queue()

    def choose(self, initial_name: str) -> Path | None:
        response = Queue(maxsize=1)
        self._requests.put(SaveDialogRequest(initial_name=initial_name, response=response))
        _trace('request queued for the desktop thread')
        outcome = response.get()
        if isinstance(outcome, BaseException):
            _trace(f'desktop thread rejected request: {outcome!s}')
            raise outcome
        _trace('desktop thread completed request')
        return outcome

    def next_request(self, timeout: float | None = None) -> SaveDialogRequest:
        return self._requests.get(timeout=timeout)

    def resolve(self, request: SaveDialogRequest, destination: Path | None) -> None:
        request.response.put(destination)

    def reject(self, request: SaveDialogRequest, error: BaseException) -> None:
        request.response.put(error)


_broker: SaveDialogBroker | None = None


def configure_broker(broker: SaveDialogBroker | None) -> None:
    global _broker
    _broker = broker


def show_png_destination(parent, initial_name: str) -> Path | None:
    selected = filedialog.asksaveasfilename(
        parent=parent,
        initialfile=initial_name,
        defaultextension='.png',
        filetypes=[('PNG image', '*.png')],
        confirmoverwrite=True,
    )
    return Path(selected) if selected else None


def choose_png_destination(initial_name: str) -> Path | None:
    if _broker is not None:
        return _broker.choose(initial_name)
    if current_thread() is not main_thread():
        raise OSError('无法在后台线程打开保存位置窗口，请通过 LogoMock 桌面程序启动')
    root = tk.Tk()
    try:
        root.withdraw()
        return show_png_destination(root, initial_name)
    finally:
        root.destroy()
