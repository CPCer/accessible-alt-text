import sys
from pathlib import Path
import pikepdf


def test_add_alt_to_figure(pdf_path):
    print("=" * 60)
    print("测试为Figure添加Alt文本")
    print("=" * 60)
    
    output_path = Path(pdf_path).parent / f"{Path(pdf_path).stem}_fig_alt.pdf"
    
    with pikepdf.open(pdf_path) as pdf:
        if '/StructTreeRoot' not in pdf.Root:
            print("无结构树")
            return
        
        struct_tree = pdf.Root['/StructTreeRoot']
        figure_count = 0
        
        def add_alt(item):
            nonlocal figure_count
            
            if isinstance(item, pikepdf.Dictionary):
                struct_type = str(item.get('/S', '')) if item.get('/S') else ''
                
                if struct_type == '/Figure':
                    item['/Alt'] = "测试图片替代文本"
                    figure_count += 1
                    print(f"✓ 为第{figure_count}个Figure添加了Alt文本")
                
                if '/K' in item:
                    add_alt(item['/K'])
            
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    add_alt(child)
            
            elif hasattr(item, 'get_object'):
                add_alt(item.get_object())
        
        add_alt(struct_tree)
        
        pdf.save(output_path)
    
    print(f"\n输出文件: {output_path}")
    
    with pikepdf.open(output_path) as pdf2:
        struct_tree2 = pdf2.Root['/StructTreeRoot']
        alt_count = 0
        
        def count_alts(item):
            nonlocal alt_count
            
            if isinstance(item, pikepdf.Dictionary):
                if '/Alt' in item:
                    alt_count += 1
                    print(f"✓ 找到Alt文本: {item['/Alt']}")
                
                if '/K' in item:
                    count_alts(item['/K'])
            
            elif isinstance(item, pikepdf.Array):
                for child in item:
                    count_alts(child)
            
            elif hasattr(item, 'get_object'):
                count_alts(item.get_object())
        
        count_alts(struct_tree2)
        
        print(f"\n共找到 {alt_count} 个Alt文本")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python test_struct_tree.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    test_add_alt_to_figure(pdf_path)