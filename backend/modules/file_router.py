"""
modules/file_router.py

Gerbang utama untuk semua upload file. Mendeteksi tipe file dan
meroute ke reader yang tepat (PDF, image, atau CAD).
"""

import os
from pathlib import Path

SUPPORTED_FORMATS: dict[str, dict] = {
    "pdf":  {"category": "pdf",   "mime": ["application/pdf"]},
    "jpg":  {"category": "image", "mime": ["image/jpeg"]},
    "jpeg": {"category": "image", "mime": ["image/jpeg"]},
    "png":  {"category": "image", "mime": ["image/png"]},
    "webp": {"category": "image", "mime": ["image/webp"]},
    "tiff": {"category": "image", "mime": ["image/tiff"]},
    "tif":  {"category": "image", "mime": ["image/tiff"]},
    "bmp":  {"category": "image", "mime": ["image/bmp"]},
    "heic": {"category": "image", "mime": ["image/heic"]},
    "heif": {"category": "image", "mime": ["image/heif"]},
    "dxf":  {"category": "cad",   "mime": ["image/vnd.dxf", "application/dxf"]},
    "dwg":  {"category": "cad",   "mime": ["image/vnd.dwg", "application/acad"]},
}


def detect_file_type(file_path: str) -> dict:
    """
    Deteksi tipe file dari ekstensi.

    Args:
        file_path: Path ke file yang akan dideteksi

    Returns:
        dict dengan extension, category, mime_type, supported, error
    """
    ext = Path(file_path).suffix.lower().lstrip(".")
    if ext not in SUPPORTED_FORMATS:
        return {
            "extension": ext,
            "category": None,
            "mime_type": None,
            "supported": False,
            "error": (
                f"Format .{ext} tidak didukung. "
                f"Format yang didukung: {', '.join(SUPPORTED_FORMATS.keys())}"
            ),
        }
    info = SUPPORTED_FORMATS[ext]
    return {
        "extension": ext,
        "category": info["category"],
        "mime_type": info["mime"][0],
        "supported": True,
        "error": None,
    }


def route_to_reader(
    file_path: str,
    llm_router=None,
    scale: float = None,
) -> dict:
    """
    Entry point utama untuk semua jenis file gambar kerja.

    Args:
        file_path: Path ke file yang diupload
        llm_router: Instance LLMRouter
        scale: Skala gambar (None = auto-detect)

    Returns:
        Format standar dimensi JSON (sama untuk semua tipe file)
    """
    file_info = detect_file_type(file_path)

    if not file_info["supported"]:
        return {"status": "error", "message": file_info["error"]}

    if file_info["category"] == "pdf":
        from modules.pdf_reader import extract_dimensions_from_pdf
        return extract_dimensions_from_pdf(file_path, scale=scale, llm_router=llm_router)

    elif file_info["category"] == "image":
        from modules.image_reader import extract_dimensions_from_image
        return extract_dimensions_from_image(file_path, scale=scale, llm_router=llm_router)

    elif file_info["category"] == "cad":
        if file_info["extension"] == "dwg":
            return {
                "status": "error",
                "message": (
                    "File DWG perlu dikonversi ke DXF terlebih dahulu. "
                    "Gunakan ODA File Converter (gratis): "
                    "https://www.opendesign.com/guestfiles/oda_file_Converter"
                ),
            }
        from modules.dxf_reader import extract_dimensions_from_dxf
        return extract_dimensions_from_dxf(file_path)

    return {"status": "error", "message": "Tipe file tidak dikenali"}
