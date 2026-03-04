import csv
import io
import requests
from typing import List

from .document_loading_base import DocumentLoadingBase
from ..common.source_document import SourceDocument

_CHUNK_ROWS = 50  # Number of rows per SourceDocument chunk


class CsvDocumentLoading(DocumentLoadingBase):
    """Load a CSV file from a URL and convert rows into SourceDocuments."""

    def __init__(self) -> None:
        super().__init__()

    def load(self, document_url: str) -> List[SourceDocument]:
        response = requests.get(document_url, timeout=60)
        response.raise_for_status()

        # Decode the CSV content
        content_text = response.content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content_text))
        rows = list(reader)

        if not rows:
            return []

        documents: List[SourceDocument] = []
        for chunk_start in range(0, len(rows), _CHUNK_ROWS):
            chunk_rows = rows[chunk_start : chunk_start + _CHUNK_ROWS]
            lines = []
            for row in chunk_rows:
                line = ", ".join(
                    f"{k}: {v}" for k, v in row.items() if v not in (None, "")
                )
                lines.append(line)
            chunk_content = "\n".join(lines)
            documents.append(
                SourceDocument(
                    content=chunk_content,
                    source=document_url,
                    page_number=chunk_start // _CHUNK_ROWS + 1,
                    offset=chunk_start,
                )
            )

        return documents
