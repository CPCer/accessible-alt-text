import sys
from pathlib import Path
from PyPDF2 import PdfReader, PdfWriter


def test_write_chinese_alt():
    print("=" * 60)
    print("测试1: pypdf写入中文Alt文本")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("用法: python test_pypdf_alt.py <测试PDF文件>")
        print("请先用Acrobat为PDF生成结构树，再用此脚本测试")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    reader = PdfReader(pdf_path)
    writer = PdfWriter()
    
    for page in reader.pages:
        writer.add_page(page)
    
    test_alt_text = "这是一张测试图片的中文替代文本"
    
    for i, page in enumerate(writer.pages):
        if "/Resources" in page and "/XObject" in page["/Resources"]:
            xobjects = page["/Resources"]["/XObject"]
            for name in xobjects.keys():
                xobj = xobjects[name]
                if "/Subtype" in xobj and xobj["/Subtype"] == "/Image":
                    xobj[("/Alt", "")] = test_alt_text
                    print(f"✓ 页面{i+1}: 成功写入中文Alt文本")
                    break
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_test_chinese.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)
    
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
    reader = PdfReader(pdf_path)
    
    has_struct_tree = False
    root = reader.trailer.get("/Root")
    if root is not None:
        root_dict = root.get_object() if hasattr(root, 'get_object') else dict(root)
        if "/StructTreeRoot" in root_dict:
            has_struct_tree = True
            print("✓ 原PDF包含结构树")
        else:
            print("✗ 原PDF不包含结构树，请先用Acrobat生成")
    else:
        print("✗ 无法读取PDF根对象")
    
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_test_struct.pdf"
    with open(output_path, "wb") as f:
        writer.write(f)
    
    reader2 = PdfReader(output_path)
    root2 = reader2.trailer.get("/Root")
    struct_tree_preserved = False
    if root2 is not None:
        root_dict2 = root2.get_object() if hasattr(root2, 'get_object') else dict(root2)
        if "/StructTreeRoot" in root_dict2:
            struct_tree_preserved = True
            print("✓ 写入后PDF仍保留结构树")
        else:
            print("✗ 写入后结构树丢失！")
    else:
        print("✗ 无法读取输出PDF根对象")
    
    print(f"\n输出文件: {output_path}")


if __name__ == "__main__":
    test_write_chinese_alt()
    test_structure_tree_preservation()