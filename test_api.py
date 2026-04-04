import requests
import os
import json
from fpdf import FPDF
import time

def create_dummy_pdf(path):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=15)
    pdf.cell(200, 10, txt="Chapter 1: The Beginning", ln=1, align='C')
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, txt="This is a test paragraph to verify that the PDF extraction and chunking pipeline is working correctly. " * 5)
    pdf.output(path)

API_URL = "http://127.0.0.1:8000/api/chunk-json"
API_KEY = "dev-key-change-me"
PDF_PATH = "test_dummy.pdf"

if __name__ == "__main__":
    print(f"Generating dummy PDF at {PDF_PATH}...")
    create_dummy_pdf(PDF_PATH)
    
    print(f"Sending POST request to {API_URL}...")
    start_time = time.time()
    
    with open(PDF_PATH, "rb") as f:
        files = {"file": ("test_dummy.pdf", f, "application/pdf")}
        data = {
            "words_per_minute": 200,
            "chunk_duration_minutes": 5.0
        }
        headers = {
            "X-API-Key": API_KEY
        }
        
        try:
            response = requests.post(API_URL, files=files, data=data, headers=headers)
            
            print(f"\nResponse Code: {response.status_code}")
            print(f"Time Taken: {time.time() - start_time:.2f} seconds\n")
            
            if response.status_code == 200:
                print("Success! JSON Output:")
                print(json.dumps(response.json(), indent=2))
            else:
                print("Error Output:")
                try:
                    print(json.dumps(response.json(), indent=2))
                except:
                    print(response.text)
                    
        except requests.exceptions.ConnectionError:
            print(f"Failed to connect to {API_URL}. Is the server running?")
        finally:
            if os.path.exists(PDF_PATH):
                os.remove(PDF_PATH)
