# PDF Reading-Time Chunker

A FastAPI-based microservice that extracts text from PDF documents and chunks them into logical sections based on estimated reading time.

## Features
- **PDF Extraction**: High-fidelity text extraction using `opendataloader-pdf`.
- **Time-Based Chunking**: Split documents into sections based on a target reading time (e.g., "5-minute chunks").
- **PDF Generation**: Returns a new PDF where each chunk starts on a new page.
- **Dockerized**: Easy deployment with Python 3.10 and Java 17 pre-configured.

## Prerequisites
- [Docker](https://www.docker.com/) and [Docker Compose](https://docs.docker.com/compose/)

## Quick Start
1.  **Clone the repository**:
    ```bash
    git clone https://github.com/Nightwing-Rb/time-chunks.git
    cd time-chunks
    ```
2.  **Start the service**:
    ```bash
    docker-compose up
    ```
3.  **Verify**: Open `http://localhost:8000/api/health`
4.  **Mobile Access**: Both your phone and computer must be on the **same Wi-Fi network**. Use your computer's local IP address (e.g., `192.168.0.39`) to access the API from your phone: `http://192.168.0.39:8000/api/health`

## Mobile Connectivity Guide

To access the API from a mobile device or a physical Android/iOS device:

1.  **Network**: Connect both your phone and PC to the same Wi-Fi.
2.  **Local IP**: Find your PC's local IP. On Windows, run `ipconfig` and look for the IPv4 Address under the Wi-Fi adapter (e.g., `192.168.0.39`).
3.  **URL**: Use `http://<YOUR_LOCAL_IP>:8000` as the base URL.
4.  **Firewall**: Ensure your Windows Firewall allows inbound connections on port `8000`. You may need to create an Inbound Rule in Windows Defender Firewall for TCP port 8000.

## API Endpoints

### Health Check
- **URL**: `GET /api/health`
- **Response**: `{"status": "ok"}`

### Chunk PDF
- **URL**: `POST /api/chunk`
- **Parameters** (Form Data):
  - `file`: The PDF file to upload.
  - `words_per_minute`: Average reading speed (default recommended: 200).
  - `chunk_duration_minutes`: Desired duration for each chunk in minutes.
- **Response**: A processed PDF file containing reorganized chunks.

## Tech Stack
- **Backend**: FastAPI
- **Extraction**: `opendataloader-pdf`
- **PDF Creation**: `reportlab`
- **Runtime**: Python 3.10 + OpenJDK 17
