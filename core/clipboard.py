import time
from io import BytesIO

import pyperclip
import win32clipboard
from PIL import Image


def get_text() -> str:
    """Read text content from the clipboard."""
    try:
        return pyperclip.paste() or ""
    except Exception:
        return ""


def set_text(text: str) -> bool:
    """Write text into the clipboard."""
    try:
        pyperclip.copy(text or "")
        return True
    except Exception:
        return False


def set_image(image: Image.Image, retries: int = 3, interval: float = 0.05) -> bool:
    """Write a PIL image into the Windows clipboard with retry to avoid contention."""
    for attempt in range(retries):
        try:
            buffer = BytesIO()
            image.convert("RGB").save(buffer, "BMP")
            data = buffer.getvalue()[14:]  # remove BMP header, keep DIB data
            buffer.close()

            win32clipboard.OpenClipboard()
            win32clipboard.EmptyClipboard()
            win32clipboard.SetClipboardData(win32clipboard.CF_DIB, data)
            win32clipboard.CloseClipboard()
            return True
        except Exception:
            try:
                win32clipboard.CloseClipboard()
            except Exception:
                pass
            if attempt < retries - 1:
                time.sleep(interval)
    return False
