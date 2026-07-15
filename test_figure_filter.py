import fitz
import pikepdf
from pathlib import Path

def analyze(pdf_path):
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    # Collect Figure elements per page
    figures = {}  # page_num -> list of figure dicts
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
                        if page_num not in figures:
                            figures[page_num] = []
                        figures[page_num].append({'page_num': page_num})
                if '/K' in item:
                    traverse(item['/K'])
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    traverse(child)
            elif hasattr(item, 'get_object'):
                traverse(item.get_object())
        traverse(pdf.Root['/StructTreeRoot'])

    print("Page | Figures | Drawings(>80) | Match?")
    print("-" * 50)

    for page_num in range(doc.page_count):
        page = doc[page_num]
        fig_count = len(figures.get(page_num + 1, []))
        drawings = page.get_drawings()

        # Filter drawings by area
        significant = []
        for d in drawings:
            rect = d.get('rect')
            area = rect.width * rect.height
            if area > 80:
                significant.append({'rect': rect, 'area': area})

        # Sort by y coordinate (top to bottom)
        significant.sort(key=lambda x: x['rect'].y0)

        match = "YES" if len(significant) == fig_count else "NO"
        print(f"{page_num+1:4} | {fig_count:7} | {len(significant):13} | {match}")
        for i, s in enumerate(significant):
            print(f"  Sig[{i}]: rect={s['rect']}, area={s['area']:.0f}")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    analyze(Path("test_iphone16.pdf"))
