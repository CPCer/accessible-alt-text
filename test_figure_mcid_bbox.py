import sys
from pathlib import Path
import fitz
import pikepdf

def inspect_figure_mcid_bbox(pdf_path):
    doc = fitz.open(pdf_path)
    pdf = pikepdf.open(pdf_path)

    print(f"PDF: {pdf_path.name}")
    print(f"Pages: {doc.page_count}")

    # === 1. Collect all Figure MCIDs per page ===
    figure_mcids = {}  # page_num -> list of mcids

    if '/StructTreeRoot' in pdf.Root:
        struct_tree = pdf.Root['/StructTreeRoot']

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

                    k = item.get('/K')
                    mcids = []
                    if isinstance(k, int):
                        mcids.append(k)
                    elif isinstance(k, pikepdf.Array):
                        for child in k:
                            if isinstance(child, int):
                                mcids.append(int(child))
                            elif isinstance(child, pikepdf.Dictionary):
                                mcid = child.get('/MCID')
                                if mcid is not None:
                                    mcids.append(int(mcid))
                    elif isinstance(k, pikepdf.Dictionary):
                        mcid = k.get('/MCID')
                        if mcid is not None:
                            mcids.append(int(mcid))

                    if page_num:
                        if page_num not in figure_mcids:
                            figure_mcids[page_num] = []
                        figure_mcids[page_num].extend(mcids)
                        print(f"Figure on Page {page_num}: MCIDs={mcids}")

                if '/K' in item:
                    traverse(item['/K'])
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    traverse(child)
            elif hasattr(item, 'get_object'):
                traverse(item.get_object())

        traverse(struct_tree)

    print(f"\nFigure MCIDs per page: {figure_mcids}")

    # === 2. Check PyMuPDF for MCID in text spans ===
    print(f"\n=== PyMuPDF: Searching for MCID in text spans ===")
    for page_num in range(doc.page_count):
        page = doc[page_num]
        raw = page.get_text("rawdict")
        print(f"\nPage {page_num+1}:")
        found_mcids = set()
        for block in raw['blocks']:
            if block['type'] == 0:  # text
                for line in block['lines']:
                    for span in line['spans']:
                        mcid = span.get('mcid')
                        if mcid is not None:
                            found_mcids.add(mcid)
                            if page_num + 1 in figure_mcids and mcid in figure_mcids[page_num + 1]:
                                print(f"  FOUND Figure MCID {mcid}: bbox={block['bbox']}, text='{span['text'][:50]}...'")
        print(f"  All MCIDs found: {sorted(found_mcids)}")

    # === 3. Try to get bbox from marked content using content stream parsing ===
    print(f"\n=== Checking page content streams for marked content BBox ===")
    for page_num in range(min(3, doc.page_count)):
        page = doc[page_num]
        print(f"\nPage {page_num+1} content stream analysis:")
        # Read raw content
        content = page.read_contents()
        if content:
            text = content.decode('latin-1', errors='replace')
            # Search for BMC/EMC or BDC/EMC pairs
            import re
            mcid_pattern = r'/Figure\s*<<\s*/MCID\s+(\d+)\s*>>\s*BDC'
            matches = re.findall(mcid_pattern, text)
            print(f"  Found Figure BDC with MCID: {matches}")

            # Also look for any BBox in content
            bbox_pattern = r'/BBox\s*\[\s*([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s+([\d.\-]+)\s*\]'
            bbox_matches = re.findall(bbox_pattern, text)
            if bbox_matches:
                print(f"  Found BBox in content: {bbox_matches[:3]}")

    doc.close()
    pdf.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        pdfs = list(Path(".").glob("test_*.pdf"))
        if pdfs:
            inspect_figure_mcid_bbox(pdfs[0])
        else:
            print("Usage: python test_figure_mcid_bbox.py <pdf_path>")
    else:
        inspect_figure_mcid_bbox(Path(sys.argv[1]))
