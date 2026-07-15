import sys
from pathlib import Path
import fitz
import pikepdf

def inspect_figure_mcid(pdf_path):
    """Inspect how Figure elements link to page content via MCID"""
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {doc.page_count}")
    print()

    if '/StructTreeRoot' not in pdf.Root:
        print("No StructTreeRoot")
        doc.close()
        pdf.close()
        return

    struct_tree = pdf.Root['/StructTreeRoot']

    # Collect all Figure elements and their MCID references
    figure_mcid_map = []  # List of (page_num, mcid, figure_dict)

    def traverse(item, depth=0):
        if isinstance(item, pikepdf.Dictionary):
            struct_type = str(item.get('/S', '')) if item.get('/S') else ''
            if struct_type == '/Figure':
                pg_ref = item.get('/Pg')
                page_num = None
                if pg_ref:
                    # Resolve page reference to page number
                    for i, page in enumerate(pdf.pages):
                        if page.objgen == pg_ref.objgen:
                            page_num = i + 1
                            break

                # Check K for MCID
                k = item.get('/K')
                mcids = []
                if isinstance(k, pikepdf.Array):
                    for child in k:
                        if isinstance(child, pikepdf.Dictionary):
                            mcid = child.get('/MCID')
                            if mcid is not None:
                                mcids.append(int(mcid))
                        elif hasattr(child, 'get_object'):
                            obj = child.get_object()
                            if isinstance(obj, pikepdf.Dictionary):
                                mcid = obj.get('/MCID')
                                if mcid is not None:
                                    mcids.append(int(mcid))
                elif isinstance(k, pikepdf.Dictionary):
                    mcid = k.get('/MCID')
                    if mcid is not None:
                        mcids.append(int(mcid))

                print(f"\n[Figure] Page={page_num}, MCIDs={mcids}")
                print(f"  Keys: {list(item.keys())}")
                print(f"  K type: {type(k).__name__}")
                figure_mcid_map.append({'page_num': page_num, 'mcids': mcids, 'dict': item})

            if '/K' in item:
                traverse(item['/K'], depth + 1)
        elif isinstance(item, pikepdf.Array):
            for child in item:
                traverse(child, depth)
        elif hasattr(item, 'get_object'):
            traverse(item.get_object(), depth)

    traverse(struct_tree)
    print(f"\nTotal Figures with MCID: {len(figure_mcid_map)}")

    # === Try PyMuPDF approach: search for images by position ===
    print("\n=== PyMuPDF: page.get_text('dict') blocks ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        blocks = page.get_text("dict")["blocks"]
        print(f"\nPage {page_num+1}: {len(blocks)} total blocks")
        for i, b in enumerate(blocks):
            if b["type"] == 0:  # text
                print(f"  Text block {i}: bbox={b['bbox']}, lines={len(b['lines'])}")
                if b['lines']:
                    first_line = b['lines'][0]
                    if first_line['spans']:
                        print(f"    First text: '{first_line['spans'][0]['text'][:50]}...'")
            elif b["type"] == 1:  # image
                print(f"  IMAGE block {i}: bbox={b['bbox']}, width={b['width']}, height={b['height']}")

    # === Try to find image positions via page.get_image_info ===
    print("\n=== PyMuPDF: page.get_image_info() ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        try:
            img_info = page.get_image_info()
            print(f"Page {page_num+1}: {len(img_info)} images")
            for i, info in enumerate(img_info):
                print(f"  Image {i}: bbox={info.get('bbox')}, transform={info.get('transform')}")
        except Exception as e:
            print(f"Page {page_num+1}: Error - {e}")

    # === Check if page has marked content with BBox ===
    print("\n=== PyMuPDF: Searching for marked content BBoxes ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        # Get raw dict with more details
        dict_data = page.get_text("dict")
        print(f"Page {page_num+1} dict keys: {dict_data.keys()}")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        uploads = list(Path("uploads").glob("*.pdf"))
        if uploads:
            inspect_figure_mcid(uploads[0])
        else:
            print("Usage: python test_figure_mcid.py <pdf_path>")
    else:
        inspect_figure_mcid(Path(sys.argv[1]))
