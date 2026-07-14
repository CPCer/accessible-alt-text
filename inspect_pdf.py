import sys
from pathlib import Path
import fitz


def inspect_pdf_structure(pdf_path):
    print("=" * 60)
    print("PDF结构检查")
    print("=" * 60)
    
    doc = fitz.open(pdf_path)
    
    print(f"\n基本信息:")
    print(f"  页数: {doc.page_count}")
    print(f"  是否加密: {doc.is_encrypted}")
    
    print(f"\n页面资源分析:")
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        
        print(f"\n  --- 页面 {page_num + 1} ---")
        
        images = page.get_images(full=True)
        print(f"  get_images() 结果: {len(images)} 张图片")
        
        if images:
            for i, img in enumerate(images):
                print(f"    图片 {i}: xref={img[0]}, width={img[2]}, height={img[3]}, bpc={img[4]}, cs={img[5]}, bbox={img[10]}")
        
        text = page.get_text()
        print(f"  文本内容: {len(text)} 字符")
        print(f"  文本预览: '{text[:100]}...'" if len(text) > 100 else f"  文本内容: '{text}'")
        
        pix = page.get_pixmap()
        print(f"  页面像素: {pix.width} x {pix.height}")
    
    print(f"\n对象统计:")
    print(f"  总对象数: {doc.xref_length() - 1}")
    
    for xref in range(1, min(doc.xref_length(), 50)):
        try:
            obj_type = doc.xref_get_type(xref)
            if obj_type == "stream":
                obj_dict = doc.xref_object(xref, compressed=False)
                if "/Image" in obj_dict:
                    print(f"  XREF {xref}: 图像流")
        except:
            pass
    
    doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python inspect_pdf.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    inspect_pdf_structure(pdf_path)