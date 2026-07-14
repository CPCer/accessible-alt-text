import sys
from pathlib import Path
try:
    import pymupdf as fitz
except ImportError:
    import fitz


def test_write_chinese_alt():
    print("=" * 60)
    print("测试1: PyMuPDF写入中文Alt文本")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("用法: python test_pymupdf_alt.py <测试PDF文件>")
        print("请先用Acrobat为PDF生成结构树，再用此脚本测试")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_pymupdf_alt.pdf"
    
    doc = fitz.open(pdf_path)
    
    test_alt_text = "这是一张测试图片的中文替代文本"
    
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        images = page.get_images(full=True)
        
        for img_index, img in enumerate(images):
            xref = img[0]
            img_dict = doc.extract_image(xref)
            
            if img_dict.get("width", 0) > 30 and img_dict.get("height", 0) > 30:
                img_obj = doc.xref_object(xref, compressed=False)
                if "/Subtype /Image" in img_obj:
                    doc.update_stream(xref, img_obj.replace(
                        "/Subtype /Image",
                        f"/Subtype /Image\n/Alt ({test_alt_text})"
                    ))
                    print(f"✓ 页面{page_num+1}: 成功写入中文Alt文本")
    
    doc.save(output_path)
    doc.close()
    
    print(f"\n✓ 测试完成，输出文件: {output_path}")
    print("请用Acrobat打开验证：")
    print("  1. 检查结构树是否完整保留")
    print("  2. 检查图片的替代文本是否正确显示中文")


def test_structure_tree_preservation():
    print("\n" + "=" * 60)
    print("测试2: 验证结构树保留")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    
    doc = fitz.open(pdf_path)
    
    if doc.has_struct_tree:
        print("✓ 原PDF包含结构树")
    else:
        print("✗ 原PDF不包含结构树，请先用Acrobat生成")
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_pymupdf_struct.pdf"
    
    doc.save(output_path)
    doc.close()
    
    doc2 = fitz.open(output_path)
    if doc2.has_struct_tree:
        print("✓ 写入后PDF仍保留结构树")
    else:
        print("✗ 写入后结构树丢失！")
    doc2.close()
    
    print(f"\n输出文件: {output_path}")


if __name__ == "__main__":
    test_write_chinese_alt()
    test_structure_tree_preservation()