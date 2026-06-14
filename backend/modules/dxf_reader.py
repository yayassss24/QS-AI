"""
modules/dxf_reader.py

Ekstraksi dimensi dari file DXF (AutoCAD).
Untuk file DWG: konversi ke DXF dulu menggunakan ODA File Converter.
"""


def extract_dimensions_from_dxf(file_path: str) -> dict:
    """
    Ekstrak dimensi dari file DXF menggunakan ezdxf.

    Args:
        file_path: Path ke file DXF

    Returns:
        dict dengan status, source, dimension_entities, text_labels, lines
    """
    try:
        import ezdxf
    except ImportError:
        return {
            "status": "error",
            "message": "ezdxf tidak terinstal. Install dengan: pip install ezdxf",
        }

    try:
        doc = ezdxf.readfile(file_path)
    except Exception as e:
        return {
            "status": "error",
            "message": f"Gagal membaca file DXF: {str(e)}",
        }

    msp = doc.modelspace()
    items: list[dict] = []

    for entity in msp.query("DIMENSION"):
        try:
            measurement = entity.dxf.actual_measurement
            dimtype = entity.dimtype
            defpoint = entity.dxf.defpoint
            items.append({
                "nama_item": f"Dimensi ({dimtype})",
                "P": round(measurement / 1000, 3),
                "L": None,
                "T": None,
                "satuan": "m",
                "confidence": 1.0,
                "tipe": "dimension_entity",
                "dimtype": dimtype,
                "koordinat": list(defpoint),
            })
        except Exception:
            continue

    labels: list[dict] = []
    for entity in msp.query("TEXT MTEXT"):
        try:
            text = entity.dxf.text if hasattr(entity.dxf, 'text') else entity.text
            insert = entity.dxf.insert if hasattr(entity.dxf, 'insert') else None
            labels.append({
                "teks": text,
                "koordinat": list(insert) if insert else None,
            })
        except Exception:
            continue

    for entity in msp.query("LINE"):
        try:
            start = entity.dxf.start
            end = entity.dxf.end
            length = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2 + (end.z - start.z) ** 2) ** 0.5
            items.append({
                "nama_item": "Garis",
                "P": round(length / 1000, 3),
                "L": None,
                "T": None,
                "satuan": "m",
                "confidence": 1.0,
                "tipe": "line",
                "start": list(start),
                "end": list(end),
            })
        except Exception:
            continue

    return {
        "status": "ok",
        "source": "ezdxf",
        "items": items,
        "text_labels": labels,
    }
