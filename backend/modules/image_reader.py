"""
modules/image_reader.py

Ekstraksi dimensi dari file gambar raster (JPG, PNG, WEBP, TIFF, BMP, HEIC).
Menggunakan 2 layer:
  Layer 1: PaddleOCR — ekstraksi teks dari gambar (cepat, akurat untuk angka)
  Layer 2: 9router Vision — analisis gambar secara komprehensif (fallback + verifikasi)
"""

import base64
import json
import os
import re
from pathlib import Path
from typing import Optional

from PIL import Image

NEEDS_CONVERSION: set[str] = {".heic", ".heif", ".tiff", ".tif", ".bmp", ".webp"}


def _normalize_image(file_path: str) -> tuple[str, bool]:
    """
    Normalisasi gambar ke format PNG untuk kompatibilitas maksimal.

    Menangani:
    - HEIC/HEIF: foto iPhone (butuh pillow-heif)
    - TIFF multi-halaman: ambil halaman pertama
    - BMP: konversi ke PNG
    - Gambar terlalu besar: resize ke max 4096px
    - Gambar terlalu kecil: upscale ke min 800px

    Returns:
        (path_normalized, was_converted)
    """
    ext = Path(file_path).suffix.lower()
    output_path = file_path.replace(ext, "_normalized.png")

    try:
        if ext in {".heic", ".heif"}:
            try:
                import pillow_heif
                pillow_heif.register_heif_opener()
            except ImportError:
                raise ImportError(
                    "pillow-heif diperlukan untuk file HEIC. "
                    "Install dengan: pip install pillow-heif"
                )

        img = Image.open(file_path)

        if ext in {".tiff", ".tif"}:
            img.seek(0)

        if img.mode in ("RGBA", "LA", "P"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            mask = img.split()[-1] if img.mode in ("RGBA", "LA") else None
            background.paste(img, mask=mask)
            img = background
        elif img.mode != "RGB":
            img = img.convert("RGB")

        max_dim = 4096
        w, h = img.size
        if max(w, h) > max_dim:
            ratio = max_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        min_dim = 800
        w, h = img.size
        if max(w, h) < min_dim:
            ratio = min_dim / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

        img.save(output_path, "PNG", optimize=True)
        return output_path, (ext != ".png")

    except Exception as e:
        raise RuntimeError(f"Gagal normalisasi gambar {file_path}: {e}")


def _image_to_base64(file_path: str) -> str:
    """Konversi file gambar ke base64 string."""
    with open(file_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def _ocr_image(image_path: str) -> list[dict]:
    """
    Layer 1: PaddleOCR — ekstrak semua teks dari gambar.

    Returns:
        list of {text, confidence, bbox}
    """
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    result = ocr.ocr(image_path, cls=True)

    extracted: list[dict] = []
    if not result or not result[0]:
        return extracted

    for line in result[0]:
        bbox, (text, confidence) = line
        xs = [p[0] for p in bbox]
        ys = [p[1] for p in bbox]
        extracted.append({
            "text": text,
            "confidence": round(confidence, 3),
            "bbox": [min(xs), min(ys), max(xs), max(ys)],
        })
    return extracted


def _analyze_with_vision(
    image_path: str,
    llm_router,
    ocr_texts: Optional[list[dict]] = None,
) -> list[dict]:
    """
    Layer 2: 9router Vision — analisis komprehensif gambar kerja.

    Args:
        image_path: Path ke gambar (sudah dinormalisasi)
        llm_router: Instance LLMRouter
        ocr_texts: Hasil OCR Layer 1 untuk konteks tambahan

    Returns:
        list of dimension items
    """
    img_b64 = _image_to_base64(image_path)

    ocr_context = ""
    if ocr_texts:
        ocr_list = [f"'{t['text']}' (conf: {t['confidence']})" for t in ocr_texts[:50]]
        ocr_context = f"\n\nTeks yang terdeteksi OCR (untuk referensi):\n{', '.join(ocr_list)}"

    prompt = f"""Kamu adalah sistem ekstraksi data teknis dari gambar kerja konstruksi Indonesia.
Analisis gambar ini secara menyeluruh dan ekstrak SEMUA dimensi elemen bangunan.{ocr_context}

Untuk setiap elemen bangunan yang punya dimensi, return JSON array:
[
  {{
    "nama_item": "nama elemen dalam bahasa Indonesia (contoh: Galian Tanah Pondasi)",
    "P": angka_panjang_meter_atau_null,
    "L": angka_lebar_meter_atau_null,
    "T": angka_tinggi_atau_kedalaman_meter_atau_null,
    "satuan": "m³ atau m² atau m",
    "confidence": nilai_0.0_sampai_1.0,
    "skala_terdeteksi": "1:100 atau null jika tidak ada",
    "catatan": "keterangan ambiguitas atau asumsi yang dibuat"
  }}
]

ATURAN PENTING:
- Semua dimensi HARUS dalam METER. Konversi jika gambar pakai cm atau mm.
- Jika gambar punya keterangan skala (misal 1:100), gunakan untuk konversi ukuran di gambar.
- Jika dimensi tidak terbaca jelas: null (BUKAN 0, BUKAN estimasi tanpa dasar).
- Jika tidak yakin suatu dimensi: turunkan confidence di bawah 0.70.
- Bedakan item 3D (galian, beton, urugan → m³) vs 2D (plesteran, cat → m²) vs 1D (panjang besi → m).
- Return JSON array SAJA. Tanpa preamble, tanpa penjelasan, tanpa markdown.
"""

    response = llm_router.call("extract_image", prompt, image_b64=img_b64)

    try:
        clean = re.sub(r'```json\s*|\s*```', '', response.strip())
        return json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []


def extract_dimensions_from_image(
    file_path: str,
    scale: float = None,
    llm_router=None,
) -> dict:
    """
    Ekstrak dimensi dari file gambar raster.

    Args:
        file_path: Path ke file gambar (JPG/PNG/WEBP/TIFF/BMP/HEIC)
        scale: Skala gambar. None = auto-detect.
        llm_router: Instance LLMRouter. Wajib untuk Layer 2 (Vision).

    Returns:
        dict dengan status, source, file_type, items, items_flagged
    """
    if llm_router is None:
        return {"status": "error", "message": "llm_router wajib untuk pemrosesan gambar"}

    file_ext = Path(file_path).suffix.lower().lstrip(".")

    try:
        normalized_path, was_converted = _normalize_image(file_path)

        ocr_results = _ocr_image(normalized_path)
        vision_items = _analyze_with_vision(normalized_path, llm_router, ocr_results)

        items_ok: list[dict] = []
        items_flagged: list[dict] = []

        for item in vision_items:
            if scale:
                if item.get("P"):
                    item["P"] = round(item["P"] * scale, 3)
                if item.get("L"):
                    item["L"] = round(item["L"] * scale, 3)
                if item.get("T"):
                    item["T"] = round(item["T"] * scale, 3)

            item["sumber"] = f"Gambar {file_ext.upper()}: {os.path.basename(file_path)}"

            if item.get("confidence", 1.0) >= 0.7:
                items_ok.append(item)
            else:
                item["alasan_flag"] = item.get("catatan", "Confidence rendah — perlu verifikasi manual")
                items_flagged.append(item)

        if was_converted and os.path.exists(normalized_path):
            os.unlink(normalized_path)

        scale_detected = None
        for item in vision_items:
            if item.get("skala_terdeteksi"):
                scale_detected = item["skala_terdeteksi"]
                break

        return {
            "status": "ok",
            "source": "paddleocr+9router_vision",
            "file_type": file_ext,
            "scale_detected": scale_detected,
            "total_items": len(items_ok) + len(items_flagged),
            "items": items_ok,
            "items_flagged": items_flagged,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Gagal memproses gambar: {str(e)}",
            "file_type": file_ext,
        }
