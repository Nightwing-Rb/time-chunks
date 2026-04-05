import os
import json
import opendataloader_pdf
import logging
from typing import List, Dict, Any
from models import FlattenedElement

logger = logging.getLogger(__name__)


def extract_metadata(pdf_path: str) -> Dict[str, Any]:
    """
    Extract basic metadata (title, author) from a PDF file.
    Uses PyPDF2 as it's lightweight and doesn't need Java.
    Falls back gracefully if metadata is missing.
    """
    metadata = {"title": None, "author": None}
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(pdf_path)
        info = reader.metadata
        if info:
            raw_title = info.get("/Title", "") or ""
            raw_author = info.get("/Author", "") or ""
            # Only use if it looks like a real title (not a filename or UUID)
            if raw_title and len(raw_title) > 2 and not raw_title.endswith(".pdf"):
                metadata["title"] = raw_title.strip()
            if raw_author and len(raw_author) > 1:
                metadata["author"] = raw_author.strip()
    except ImportError:
        logger.warning("PyPDF2 not installed. Skipping metadata extraction.")
    except Exception as e:
        logger.warning(f"Failed to extract metadata: {e}")
    return metadata


def extract_elements(pdf_path: str, output_dir: str) -> List[FlattenedElement]:
    """
    Runs opendataloader-pdf on the given PDF file, parses the resulting JSON,
    and flattens the hierarchy into a sequential list of FlattenedElement.
    """
    # 1. Run extraction (creates JSON file in output_dir)
    opendataloader_pdf.convert(
        input_path=[pdf_path],
        output_dir=output_dir,
        format="json",
        image_output="embedded",  # Extract images inline as base64
        image_format="jpeg",
    )

    # Figure out the expected JSON filename
    base_name = os.path.splitext(os.path.basename(pdf_path))[0]
    json_path = os.path.join(output_dir, f"{base_name}.json")

    if not os.path.exists(json_path):
        raise RuntimeError(f"Extraction failed. Expected JSON at {json_path}")

    # 2. Parse JSON and flatten
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    flat_list = []

    # Document kids represent top-level elements for each page
    if "kids" in data:
        for kid in data["kids"]:
            _flatten_node(kid, flat_list)

    # 3. Post-Process: Chapter Number Merging
    flat_list = _merge_chapter_numbers(flat_list)

    return flat_list


def _merge_chapter_numbers(elements: List[FlattenedElement]) -> List[FlattenedElement]:
    """
    Standalone number headings like "1" get merged with the adjacent
    chapter title heading to prevent them splitting into separate lines.
    Only merges if a pure digit heading is immediately followed by another heading of the same or higher level.
    """
    import re

    merged: List[FlattenedElement] = []
    skip_next = False

    for i, element in enumerate(elements):
        if skip_next:
            skip_next = False
            continue

        is_number_heading = element.type == "heading" and re.match(
            r"^\d+$", element.content.strip()
        )

        if not is_number_heading:
            merged.append(element)
            continue

        num = element.content.strip()

        # Look FORWARD: next block might be the chapter title
        if (
            i + 1 < len(elements)
            and elements[i + 1].type == "heading"
            and not re.match(r"^\d+$", elements[i + 1].content.strip())
        ):
            nxt = elements[i + 1]

            # Ensure it's effectively a chapter title (e.g., heading level is same or higher (which means smaller int))
            if (
                element.heading_level
                and nxt.heading_level
                and nxt.heading_level <= element.heading_level
            ):
                new_content = f"Chapter {num}: {nxt.content}"
                merged.append(
                    FlattenedElement(
                        type="heading",
                        content=new_content,
                        page_number=element.page_number,
                        word_count=len(new_content.split()),
                        heading_level=min(element.heading_level, nxt.heading_level),
                    )
                )
                skip_next = True
                continue

        # If no forward match, just leave it as is
        merged.append(element)

    return merged


def _flatten_node(node: Dict[str, Any], result: List[FlattenedElement]):
    """
    Recursively walk the opendataloader AST and flatten into `result`.
    """
    node_type = node.get("type")
    page_number = node.get("page number", 1)

    if node_type == "image":
        image_source = node.get("data", "")
        if image_source:
            result.append(
                FlattenedElement(
                    type="image",
                    page_number=page_number,
                    word_count=0,
                    image_source=image_source,
                    image_format=node.get("format", "jpeg"),
                )
            )

    elif node_type == "paragraph":
        content = node.get("content", "").strip()
        if content:
            result.append(
                FlattenedElement(
                    type="paragraph",
                    content=content,
                    page_number=page_number,
                    word_count=len(content.split()),
                )
            )

    elif node_type == "heading":
        content = node.get("content", "").strip()
        if content:
            result.append(
                FlattenedElement(
                    type="heading",
                    content=content,
                    page_number=page_number,
                    word_count=len(content.split()),
                    heading_level=node.get("heading level", 1),
                )
            )

    elif node_type == "caption":
        content = node.get("content", "").strip()
        if content:
            result.append(
                FlattenedElement(
                    type="caption",
                    content=content,
                    page_number=page_number,
                    word_count=len(content.split()),
                )
            )

    elif node_type == "table":
        # Extract row/cell data
        rows_data = []
        total_words = 0
        if "rows" in node:
            for row in node["rows"]:
                cells_data = []
                if "cells" in row:
                    for cell in row["cells"]:
                        # Extract text from the cell's kids
                        cell_content = []
                        _extract_text_only(cell.get("kids", []), cell_content)
                        cell_text = " ".join(cell_content).strip()
                        cells_data.append(cell_text)
                        total_words += len(cell_text.split())
                rows_data.append(cells_data)

        if rows_data:
            result.append(
                FlattenedElement(
                    type="table",
                    table_data=rows_data,
                    page_number=page_number,
                    word_count=total_words,
                )
            )

    elif node_type == "list":
        # Process the entire list as a SINGLE atomic element so it never splits across chunks
        list_style = node.get("numbering style", "bullet")
        lines: List[str] = []
        if "list items" in node:
            for item in node["list items"]:
                item_content_parts = []
                c = item.get("content", "").strip()
                if c:
                    item_content_parts.append(f"• {c}")

                # Fetch nested kids
                nested_parts = []
                _extract_text_only(item.get("kids", []), nested_parts)
                if nested_parts:
                    item_content_parts.append(" ".join(nested_parts).strip())

                lines.append("\n  ".join(item_content_parts))

        full_content = "\n".join(lines).strip()
        if full_content:
            result.append(
                FlattenedElement(
                    type="list",
                    content=full_content,
                    page_number=page_number,
                    word_count=len(full_content.split()),
                    list_style=list_style,
                )
            )

    elif node_type == "text block":
        # Fall through and just rip the kids out
        if "kids" in node:
            for kid in node["kids"]:
                _flatten_node(kid, result)

    # ignore headers/footers and other unrecognized node types


def _extract_text_only(kids: List[Dict[str, Any]], out_texts: List[str]):
    """Helper to just pull raw text bytes from nested structures like table cells."""
    for kid in kids:
        if "content" in kid:
            out_texts.append(kid["content"])
        if "kids" in kid:
            _extract_text_only(kid["kids"], out_texts)
