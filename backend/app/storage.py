"""File storage on a shared volume (`DATA_DIR`), mounted into the API and the worker.

Aiven has no object store, so files live on the volume and everything else in
Postgres. To deploy API and worker on different hosts, swap this for S3/R2 behind
the same three functions.
"""

import uuid
from pathlib import Path

from app.config import get_settings


def document_dir(document_id: uuid.UUID) -> Path:
    return get_settings().data_dir / "documents" / str(document_id)


def original_path(document_id: uuid.UUID, extension: str) -> Path:
    return document_dir(document_id) / f"original{extension}"


def page_image_path(document_id: uuid.UUID, page_index: int) -> Path:
    return document_dir(document_id) / "pages" / f"{page_index}.png"


def model_ifc_path(document_id: uuid.UUID) -> Path:
    """Generated IFC for drawings; for IFC uploads the original is the model."""
    return document_dir(document_id) / "model.ifc"


def mesh_path(document_id: uuid.UUID) -> Path:
    return document_dir(document_id) / "mesh.json.gz"  # gzip: meshes compress about 5x


def write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)  # atomic: readers never see half a file
