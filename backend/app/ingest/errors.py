"""A reader failure whose cause we know, with a code from app/domain/ingest_errors.py."""


class ReaderError(Exception):
    def __init__(self, code: str, detail: str = "") -> None:
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
