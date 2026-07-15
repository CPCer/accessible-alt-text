import sys
from pathlib import Path
import fitz
import pikepdf

def inspect_figure_elements(pdf_path):
    """Inspect Figure elements in the structure tree for BBox info"""
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {doc.page_count}")

    if '/StructTreeRoot' not in pdf.Root:
        print("No StructTreeRoot found")
        return

    struct_tree = pdf.Root['/StructTreeRoot']
    figures = []

    def traverse(item, depth=0):
        indent = "  " * depth
        if isinstance(item, pikepdf.Dictionary):
            struct_type = str(item.get('/S', '')) if item.get('/S') else ''
            if struct_type == '/Figure':
                fig_info = {
                    'type': struct_type,
                    'keys': list(item.keys()),
                    'has_bbox': '/BBox' in item,
                    'bbox': str(item.get('/BBox', 'N/A')),
                    'has_k': '/K' in item,
                    'k_type': type(item.get('/K')).__name__ if '/K' in item else 'N/A',
                    'pg': str(item.get('/Pg', 'N/A')),
                }
                figures.append(fig_info)
                print(f"\n{indent}[Figure] Keys: {fig_info['keys']}")
                print(f"{indent}  BBox: {fig_info['bbox']}")
                print(f"{indent}  Pg (page ref): {fig_info['pg']}")
                print(f"{indent}  K: {fig_info['k_type']}")
                if '/K' in item:
                    k = item['/K']
                    if isinstance(k, pikepdf.Array):
                        for i, child in enumerate(k):
                            print(f"{indent}    K[{i}] type: {type(child).__name__}")
                            if isinstance(child, pikepdf.Dictionary):
                                print(f"{indent}    K[{i}] keys: {list(child.keys())}")
                                if '/BBox' in child:
                                    print(f"{indent}    K[{i}] BBox: {child['/BBox']}")
                                if '/S' in child:
                                    print(f"{indent}    K[{i}] S: {child['/S']}")
                    elif isinstance(k, pikepdf.Dictionary):
                        print(f"{indent}    K keys: {list(k.keys())}")
                        if '/BBox' in k:
                            print(f"{indent}    K BBox: {k['/BBox']}")
            if '/K' in item:
                traverse(item['/K'], depth + 1)
        elif isinstance(item, pikepdf.Array):
            for child in item:
                traverse(child, depth)
        elif hasattr(item, 'get_object'):
            traverse(item.get_object(), depth)

    traverse(struct_tree)
    print(f"\nTotal Figure elements found: {len(figures)}")

    # Also check MCIDs
    print("\n--- Checking page content for MCID-based Figure detection ---")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        images = page.get_images(full=True)
        print(f"\nPage {page_num+1}: {len(images)} XObject images")
        for i, img in enumerate(images):
            print(f"  Image {i}: xref={img[0]}, width={img[1]}, height={img[2]}")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Try to find a test PDF
        uploads = list(Path("uploads").glob("*.pdf"))
        if uploads:
            inspect_figure_elements(uploads[0])
        else:
            print("Usage: python test_figure_bbox.py <pdf_path>")
    else:
        inspect_figure_elements(Path(sys.argv[1]))
