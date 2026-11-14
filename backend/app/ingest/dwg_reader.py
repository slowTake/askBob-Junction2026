"""DWG (AutoCAD's binary format): convert to DXF, then read it like any DXF.

DWG is closed, so it needs a converter on the server: LibreDWG's `dwg2dxf`
(apt: libredwg-utils / libredwg-tools) or the ODA File Converter. Without one the
document fails with a clear message asking for a DXF export instead.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from app.config import Settings
from app.ingest.dxf_reader import read_dxf
from app.ingest.errors import ReaderError
from app.ingest.types import ExtractedDocument, Progress

CONVERT_TIMEOUT_S = 300


def read_dwg(path: Path, settings: Settings, progress: Progress) -> ExtractedDocument:
    with tempfile.TemporaryDirectory() as tmp:
        dxf = Path(tmp) / "converted.dxf"
        _convert(path, dxf)
        progress("converted", 0.2)
        return read_dxf(dxf, settings, lambda stage, f: progress(stage, 0.2 + 0.8 * f))


def _convert(src: Path, dst: Path) -> None:
    dwg2dxf = shutil.which("dwg2dxf")
    if dwg2dxf:
        try:
            subprocess.run(
                [dwg2dxf, "-y", "-o", str(dst), str(src)],
                check=True, capture_output=True, timeout=CONVERT_TIMEOUT_S,
            )  # fmt: skip
        except (subprocess.SubprocessError, OSError) as exc:
            raise ReaderError("unreadable_file", "dwg2dxf failed") from exc
        if dst.is_file():
            return
        raise ReaderError("unreadable_file", "dwg2dxf produced no output")

    from ezdxf.addons import odafc  # optional ODA File Converter

    if odafc.is_installed():  # type: ignore[attr-defined]
        try:
            odafc.convert(str(src), str(dst), replace=True)  # type: ignore[attr-defined]
        except Exception as exc:
            raise ReaderError("unreadable_file", "ODA conversion failed") from exc
        return
    raise ReaderError("dwg_converter_missing")
