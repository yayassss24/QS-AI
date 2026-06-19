# QS BOQ AI Extension

Ekstraksi dimensi gambar kerja konstruksi dan generate BOQ (Bill of Quantity) otomatis berbasis AI. Mendukung PDF, gambar (JPG/PNG), dan DXF dengan unified LLM gateway via 9router.

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌──────────────┐
│  Excel Add-in   │────▶│                  │     │              │
│  (Office JS)    │     │                  │────▶│   9router    │
├─────────────────┤     │  FastAPI Backend  │     │  AI Gateway  │
│  Google Sheets  │────▶│  (Python 3.11)   │────▶│              │
│  Add-on (GAS)   │     │                  │     └──────────────┘
└─────────────────┘     │  + BYOK(AES-256) │
                        │  + Rate Limit    │
                        └──────────────────┘
```

## Tech Stack

- **Backend:** FastAPI (Python 3.11), uvicorn
- **LLM Gateway:** 9router (unified API — gantikan Gemini/Groq/OpenRouter)
- **PDF:** PyMuPDF, PaddleOCR (opsional)
- **Image:** Pillow, 9router Vision
- **CAD:** ezdxf
- **Excel:** openpyxl
- **Security:** BYOK (Bring Your Own Key) with Fernet AES-256
- **Rate Limiting:** Redis (opsional, fallback in-memory)

## Setup

### Backend

```bash
cd backend
pip install -r requirements.txt

# Optional heavy dependencies:
# pip install paddlepaddle paddleocr  # OCR (~2.6GB)
# pip install pillow-heif             # HEIC/HEIF support

cp .env.example .env
# Edit .env with your API keys
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Environment Variables

| Variable | Required | Description |
|---|---|---|---|
| `9ROUTER_API_KEY` | Yes | 9router API key (sk-...) |
| `9ROUTER_BASE_URL` | No | 9router base URL (default: https://api.9router.ai/v1) |
| `9ROUTER_MODEL` | No | Model untuk teks (default: gpt-4o-mini) |
| `9ROUTER_VISION_MODEL` | No | Model untuk vision (default: gpt-4o) |
| `BYOK_ENCRYPTION_KEY` | Yes | Fernet key for BYOK encryption |
| `REDIS_URL` | No | Redis for rate limiting (default: in-memory) |
| `DEBUG` | No | Enable debug mode (default: false) |

Generate BYOK key:
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/api/health` | Health check |
| `POST` | `/api/extract-file` | Extract dimensions from PDF/image/DXF |
| `POST` | `/api/detect-template` | Detect Excel BOQ template structure |
| `POST` | `/api/generate-boq` | Generate BOQ Excel file with formulas |
| `POST` | `/api/compute-boq` | Compute BOQ formulas (returns JSON, needs template file) |
| `POST` | `/api/compute-boq-from-json` | Compute BOQ from JSON headers (for Excel Add-in) |
| `POST` | `/api/chat` | QS Assistant chat |
| `POST` | `/api/byok/validate` | Validate BYOK API key |
| `POST` | `/api/byok/save` | Save BYOK key (encrypted) |
| `POST` | `/api/byok/delete` | Delete BYOK key |

## Frontends

### Google Sheets Add-on
1. Buka `google-sheets-addon/`
2. Deploy `Code.gs` ke AppsScript project
3. Upload `Sidebar.html` sebagai file HTML
4. Update `BACKEND_URL` di `Code.gs`

### Excel Add-in
1. Sideload `excel-addin/manifest.xml` ke Excel
2. Konfigurasi backend via `?backend=` query parameter

## Docker

```bash
docker build -t qs-boq-ai .
docker run -p 8000:8000 --env-file backend/.env qs-boq-ai
```

## Testing

```bash
cd backend
pytest tests/ -v
```

## Security Notes

- API key ada di `.env` (sudah di `.gitignore`)
- BYOK key dienkripsi AES-256 sebelum disimpan
- Key tidak pernah dikirim kembali ke client
- Endpoint BYOK divalidasi sebelum disimpan
