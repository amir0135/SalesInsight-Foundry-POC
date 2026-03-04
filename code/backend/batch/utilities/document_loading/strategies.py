from enum import Enum
from .csv_document import CsvDocumentLoading
from .layout import LayoutDocumentLoading
from .read import ReadDocumentLoading
from .web import WebDocumentLoading
from .word_document import WordDocumentLoading


class LoadingStrategy(Enum):
    LAYOUT = "layout"
    READ = "read"
    WEB = "web"
    DOCX = "docx"
    CSV = "csv"


def get_document_loader(loader_strategy: str):
    if loader_strategy == LoadingStrategy.LAYOUT.value:
        return LayoutDocumentLoading()
    elif loader_strategy == LoadingStrategy.READ.value:
        return ReadDocumentLoading()
    elif loader_strategy == LoadingStrategy.WEB.value:
        return WebDocumentLoading()
    elif loader_strategy == LoadingStrategy.DOCX.value:
        return WordDocumentLoading()
    elif loader_strategy == LoadingStrategy.CSV.value:
        return CsvDocumentLoading()
    else:
        raise Exception(f"Unknown loader strategy: {loader_strategy}")
