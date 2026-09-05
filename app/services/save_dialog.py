"""A small, testable boundary around the local Windows Save As dialog."""
from pathlib import Path
import tkinter as tk
from tkinter import filedialog


def choose_png_destination(initial_name: str) -> Path | None:
    root = tk.Tk()
    try:
        root.withdraw()
        selected = filedialog.asksaveasfilename(
            initialfile=initial_name,
            defaultextension='.png',
            filetypes=[('PNG image', '*.png')],
            confirmoverwrite=True,
        )
    finally:
        root.destroy()
    return Path(selected) if selected else None
