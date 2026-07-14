import sys
from pathlib import Path
import pikepdf


def inspect_pdf_resources(pdf_path):
    print("=" * 60)
    print("PDF资源检查 (pikepdf)")
    print("=" * 60)
    
    with pikepdf.open(pdf_path) as pdf:
        print(f"\n基本信息:")
        print(f"  页数: {len(pdf.pages)}")
        
        print(f"\n页面资源分析:")
        for page_num, page in enumerate(pdf.pages):
            print(f"\n  --- 页面 {page_num + 1} ---")
            
            if '/Resources' in page:
                resources = page['/Resources']
                print(f"  Resources键: {list(resources.keys())}")
                
                if '/XObject' in resources:
                    xobjects = resources['/XObject']
                    print(f"  XObject数量: {len(xobjects)}")
                    
                    for name, xobj in xobjects.items():
                        if '/Subtype' in xobj:
                            print(f"    {name}: {xobj['/Subtype']}")
                            if xobj['/Subtype'] == '/Image':
                                print(f"      - 尺寸: {xobj.get('/Width', '?')} x {xobj.get('/Height', '?')}")
                                print(f"      - 色彩空间: {xobj.get('/ColorSpace', '?')}")
                                print(f"      - 位深度: {xobj.get('/BitsPerComponent', '?')}")
                else:
                    print(f"  无XObject")
                
                if '/Font' in resources:
                    fonts = resources['/Font']
                    print(f"  Font数量: {len(fonts)}")
                
                if '/ProcSet' in resources:
                    print(f"  ProcSet: {resources['/ProcSet']}")
            else:
                print(f"  无Resources")
        
        print(f"\n根对象键:")
        print(f"  {list(pdf.Root.keys())}")
        
        if '/StructTreeRoot' in pdf.Root:
            struct_tree = pdf.Root['/StructTreeRoot']
            print(f"\n结构树:")
            print(f"  类型: {struct_tree.get('/Type', '?')}")
            print(f"  子元素: {struct_tree.get('/K', '?')}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python inspect_pdf_resources.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    inspect_pdf_resources(pdf_path)