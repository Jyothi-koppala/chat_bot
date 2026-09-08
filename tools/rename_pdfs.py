"""Rename local PDFs using an organization/title detected from the first pages.
Run from project root: py -3.11 tools\rename_pdfs.py
Review the proposed names before accepting them.
"""
from pathlib import Path
import re
from pypdf import PdfReader

PDF_DIR = Path(__file__).resolve().parents[1] / "pdf"
PATTERNS = [
    (r"ICICI\s+Lombard", "ICICI_Lombard"),
    (r"HDFC\s+ERGO", "HDFC_ERGO"),
    (r"SBI\s+General", "SBI_General"),
    (r"Star Health", "Star_Health"),
    (r"Care Health", "Care_Health"),
    (r"Niva Bupa", "Niva_Bupa"),
    (r"Bajaj Allianz", "Bajaj_Allianz"),
    (r"Aditya Birla", "Aditya_Birla"),
]

def clean(s):
    s = re.sub(r"[^A-Za-z0-9]+", "_", s).strip("_")
    return re.sub(r"_+", "_", s)

for path in sorted(PDF_DIR.glob("*.pdf")):
    if any(c.isupper() for c in path.stem) and "_" in path.stem:
        continue
    try:
        text = "\n".join((p.extract_text() or "") for p in PdfReader(path).pages[:2])
    except Exception as exc:
        print(f"SKIP {path.name}: {exc}")
        continue
    prefix = next((name for pattern, name in PATTERNS if re.search(pattern, text, re.I)), None)
    if not prefix:
        prefix = "Policy_Document"
    title_match = re.search(r"(?i)([A-Za-z ]{3,60}(?:Health|Insurance|Policy|Prospectus|Benefits|Plan))", text)
    title = clean(title_match.group(1)) if title_match else clean(path.stem)
    base = f"{prefix}_{title}" if prefix.lower() not in title.lower() else title
    base = clean(base)[:100]
    target = path.with_name(base + ".pdf")
    if target == path:
        print(f"KEEP {path.name}")
        continue
    n = 1
    candidate = target
    while candidate.exists():
        candidate = path.with_name(f"{base}_{n}.pdf")
        n += 1
    print(f"RENAME: {path.name} -> {candidate.name}")
