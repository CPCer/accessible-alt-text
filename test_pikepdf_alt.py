import sys
from pathlib import Path
import pikepdf


def test_write_chinese_alt():
    print("=" * 60)
    print("测试1: pikepdf写入中文Alt文本")
    print("=" * 60)
    
    if len(sys.argv) < 2:
        print("用法: python test_pikepdf_alt.py <测试PDF文件>")
        print("请先用Acrobat为PDF生成结构树，再用此脚本测试")
        sys.exit(1)
    
    pdf_path = Path(sys.argv[1])
    if not pdf_path.exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_pikepdf_alt.pdf"
    
    with pikepdf.open(pdf_path) as pdf:
        test_alt_text = "这是一张测试图片的中文替代文本"
        
        for page_num, page in enumerate(pdf.pages):
            if '/Resources' in page and '/XObject' in page['/Resources']:
                xobjects = page['/Resources']['/XObject']
                
                for name in xobjects.keys():
                    xobj = xobjects[name]
                    
                    if '/Subtype' in xobj and xobj['/Subtype'] == '/Image':
                        xobj['/Alt'] = test_alt_text
                        print(f"✓ 页面{page_num+1}: 成功写入中文Alt文本")
                        break
        
        pdf.save(output_path)
    
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
    
    with pikepdf.open(pdf_path) as pdf:
        if '/StructTreeRoot' in pdf.Root:
            print("✓ 原PDF包含结构树")
        else:
            print("✗ 原PDF不包含结构树，请先用Acrobat生成")
    
    output_path = pdf_path.parent / f"{pdf_path.stem}_pikepdf_struct.pdf"
    
    with pikepdf.open(pdf_path) as pdf:
        pdf.save(output_path)
    
    with pikepdf.open(output_path) as pdf2:
        if '/StructTreeRoot' in pdf2.Root:
            print("✓ 写入后PDF仍保留结构树")
        else:
            print("✗ 写入后结构树丢失！")
    
    print(f"\n输出文件: {output_path}")


if __name__ == "__main__":
    test_write_chinese_alt()
    test_structure_tree_preservation()