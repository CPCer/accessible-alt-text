import fitz
import pikepdf
from pathlib import Path
from PIL import Image
import io

def is_inside(inner, outer):
    """Check if inner rect is completely inside outer rect (with small margin)"""
    margin = 1.0
    return (inner.x0 >= outer.x0 - margin and inner.y0 >= outer.y0 - margin and
            inner.x1 <= outer.x1 + margin and inner.y1 <= outer.y1 + margin and
            (inner.x1 - inner.x0) < (outer.x1 - outer.x0) - margin)

def get_significant_drawings(page):
    """Get significant drawings, filtering out small ones and nested ones"""
    drawings = page.get_drawings()

    # Filter by area
    candidates = []
    for d in drawings:
        rect = d.get('rect')
        area = rect.width * rect.height
        if area > 80:
            candidates.append(rect)

    # Remove drawings that are completely inside another drawing
    significant = []
    for rect in candidates:
        is_nested = False
        for other in candidates:
            if rect is not other and is_inside(rect, other):
                is_nested = True
                break
        if not is_nested:
            significant.append(rect)

    # Sort by y coordinate (top to bottom)
    significant.sort(key=lambda r: r.y0)
    return significant

def test_crop(pdf_path):
    doc = fitz.open(pdf_path)

    # Collect figures per page
    pdf = pikepdf.open(pdf_path)
    figures = {}
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
                        figures[page_num] = figures.get(page_num, 0) + 1
                if '/K' in item:
                    traverse(item['/K'])
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    traverse(child)
            elif hasattr(item, 'get_object'):
                traverse(item.get_object())
        traverse(pdf.Root['/StructTreeRoot'])
    pdf.close()

    print("Page | Figures | SigDrawings | Match?")
    print("-" * 45)

    for page_num in range(doc.page_count):
        page = doc[page_num]
        fig_count = figures.get(page_num + 1, 0)
        sig = get_significant_drawings(page)
        match = "YES" if len(sig) == fig_count else "NO"
        print(f"{page_num+1:4} | {fig_count:7} | {len(sig):11} | {match}")

        if fig_count > 0 and len(sig) > 0:
            # Render page and crop each drawing
            pix = page.get_pixmap(dpi=200)
            img = Image.open(io.BytesIO(pix.tobytes("png")))

            scale_x = pix.width / page.rect.width
            scale_y = pix.height / page.rect.height

            for i, rect in enumerate(sig):
                # Convert PDF rect to pixel coordinates
                x0 = int(rect.x0 * scale_x)
                y0 = int(rect.y0 * scale_y)
                x1 = int(rect.x1 * scale_x)
                y1 = int(rect.y1 * scale_y)

                # Crop
                cropped = img.crop((x0, y0, x1, y1))
                out_path = f"figure_preview_p{page_num+1}_f{i}.png"
                cropped.save(out_path)
                print(f"  Saved: {out_path} ({cropped.width}x{cropped.height})")

    doc.close()

if __name__ == "__main__":
    test_crop(Path("test_iphone16.pdf"))
