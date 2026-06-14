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

        full_prompt = f"{system}\n\nUser: {user_message}"
        response_text = self.router.call("chat", full_prompt)
        action = self._extract_action(response_text)

        self.conversation_history.append({"user": user_message, "assistant": response_text})

        return {
            "response_text": response_text,
            "action": action,
            "flagged_items": [],
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
