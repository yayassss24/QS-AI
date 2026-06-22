"""
modules/pdf_reader.py

Ekstraksi dimensi dari file PDF gambar kerja konstruksi.
Menggunakan 3 layer:
  Layer 1: PyMuPDF — PDF vector (paling akurat, paling cepat)
  Layer 2: PaddleOCR — PDF scan / gambar foto
  Layer 3: 9router Vision — fallback untuk gambar kompleks
"""

import base64
import json
import re
import tempfile
from pathlib import Path
from typing import Optional, Union


def _extract_vector_pdf(file_path: str) -> list[dict]:
    """
    Layer 1: Ekstrak teks dari PDF vector menggunakan PyMuPDF.
    Cocok untuk PDF langsung dari AutoCAD/Revit.

    Args:
        file_path: Path ke file PDF

    Returns:
        list of {page, raw_texts}
    """
    import fitz
    doc = fitz.open(file_path)
    results: list[dict] = []
    for page_num, page in enumerate(doc):
        blocks = page.get_text("dict")["blocks"]
        texts: list[dict] = []
        for block in blocks:
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        texts.append({
                            "text": span.get("text", "").strip(),
                            "bbox": list(span.get("bbox", [])),
                            "font": span.get("font", ""),
                            "size": span.get("size", 0),
                        })
        results.append({"page": page_num + 1, "raw_texts": texts})
    doc.close()
    return results


def _extract_scanned_pdf(file_path: str) -> list[dict]:
    """
    Layer 2: Ekstrak teks dari PDF scan menggunakan PaddleOCR.

    Args:
        file_path: Path ke file PDF

    Returns:
        list of {page, ocr_result}
    """
    from paddleocr import PaddleOCR
    import fitz
    ocr = PaddleOCR(use_angle_cls=True, lang='en', show_log=False)
    doc = fitz.open(file_path)
    results: list[dict] = []
    for page_num, page in enumerate(doc):
        mat = fitz.Matrix(2, 2)
        clip = page.get_pixmap(matrix=mat)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            img_path = tmp.name
            clip.save(img_path)
        try:
            result = ocr.ocr(img_path, cls=True)
            extracted = []
            if result and result[0]:
                for line in result[0]:
                    bbox, (text, confidence) = line
                    xs = [p[0] for p in bbox]
                    ys = [p[1] for p in bbox]
                    extracted.append({
                        "text": text,
                        "confidence": round(confidence, 3),
                        "bbox": [min(xs), min(ys), max(xs), max(ys)],
                    })
            results.append({"page": page_num + 1, "ocr_result": extracted})
        finally:
            import os
            if os.path.exists(img_path):
                os.unlink(img_path)
    doc.close()
    return results


def _process_vision_page(args):
    page_num, page, llm_router = args
    mat = fitz.Matrix(2, 2)
    clip = page.get_pixmap(matrix=mat)
    img_bytes = clip.tobytes("png")
    img_b64 = base64.b64encode(img_bytes).decode()

    prompt = """
Kamu adalah sistem ekstraksi data teknis dari gambar kerja konstruksi.
Analisis gambar ini dan ekstrak SEMUA dimensi yang terlihat.

Untuk setiap elemen bangunan yang punya dimensi, return JSON array:
[
  {
    "nama_item": "nama elemen pekerjaan dalam bahasa Indonesia",
    "P": angka_panjang_atau_null,
    "L": angka_lebar_atau_null,
    "T": angka_tinggi_atau_null,
    "satuan": "m³|m²|m",
    "confidence": 0.0_sampai_1.0,
    "catatan": "keterangan jika ada ambiguitas"
  }
]

ATURAN:
- Semua dimensi dalam METER (konversi jika perlu)
- Jika dimensi tidak ada/tidak terbaca: null (bukan 0)
- Jika tidak yakin: turunkan confidence di bawah 0.7
- Return JSON array SAJA, tanpa penjelasan tambahan
"""

    response = llm_router.call("extract_image", prompt, image_b64=img_b64)
    try:
        clean = re.sub(r'```json\s*|\s*```', '', response.strip())
        items = json.loads(clean)
    except json.JSONDecodeError:
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                items = json.loads(match.group())
            except Exception:
                items = []
        else:
            items = []
    return {"page": page_num + 1, "items": items}

def _extract_via_9router_vision(
    file_path: str,
    llm_router,
    max_workers: int = 4,
) -> list[dict]:
    """
    Layer 3: Ekstrak dimensi menggunakan 9router Vision sebagai fallback.
    Halaman diproses secara paralel.

    Args:
        file_path: Path ke file PDF
        llm_router: Instance LLMRouter
        max_workers: Jumlah thread paralel

    Returns:
        list of {page, items}
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed
    import fitz
    doc = fitz.open(file_path)
    pages = list(enumerate(doc))
    results = [None] * len(pages)
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_process_vision_page, (num, page, llm_router)): num for num, page in pages}
        for future in as_completed(futures):
            num = futures[future]
            results[num] = future.result()
    doc.close()
    return [r for r in results if r is not None]


def _assess_quality(vector_results: list[dict], ocr_results: list[dict]) -> tuple[bool, bool]:
    """
    Nilai kualitas hasil ekstraksi untuk menentukan perlu fallback.

    Returns:
        (vector_adequate, ocr_adequate)
    """
    vector_total = 0
    for page in vector_results:
        vector_total += len(page.get("raw_texts", []))

    ocr_total = 0
    for page in ocr_results:
        ocr_total += len(page.get("ocr_result", []))

    return (vector_total >= 5, ocr_total >= 3)


def _parse_text_to_dimensions(all_texts: list[dict], llm_router) -> list[dict]:
    """
    Parse extracted PDF text into structured dimension items using LLM.

    Args:
        all_texts: List of {text, page, bbox} from PDF extraction
        llm_router: Instance LLMRouter

    Returns:
        list of dimension items {nama_item, P, L, T, satuan, confidence}
    """
    text_content = "\n".join(
        f"[Halaman {t['page']}] {t['text']}" for t in all_texts[:200]
    )

    prompt = f"""Kamu adalah sistem parsing teks gambar kerja konstruksi Indonesia.
Dari teks yang diekstrak dari file PDF, temukan SEMUA elemen pekerjaan beserta dimensinya.

Teks dari PDF:
{text_content}

Return JSON array:
[
  {{
    "nama_item": "nama elemen pekerjaan dalam bahasa Indonesia",
    "P": angka_panjang_dalam_meter_atau_null,
    "L": angka_lebar_dalam_meter_atau_null,
    "T": angka_tinggi_atau_kedalaman_dalam_meter_atau_null,
    "satuan": "m³ atau m² atau m",
    "confidence": 0.0_sampai_1.0,
    "halaman": nomor_halaman
  }}
]

ATURAN:
- Cari semua angka dimensi (panjang, lebar, tinggi) dari teks
- Konversi ke meter (cm→m, mm→m)
- Jika item tidak punya dimensi numerik: null (bukan 0)
- Item pekerjaan biasanya diawali dengan kata seperti: Galian, Urugan, Beton, Pasangan, Plesteran, Cat, dll
- Perhatikan format kolom pada teks: biasanya ada tabel dengan format Uraian | P | L | T | Volume
- Jika tidak ada item yang bisa diekstrak: return []
- Return JSON array SAJA, tanpa penjelasan tambahan
"""

    response = llm_router.call("parse_dimensions", prompt)
    try:
        clean = re.sub(r'```json\s*|\s*```', '', response.strip())
        items = json.loads(clean)
        if not isinstance(items, list):
            return []
        return items
    except (json.JSONDecodeError, Exception):
        match = re.search(r'\[.*\]', response, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        return []


def extract_dimensions_from_pdf(
    file_path: str,
    scale: float = None,
    llm_router=None,
) -> dict:
    """
    Ekstrak dimensi dari file PDF gambar kerja konstruksi.
    Menggunakan 3 layer dengan fallback otomatis.

    Args:
        file_path: Path ke file PDF
        scale: Skala gambar (None = auto-detect)
        llm_router: Instance LLMRouter (wajib untuk Layer 3)

    Returns:
        dict dengan status, source, items, items_flagged
    """
    def _apply_scale(items_list: list[dict], scale_val: Optional[float]) -> list[dict]:
        if scale_val is None or scale_val == 1.0:
            return items_list
        for item in items_list:
            if item.get("P") is not None:
                item["P"] = round(item["P"] * scale_val, 4)
            if item.get("L") is not None:
                item["L"] = round(item["L"] * scale_val, 4)
            if item.get("T") is not None:
                item["T"] = round(item["T"] * scale_val, 4)
        return items_list

    try:
        vector_results = _extract_vector_pdf(file_path)
        vector_ok, _ = _assess_quality(vector_results, [])
        source = "pymupdf"
        all_texts: list[dict] = []

        if vector_ok:
            source = "pymupdf"
            for page in vector_results:
                for t in page.get("raw_texts", []):
                    all_texts.append({
                        "text": t["text"],
                        "page": page["page"],
                        "bbox": t.get("bbox"),
                    })
        else:
            ocr_results = _extract_scanned_pdf(file_path)
            _, ocr_ok = _assess_quality(vector_results, ocr_results)
            if ocr_ok:
                source = "paddleocr"
                for page in ocr_results:
                    for t in page.get("ocr_result", []):
                        all_texts.append({
                            "text": t["text"],
                            "page": page["page"],
                            "bbox": t.get("bbox"),
                            "confidence": t.get("confidence"),
                        })

        # Priority:
        #   Vector PDF → text parse (cepat, akurat untuk PDF asli dari CAD/Revit)
        #   Scanned PDF → OCR + text parse dulu (lebih murah),
        #     fallback Vision kalau semua dimensi null (OCR gagal baca angka)
        if llm_router:
            if vector_ok:
                try:
                    parsed = _parse_text_to_dimensions(all_texts, llm_router)
                    if parsed:
                        parsed = _apply_scale(parsed, scale)
                        return {
                            "status": "ok",
                            "source": "pymupdf+llm",
                            "scale_detected": scale,
                            "items": parsed,
                            "items_flagged": [],
                        }
                except Exception:
                    pass
            else:
                try:
                    parsed = _parse_text_to_dimensions(all_texts, llm_router)
                    if parsed:
                        parsed = _apply_scale(parsed, scale)
                        has_numeric = any(
                            item.get("P") is not None
                            or item.get("L") is not None
                            or item.get("T") is not None
                            for item in parsed
                        )
                        if has_numeric:
                            return {
                                "status": "ok",
                                "source": "paddleocr+llm",
                                "scale_detected": scale,
                                "items": parsed,
                                "items_flagged": [],
                            }
                except Exception:
                    pass

            try:
                vision_results = _extract_via_9router_vision(file_path, llm_router)
                items_ok = []
                items_flagged = []
                for page in vision_results:
                    for item in page.get("items", []):
                        item["sumber"] = f"PDF halaman {page['page']}"
                        item["halaman"] = page["page"]
                        if item.get("confidence", 1.0) >= 0.7:
                            items_ok.append(item)
                        else:
                            item["alasan_flag"] = item.get("catatan", "Confidence rendah")
                            items_flagged.append(item)
                if items_ok or items_flagged:
                    items_ok = _apply_scale(items_ok, scale)
                    items_flagged = _apply_scale(items_flagged, scale)
                    return {
                        "status": "ok",
                        "source": "9router_vision",
                        "scale_detected": scale,
                        "items": items_ok,
                        "items_flagged": items_flagged,
                    }
            except Exception:
                pass

        if not all_texts:
            return {
                "status": "ok",
                "source": source,
                "message": "Tidak ada teks yang bisa diekstrak",
                "items": [],
                "items_flagged": [],
            }

        items_ok = []
        items_flagged = []
        for t in all_texts:
            items_ok.append({
                "nama_item": f"Teks dari halaman {t['page']}",
                "P": None,
                "L": None,
                "T": None,
                "satuan": "m³",
                "confidence": 1.0,
                "halaman": t["page"],
                "sumber": f"PDF halaman {t['page']}",
                "teks_mentah": t["text"],
            })

        items_ok = _apply_scale(items_ok, scale)

        return {
            "status": "ok",
            "source": source,
            "scale_detected": scale,
            "items": items_ok,
            "items_flagged": items_flagged,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": f"Gagal memproses PDF: {str(e)}",
        }
