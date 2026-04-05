from pydantic import BaseModel
from typing import List, Optional, Any


class HealthResponse(BaseModel):
    status: str = "ok"


class FlattenedElement(BaseModel):
    """
    A single block of content extracted from the PDF, flattened from the
    recursive opendataloader schema into a simple sequential list for chunking.
    """

    type: str
    content: str = ""
    word_count: int = 0
    page_number: int
    heading_level: Optional[int] = None
    table_data: Optional[List[List[Any]]] = (
        None  # For tables: list of rows, where each row is a list of cell contents
    )
    list_style: Optional[str] = None  # For lists: 'bullet', 'ordered', etc.
    image_source: Optional[str] = None  # Base64 encoded image data if 'embedded'
    image_format: Optional[str] = None  # 'png', 'jpeg', etc.


class Chunk(BaseModel):
    """
    A group of elements that make up one chunk.
    """

    chunk_number: int
    elements: List[FlattenedElement]
    total_words: int
    estimated_minutes: float


class ErrorResponse(BaseModel):
    detail: str
