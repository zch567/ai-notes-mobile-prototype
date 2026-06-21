from __future__ import annotations

import platform
import uuid
from pathlib import Path

from .config import settings


DOCX_FILE_FORMAT = 16
AUTOMATION_SECURITY_FORCE_DISABLE = 3


def convert_legacy_doc(path: Path, *, output_dir: Path | None = None) -> Path:
    source = path.expanduser().resolve()
    if source.suffix.lower() != ".doc":
        raise ValueError(f"Legacy Word conversion requires a .doc file: {source.name}")
    if platform.system() != "Windows":
        raise ValueError("DOC conversion requires Windows and Microsoft Word. Please save the file as DOCX and retry.")

    try:
        import pythoncom
        import win32com.client
    except ImportError as exc:
        raise ValueError(
            "DOC conversion support is unavailable. Install pywin32 and Microsoft Word, or save the file as DOCX."
        ) from exc

    target_dir = (output_dir or settings.output_dir / "_converted").resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"{source.stem}-{uuid.uuid4().hex[:8]}.docx"
    word = None
    document = None
    pythoncom.CoInitialize()
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        word.AutomationSecurity = AUTOMATION_SECURITY_FORCE_DISABLE
        document = word.Documents.Open(
            str(source),
            ConfirmConversions=False,
            ReadOnly=True,
            AddToRecentFiles=False,
            UpdateLinks=0,
            Visible=False,
        )
        document.SaveAs2(str(target), FileFormat=DOCX_FILE_FORMAT, AddToRecentFiles=False)
    except Exception as exc:
        target.unlink(missing_ok=True)
        raise ValueError(
            f"Unable to convert DOC file '{source.name}' with Microsoft Word. Save it as DOCX and retry."
        ) from exc
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:
                pass
        pythoncom.CoUninitialize()

    if not target.exists() or target.stat().st_size == 0:
        target.unlink(missing_ok=True)
        raise ValueError(
            f"Microsoft Word did not produce a valid DOCX file for '{source.name}'. Save it as DOCX and retry."
        )
    return target
