import fitz
import pikepdf
from pathlib import Path

def analyze(pdf_path):
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    # Count figures per page
    figure_counts = {}
    if '/StructTreeRoot' in pdf.Root:
        def traverse(item):
            if isinstance(item, pikepdf.Dictionary):
                struct_type = str(item.get('/S', '')) if item.get('/S') else ''
                if struct_type == '/Figure':
                    pg_ref = item.get('/Pg')
                    page_num = None
                    if pg_ref:
                        for i, page in enumerate(pdf.pages):
                            if page.objgen == pg_ref.objgen:
                                page_num = i + 1
                                break
                    if page_num:
                        figure_counts[page_num] = figure_counts.get(page_num, 0) + 1
                if '/K' in item:
                    traverse(item['/K'])
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    traverse(child)
            elif hasattr(item, 'get_object'):
                traverse(item.get_object())
        traverse(pdf.Root['/StructTreeRoot'])

    # Count drawings per page
    print("Page | Figures | Drawings | Drawings detail")
    print("-" * 60)
    for page_num in range(doc.page_count):
        page = doc[page_num]
        drawings = page.get_drawings()
        fig_count = figure_counts.get(page_num + 1, 0)
        print(f"{page_num+1:4} | {fig_count:7} | {len(drawings):8} | ", end="")
        for i, d in enumerate(drawings):
            rect = d.get('rect')
            print(f"[{i}]{rect} ", end="")
        print()

    # Also check: are drawings within the page bounds of figures?
    # Let's render page 2 and see
    print("\n=== Rendering Page 2 to see what's there ===")
    page = doc[1]  # Page 2
    pix = page.get_pixmap(dpi=150)
    pix.save("page2_preview.png")
    print(f"Page 2 rendered: {pix.width}x{pix.height}")

    # Check if drawings rect makes sense
    drawings = page.get_drawings()
    for i, d in enumerate(drawings):
        rect = d.get('rect')
        print(f"Drawing {i}: rect={rect}, area={rect.width*rect.height}")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    analyze(Path("test_iphone16.pdf"))
