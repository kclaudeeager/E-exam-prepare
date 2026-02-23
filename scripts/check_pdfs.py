"""Check which PDFs in web-scrap have extractable text."""
import pdfplumber
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent

test_files = [
    BASE / "web-scrap/rwanda_papers_organized1/Primary_School_P6/General/P6_2046_mathematics.pdf",
    BASE / "web-scrap/rwanda_papers/Curriculum/Biology/S4_Biology_2012.pdf",
    BASE / "web-scrap/rwanda_papers/Curriculum/Math/P6 Mathematics_Study Book_2017_LR.pdf",
    BASE / "web-scrap/rwanda_papers/S3/General",
    BASE / "web-scrap/rwanda_papers/S6/General",
]

for path in test_files:
    if path.is_dir():
        pdfs = list(path.glob("*.pdf"))
        print(f"\nDIR {path.name}: {len(pdfs)} PDFs")
        path = pdfs[0] if pdfs else None

    if not path or not path.exists():
        print(f"  NOT FOUND: {path}")
        continue

    with pdfplumber.open(str(path)) as pdf:
        total_pages = len(pdf.pages)
        chars = []
        for pg in pdf.pages[:5]:
            t = pg.extract_text() or ""
            chars.append(len(t.strip()))

        avg = sum(chars) / len(chars) if chars else 0
        status = "✅ HAS TEXT" if avg > 100 else "❌ SCANNED/IMAGE"
        print(f"{status} | {path.name} | pages={total_pages}, avg_chars/pg={avg:.0f}")
        if avg > 100:
            sample = (pdf.pages[0].extract_text() or "").strip()[:150]
            print(f"  Sample: {repr(sample)}")
