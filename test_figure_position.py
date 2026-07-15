import sys
from pathlib import Path
import fitz
import pikepdf
from PIL import Image
import io

def inspect_pdf(pdf_path):
    """Comprehensive inspection of PDF for Figure position info"""
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {doc.page_count}")
    print()

    # === 1. Check StructTreeRoot ===
    has_struct = '/StructTreeRoot' in pdf.Root
    print(f"Has StructTreeRoot: {has_struct}")

    if has_struct:
        struct_tree = pdf.Root['/StructTreeRoot']
        print(f"StructTreeRoot keys: {list(struct_tree.keys())}")

        figures = []
        def traverse(item, depth=0):
            indent = "  " * depth
            if isinstance(item, pikepdf.Dictionary):
                struct_type = str(item.get('/S', '')) if item.get('/S') else ''
                if struct_type == '/Figure':
                    bbox = item.get('/BBox')
                    pg = item.get('/Pg')
                    k = item.get('/K')
                    print(f"\n{indent}[Figure element]")
                    print(f"{indent}  All keys: {list(item.keys())}")
                    print(f"{indent}  BBox: {bbox}")
                    print(f"{indent}  Pg (page reference): {pg}")
                    if k:
                        print(f"{indent}  K type: {type(k).__name__}")
                        if isinstance(k, pikepdf.Dictionary):
                            print(f"{indent}  K keys: {list(k.keys())}")
                            print(f"{indent}  K BBox: {k.get('/BBox')}")
                        elif isinstance(k, pikepdf.Array):
                            for i, child in enumerate(k):
                                print(f"{indent}  K[{i}] type: {type(child).__name__}")
                                if isinstance(child, pikepdf.Dictionary):
                                    print(f"{indent}  K[{i}] keys: {list(child.keys())}")
                                    print(f"{indent}  K[{i}] BBox: {child.get('/BBox')}")
                                    print(f"{indent}  K[{i}] S: {child.get('/S')}")
                                    print(f"{indent}  K[{i}] MCID: {child.get('/MCID')}")
                    figures.append({'bbox': bbox, 'pg': pg})
                if '/K' in item:
                    traverse(item['/K'], depth + 1)
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    traverse(child, depth)
            elif hasattr(item, 'get_object'):
                traverse(item.get_object(), depth)

        traverse(struct_tree)
        print(f"\nTotal Figure elements: {len(figures)}")

    # === 2. Check PyMuPDF page dict for image blocks ===
    print("\n=== PyMuPDF page.get_text('dict') image blocks ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        img_blocks = [b for b in blocks if b["type"] == 1]
        print(f"\nPage {page_num+1}: {len(img_blocks)} image blocks")
        for i, b in enumerate(img_blocks):
            print(f"  Image block {i}: bbox={b['bbox']}, width={b['width']}, height={b['height']}, ext={b.get('ext','N/A')}")

    # === 3. Check page.get_images ===
    print("\n=== page.get_images() ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        images = page.get_images(full=True)
        print(f"Page {page_num+1}: {len(images)} XObject images")
        for i, img in enumerate(images):
            print(f"  Image {i}: xref={img[0]}, width={img[1]}, height={img[2]}, cs_name={img[3]}, name={img[7]}")

    # === 4. Check for MCID-based structure ===
    print("\n=== Checking MCID structure with PyMuPDF ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        # Get text with structure info
        try:
            html = page.get_text("html")
            print(f"Page {page_num+1}: HTML text length = {len(html)}")
        except:
            pass

    doc.close()
    pdf.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        uploads = list(Path("uploads").glob("*.pdf"))
        if uploads:
            inspect_pdf(uploads[0])
        else:
            print("Usage: python test_figure_position.py <pdf_path>")
    else:
        inspect_pdf(Path(sys.argv[1]))
