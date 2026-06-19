"""
modules/chat_handler.py

QS Assistant — chat AI dengan konteks BOQ aktif.
Setiap pesan membawa state BOQ terkini.

Chat actions diekstrak dari JSON dalam markdown code fence ```json ... ```
"""

import json
import re


class ChatHandler:
    """
    QS Assistant — chat AI dengan konteks BOQ aktif.
    """

    SYSTEM_PROMPT = """
Kamu adalah QS Assistant, asisten teknis profesional untuk Quantity Surveyor Indonesia.
Kamu sedang membantu mengerjakan BOQ (Bill of Quantity) proyek konstruksi.

KONTEKS AKTIF:
- File gambar: {nama_file}
- Template Excel: {nama_template}
- Mapping kolom: {json_mapping}
- Data BOQ saat ini: {json_boq}

KEMAMPUAN:
1. Jawab pertanyaan tentang data BOQ di atas dengan presisi
2. Jika user minta update dimensi, return JSON action:
   {{"action": "update_cell", "item": "nama item", "field": "P|L|T", "value": angka}}
3. Jika user tanya teknis, jawab berdasarkan SNI/AHSP Indonesia
4. Jika ada anomali di BOQ (satuan salah, volume tidak masuk akal), flagging proaktif
5. Selalu sebut nomor baris Excel jika merujuk data spesifik

BATASAN:
- Jangan mengarang dimensi yang tidak disebutkan user atau tidak ada di gambar
- Jika tidak yakin, tanyakan konfirmasi
- Satuan selalu eksplisit: m, m², m³, kg, ls, unit
- Jawab dalam bahasa Indonesia kecuali user pakai bahasa lain

FORMAT RESPONSE untuk update cell:
Jika ada update: awali response dengan blok JSON, lalu penjelasan teks.
Contoh:
```json
{{"action": "update_cell", "item": "Galian Tanah", "field": "T", "value": 1.20}}
```
Update berhasil. Galian Tanah baris 4: P=12.5 × L=0.8 × T=1.20 = 12.00 m³
"""

    def __init__(self, llm_router):
        """
        Args:
            llm_router: Instance LLMRouter untuk memanggil LLM
        """
        self.router = llm_router
        self.conversation_history: list[dict] = []

    MAX_HISTORY = 20

    def _flag_items(self, boq_state: list[dict]) -> list[dict]:
        flagged = []
        for i, item in enumerate(boq_state):
            flags = []
            conf = item.get("confidence", 1.0)
            if conf < 0.7:
                flags.append(f"Confidence rendah ({conf})")

            nama = (item.get("nama_item") or "").lower()
            tipe_3d = any(kw in nama for kw in ["galian", "beton", "urugan", "pondasi", "sloof", "pasangan"])
            if tipe_3d:
                if item.get("P") is None:
                    flags.append("Panjang (P) tidak terbaca")
                if item.get("L") is None:
                    flags.append("Lebar (L) tidak terbaca")
                if item.get("T") is None:
                    flags.append("Tinggi/Kedalaman (T) tidak terbaca")

            if item.get("P") is not None and item["P"] > 100:
                flags.append(f"Panjang {item['P']}m tidak realistis")
            if item.get("T") is not None and item["T"] > 10:
                flags.append(f"Tinggi {item['T']}m tidak realistis")

            if flags:
                flagged.append({
                    "index": i,
                    "nama_item": item.get("nama_item", ""),
                    "alasan": "; ".join(flags),
                })
        return flagged

    def chat(
        self,
        user_message: str,
        boq_state: list[dict],
        template_mapping: dict,
        file_names: dict,
    ) -> dict:
        """
        Proses pesan user dan return response + action jika ada.

        Args:
            user_message: Pesan dari user
            boq_state: Data BOQ terkini (list of items)
            template_mapping: Mapping kolom dari template_detector
            file_names: {gambar, template}

        Returns:
            dict dengan response_text, action, flagged_items
        """
        system = self.SYSTEM_PROMPT.format(
            nama_file=file_names.get("gambar", "tidak ada"),
            nama_template=file_names.get("template", "tidak ada"),
            json_mapping=json.dumps(template_mapping, ensure_ascii=False, indent=2),
            json_boq=json.dumps(boq_state[:20], ensure_ascii=False, indent=2),
        )

        history_text = ""
        if self.conversation_history:
            parts = []
            for h in self.conversation_history[-5:]:
                parts.append(f"User: {h['user']}\nAssistant: {h['assistant']}")
            history_text = "\n\nRIWAYAT PERCAKAPAN:\n" + "\n---\n".join(parts)

        full_prompt = f"{system}{history_text}\n\nUser: {user_message}"
        response_text = self.router.call("chat", full_prompt)
        action = self._extract_action(response_text)

        self.conversation_history.append({"user": user_message, "assistant": response_text})
        if len(self.conversation_history) > self.MAX_HISTORY:
            self.conversation_history = self.conversation_history[-self.MAX_HISTORY:]

        flagged_items = self._flag_items(boq_state)

        return {
            "response_text": response_text,
            "action": action,
            "flagged_items": flagged_items,
        }

    def _extract_action(self, response_text: str) -> dict:
        """Extract JSON action dari response teks."""
        pattern = r'```json\s*(\{.*?\})\s*```'
        match = re.search(pattern, response_text, re.DOTALL)
        if match:
            raw = match.group(1)
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                pass
            try:
                depth = 0
                start = raw.index("{")
                for i, ch in enumerate(raw[start:], start):
                    if ch == "{":
                        depth += 1
                    elif ch == "}":
                        depth -= 1
                        if depth == 0:
                            return json.loads(raw[start : i + 1])
            except (ValueError, json.JSONDecodeError):
                pass
        return None
