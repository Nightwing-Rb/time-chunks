import os
import shutil
import tempfile
import uuid
import traceback
from typing import Annotated

from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
import logging

from models import HealthResponse, ErrorResponse
from extractor import extract_elements
from chunker import generate_chunks
from pdf_generator import generate_single_pdf

app = FastAPI(title="PDF Reading-Time Chunker")
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
          })
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
