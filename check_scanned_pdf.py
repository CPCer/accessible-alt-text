import sys
from pathlib import Path
import fitz


def check_scanned_pdf(pdf_path):
    print("=" * 60)
    print("扫描件PDF检查")
    print("=" * 60)
    
    doc = fitz.open(pdf_path)
    
    for page_num in range(doc.page_count):
        page = doc.load_page(page_num)
        
        print(f"\n--- 页面 {page_num + 1} ---")
        
        content = page.get_text("text")
        print(f"文本内容长度: {len(content)}")
        print(f"文本预览: '{content[:200]}'")
        
        text_blocks = page.get_text("blocks")
        print(f"文本块数量: {len(text_blocks)}")
        
        if len(text_blocks) > 0:
            print(f"第一个文本块: {text_blocks[0][4][:100]}")
        
        images = page.get_images(full=True)
        print(f"图片对象数量: {len(images)}")
        
        pix = page.get_pixmap()
        print(f"页面像素: {pix.width} x {pix.height}")
        print(f"页面尺寸: {page.rect.width} x {page.rect.height} 点")
        
        xref = page.get_contents()[0] if page.get_contents() else None
        if xref:
            content_stream = doc.xref_object(xref, compressed=False)
            print(f"\n内容流预览 (前500字符):")
            print(f"{content_stream[:500]}")
            
            if "/Image" in content_stream:
                print("\n✓ 内容流中包含图像引用")
            else:
                print("\n✗ 内容流中不包含图像引用")
        
        page_text_density = len(content) / (page.rect.width * page.rect.height)
        print(f"\n文本密度: {page_text_density:.6f} 字符/平方点")
        
        if len(content) > 0 and len(images) == 0:
            print("\n这可能是一个OCR后的扫描件，文本层已添加但原始图像未作为XObject存储")
            print("建议：使用页面栅格化方式获取图像")
    
    doc.close()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python check_scanned_pdf.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not Path(pdf_path).exists():
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    check_scanned_pdf(pdf_path)