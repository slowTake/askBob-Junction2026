"""Why a document failed to process, in words a user can act on.

Readers raise ReaderError with one of these codes; the API shows the message.
Codes not listed here fall back to the generic message.
"""

MESSAGES: dict[str, str] = {
    "ingest_failed": "Processing failed. Try uploading the file again.",
    "unreadable_file": (
        "The file could not be read. It may be damaged or in an unsupported variant."
    ),
    "encrypted_pdf": "The PDF is password-protected. Upload an unprotected copy.",
    "empty_drawing": "The file contains no drawing to read.",
    "dwg_converter_missing": (
        "DWG files need a converter on the server (LibreDWG dwg2dxf or ODA File Converter). "
        "Export the drawing as DXF and upload that instead."
    ),
}


def error_message(code: str | None) -> str | None:
    if code is None:
        return None
    return MESSAGES.get(code, MESSAGES["ingest_failed"])
