"""Generate synthetic PDF test files for the golden dataset."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.app.config import settings


def generate_pdf_text(text: str, output_path: Path) -> None:
    try:
        from fpdf import FPDF
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", "", 12)
        for line in text.split("\n"):
            pdf.cell(0, 8, line.strip(), new_x="LMARGIN", new_y="NEXT")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        pdf.output(str(output_path))
        print(f"  Generated: {output_path}")
    except ImportError:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text)
        print(f"  Generated (text fallback): {output_path}")


def main():
    base = settings.golden_dataset_dir / "simple"
    base.mkdir(parents=True, exist_ok=True)

    cases = {
        "simple-synthetic-area-violation": "Building Plan\narea: 250 m2\nheight: 3.0 m\nsetback: 5.0 m",
        "simple-synthetic-height-violation": "Building Plan\narea: 100 m2\nheight: 2.0 m\nsetback: 5.0 m",
        "simple-synthetic-setback-violation": "Building Plan\narea: 100 m2\nheight: 3.0 m\nsetback: 1.5 m",
        "simple-synthetic-clean": "Building Plan\narea: 120 m2\nheight: 3.0 m\nsetback: 5.0 m",
    }

    print("Generating synthetic PDFs...")
    for entry_id, text in cases.items():
        output_path = base / f"{entry_id}.pdf"
        generate_pdf_text(text, output_path)

    print("Done.")


if __name__ == "__main__":
    main()
