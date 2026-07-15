import sys
from pathlib import Path
import fitz
import pikepdf

def inspect_advanced(pdf_path):
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {doc.page_count}")

    # === 1. Check ParentTree ===
    if '/StructTreeRoot' in pdf.Root:
        struct_tree = pdf.Root['/StructTreeRoot']
        print(f"\n=== ParentTree ===")
        if '/ParentTree' in struct_tree:
            pt = struct_tree['/ParentTree']
            print(f"ParentTree type: {type(pt).__name__}")
            print(f"ParentTree keys: {list(pt.keys())}")
            if '/Nums' in pt:
                nums = pt['/Nums']
                print(f"Nums length: {len(nums)}")
                # Show first few entries
                for i in range(0, min(6, len(nums)), 2):
                    key = nums[i]
                    val = nums[i+1]
                    print(f"  [{key}] type={type(val).__name__}")
                    if isinstance(val, pikepdf.Array):
                        for j, v in enumerate(val):
                            print(f"    [{j}] type={type(v).__name__}")
                            if hasattr(v, 'get_object'):
                                obj = v.get_object()
                                if isinstance(obj, pikepdf.Dictionary):
                                    print(f"      keys={list(obj.keys())}")
                                    print(f"      S={obj.get('/S')}")
                                    print(f"      BBox={obj.get('/BBox')}")

    # === 2. Check PyMuPDF page.get_drawings() for vector graphics ===
    print(f"\n=== PyMuPDF page.get_drawings() ===")
    for page_num in range(min(2, doc.page_count)):
        page = doc[page_num]
        drawings = page.get_drawings()
        print(f"Page {page_num+1}: {len(drawings)} drawings")
        for i, d in enumerate(drawings[:3]):
            print(f"  Drawing {i}: rect={d.get('rect')}, items={len(d.get('items', []))}")

    # === 3. Check PyMuPDF page.get_cdrawings() ===
    print(f"\n=== PyMuPDF page.get_cdrawings() ===")
    for page_num in range(min(2, doc.page_count)):
        page = doc[page_num]
        try:
            cdrawings = page.get_cdrawings()
            print(f"Page {page_num+1}: {len(cdrawings)} cdrawings")
        except Exception as e:
            print(f"Page {page_num+1}: Error - {e}")

    # === 4. Check rawdict for any image-like content ===
    print(f"\n=== PyMuPDF page.get_text('rawdict') ===")
    for page_num in range(min(2, doc.page_count)):
        page = doc[page_num]
        raw = page.get_text("rawdict")
        print(f"Page {page_num+1}: {len(raw['blocks'])} blocks")
        for i, b in enumerate(raw['blocks']):
            print(f"  Block {i}: type={b['type']}, bbox={b['bbox']}")
            if b['type'] == 1:
                print(f"    IMAGE: width={b.get('width')}, height={b.get('height')}, ext={b.get('ext')}")

    # === 5. Check for paths/vector content that might be figures ===
    print(f"\n=== PyMuPDF: Search for non-text visual content ===")
    for page_num in range(min(2, doc.page_count)):
        page = doc[page_num]
        # Get all blocks including images
        blocks = page.get_text("blocks")
        print(f"Page {page_num+1}: {len(blocks)} text blocks")
        for i, b in enumerate(blocks[:5]):
            print(f"  Block {i}: bbox={b[:4]}, type={b[6] if len(b) > 6 else 'N/A'}, text='{b[4][:60]}...'")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        uploads = list(Path(".").glob("test_*.pdf"))
        if uploads:
            inspect_advanced(uploads[0])
        else:
            print("Usage: python test_figure_advanced.py <pdf_path>")
    else:
        inspect_advanced(Path(sys.argv[1]))
