import os
import shutil
import tempfile
import uuid
import traceback
from typing import Annotated

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse
import logging

from models import HealthResponse, ErrorResponse
from extractor import extract_elements, extract_metadata
from chunker import generate_chunks
from pdf_generator import generate_single_pdf

app = FastAPI(title="PDF Reading-Time Chunker")

# --- API Key Authentication ---
API_KEY = os.environ.get("API_KEY", "dev-key-change-me")

async def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return x_api_key
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@app.get("/api/health", response_model=HealthResponse)
def health_check():
    return HealthResponse(status="ok")

@app.post("/api/chunk", 
          responses={
              200: {"content": {"application/pdf": {}}},
              422: {"model": ErrorResponse},
              500: {"model": ErrorResponse}
          },
          dependencies=[Depends(verify_api_key)])
async def chunk_pdf(
    file: Annotated[UploadFile, File(...)],
    words_per_minute: Annotated[int, Form(ge=50, le=1000)],
    chunk_duration_minutes: Annotated[float, Form(gt=0)]
):
    """
    Receives a PDF and reading parameters. Returns a single PDF where each 
    time-based chunk starts on a new page.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Uploaded file must be a PDF")
        
    temp_dir = tempfile.mkdtemp()
    
    try:
        # [1] Save uploaded PDF to temp dir
        unique_id = str(uuid.uuid4())
        input_pdf_path = os.path.join(temp_dir, f"{unique_id}.pdf")
        
        with open(input_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"Saved upload to {input_pdf_path}. Starting extraction.")
        
        # [2 & 3] Extract and Flatten via opendataloader
        try:
            elements = extract_elements(input_pdf_path, output_dir=temp_dir)
        except Exception as e:
            logger.error(f"Extraction failed: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")
            
        if not elements:
            raise HTTPException(status_code=400, detail="No extractable text found in PDF.")
            
        logger.info(f"Extraction complete. Found {len(elements)} flattened elements.")
        
        # [4] Chunk elements
        chunks = generate_chunks(
            elements=elements, 
            words_per_minute=words_per_minute, 
            duration_minutes=chunk_duration_minutes
        )
        logger.info(f"Chunking complete. Created {len(chunks)} chunks.")
        
        # [5] Build PDF
        try:
            pdf_buffer = generate_single_pdf(chunks)
        except Exception as e:
            logger.error(f"PDF generation failed: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")
            
        logger.info("PDF generated successfully. Streaming response.")
        
        # [6] Return Streaming Response
        headers = {
            'Content-Disposition': f'attachment; filename="chunked_{file.filename}"'
        }
        
        return StreamingResponse(
            pdf_buffer, 
            media_type="application/pdf", 
            headers=headers
        )

    finally:
        # Guaranteed cleanup of raw uploaded PDF and generated JSONs
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory {temp_dir}")


@app.post("/api/chunk-json",
          responses={
              200: {"content": {"application/json": {}}},
              422: {"model": ErrorResponse},
              500: {"model": ErrorResponse}
          },
          dependencies=[Depends(verify_api_key)])
async def chunk_pdf_json(
    file: Annotated[UploadFile, File(...)],
    words_per_minute: Annotated[int, Form(ge=50, le=1000)],
    chunk_duration_minutes: Annotated[float, Form(gt=0)]
):
    """
    Receives a PDF and reading parameters. Returns structured JSON with
    chunks and their elements for use by the Flutter reading app.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=422, detail="Uploaded file must be a PDF")

    temp_dir = tempfile.mkdtemp()

    try:
        # [1] Save uploaded PDF to temp dir
        unique_id = str(uuid.uuid4())
        input_pdf_path = os.path.join(temp_dir, f"{unique_id}.pdf")

        with open(input_pdf_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        logger.info(f"Saved upload to {input_pdf_path}. Starting extraction.")

        # [2] Extract metadata (title, author)
        metadata = extract_metadata(input_pdf_path)

        # [3] Extract structured elements via opendataloader
        try:
            elements = extract_elements(input_pdf_path, output_dir=temp_dir)
        except Exception as e:
            logger.error(f"Extraction failed: {traceback.format_exc()}")
            raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")

        if not elements:
            raise HTTPException(status_code=400, detail="No extractable text found in PDF.")

        logger.info(f"Extraction complete. Found {len(elements)} flattened elements.")

        # [4] Chunk elements
        chunks = generate_chunks(
            elements=elements,
            words_per_minute=words_per_minute,
            duration_minutes=chunk_duration_minutes
        )
        logger.info(f"Chunking complete. Created {len(chunks)} chunks.")

        # [5] Compute total words
        total_words = sum(e.word_count for e in elements)
        total_pages = max((e.page_number for e in elements), default=1)

        # [6] Build JSON response
        chunks_json = []
        for chunk in chunks:
            elements_json = []
            for el in chunk.elements:
                el_dict = {
                    "type": el.type,
                    "content": el.content,
                    "word_count": el.word_count,
                    "page_number": el.page_number,
                }
                if el.heading_level is not None:
                    el_dict["heading_level"] = el.heading_level
                if el.table_data is not None:
                    el_dict["table_data"] = el.table_data
                if el.list_style is not None:
                    el_dict["list_style"] = el.list_style
                if el.image_source is not None:
                    el_dict["image_source"] = el.image_source
                if el.image_format is not None:
                    el_dict["image_format"] = el.image_format
                elements_json.append(el_dict)

            chunks_json.append({
                "chunk_number": chunk.chunk_number,
                "total_words": chunk.total_words,
                "estimated_minutes": chunk.estimated_minutes,
                "elements": elements_json,
            })

        return {
            "title": metadata.get("title"),
            "author": metadata.get("author"),
            "total_words": total_words,
            "total_pages": total_pages,
            "chunks": chunks_json,
        }

    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.info(f"Cleaned up temp directory {temp_dir}")
