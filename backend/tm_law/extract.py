"""Parse document bytes in a disposable process without using uploaded file paths."""

import io
import sys
import zipfile
from xml.etree import ElementTree

from pypdf import PdfReader

MAX_UPLOAD = 8 * 1024 * 1024
MAX_TEXT = 180_000
WORD_NS = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def extract(data: bytes, suffix: str) -> str:
    if suffix == ".txt":
        text = data.decode("utf-8-sig")
        if "\0" in text:
            raise ValueError("Neplatný textový súbor.")
    elif suffix == ".pdf" and data.startswith(b"%PDF-"):
        reader = PdfReader(io.BytesIO(data), strict=True)
        if reader.is_encrypted or len(reader.pages) > 150:
            raise ValueError("PDF musí byť odomknuté a mať najviac 150 strán.")
        pages = []
        length = 0
        for page in reader.pages:
            body = page.extract_text() or ""
            pages.append(body)
            length += len(body)
            if length > MAX_TEXT:
                raise ValueError("Dokument obsahuje priveľa textu.")
        text = "\n\n".join(pages)
        if not text.strip():
            raise ValueError("PDF nemá použiteľnú textovú vrstvu. Vyžaduje OCR.")
    elif suffix == ".docx" and data.startswith(b"PK"):
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > 400 or sum(entry.file_size for entry in entries) > 20 * 1024 * 1024:
                raise ValueError("Dokument po rozbalení prekračuje limit.")
            xml = archive.read("word/document.xml")
        # Decode before checking so UTF-16 cannot hide declarations from the guard.
        decoded = xml.decode("utf-8-sig")
        if "<!DOCTYPE" in decoded or "<!ENTITY" in decoded:
            raise ValueError("Nepodporovaná deklarácia XML.")
        root = ElementTree.fromstring(decoded)
        if root.tag != WORD_NS + "document":
            raise ValueError("Nepodporovaný obsah DOCX.")
        text = "\n".join(
            "".join(node.text or "" for node in paragraph.iter(WORD_NS + "t"))
            for paragraph in root.iter(WORD_NS + "p")
        )
    else:
        raise ValueError("Obsah súboru nezodpovedá podporovanému typu TXT, PDF alebo DOCX.")
    text = text.strip()
    if not text or len(text) > MAX_TEXT:
        raise ValueError("Dokument je prázdny alebo obsahuje priveľa textu.")
    return text


if __name__ == "__main__":
    try:
        sys.stdout.buffer.write(
            extract(sys.stdin.buffer.read(MAX_UPLOAD + 1), sys.argv[1]).encode()
        )
    except ValueError as error:
        # Decoder and parser exceptions can contain partial input. Only emit our messages.
        message = str(error) if type(error) is ValueError else "Súbor sa nedá spracovať."
        sys.stdout.buffer.write(message.encode())
        sys.exit(2)
    except Exception:
        sys.stdout.buffer.write("Súbor je poškodený alebo nepodporovaný.".encode())
        sys.exit(2)
