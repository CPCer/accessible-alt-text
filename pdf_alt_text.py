import os
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path

import fitz
import pikepdf
from PIL import Image
import io


class PDFAltTextGenerator:
    def __init__(self, pdf_path, output_dir="output", log_dir="logs", dpi=200):
        self.pdf_path = Path(pdf_path)
        self.output_dir = Path(output_dir)
        self.log_dir = Path(log_dir)
        self.dpi = dpi
        self.output_dir.mkdir(exist_ok=True)
        self.log_dir.mkdir(exist_ok=True)
        
        self.images_info = []
        self.processed_count = 0
        self.skipped_count = 0
        self.success_count = 0
        self.failed_count = 0
        self.log_entries = []
        self.figure_alts = []
    
    def log(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level.upper()}] {message}"
        self.log_entries.append(entry)
        print(entry)
    
    def extract_images(self):
        self.log("INFO", f"开始提取图片: {self.pdf_path.name}")
        
        doc = fitz.open(self.pdf_path)
        total_pages = doc.page_count
        self.log("INFO", f"PDF总页数: {total_pages}")
        
        has_xobject_images = False
        
        for page_num in range(total_pages):
            page = doc.load_page(page_num)
            images = page.get_images(full=True)
            
            for img_index, img in enumerate(images):
                xref = img[0]
                base_image = doc.extract_image(xref)
                img_bytes = base_image["image"]
                img_ext = base_image["ext"]
                
                img_info = {
                    "page_num": page_num + 1,
                    "img_index": img_index,
                    "xref": xref,
                    "width": base_image.get("width", 0),
                    "height": base_image.get("height", 0),
                    "bytes": img_bytes,
                    "ext": img_ext,
                    "filename": f"page_{page_num+1}_img_{img_index}.{img_ext}",
                    "source": "xobject"
                }
                self.images_info.append(img_info)
                has_xobject_images = True
        
        if not has_xobject_images:
            self.log("INFO", "未找到XObject图像，尝试页面栅格化")
            
            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)
            
            for page_num in range(total_pages):
                page = doc.load_page(page_num)
                
                pix = page.get_pixmap(matrix=mat)
                img_bytes = pix.tobytes("png")
                
                img_info = {
                    "page_num": page_num + 1,
                    "img_index": 0,
                    "xref": None,
                    "width": pix.width,
                    "height": pix.height,
                    "bytes": img_bytes,
                    "ext": "png",
                    "filename": f"page_{page_num+1}_raster.png",
                    "source": "raster"
                }
                self.images_info.append(img_info)
        
        doc.close()
        self.log("INFO", f"共提取到 {len(self.images_info)} 张图片")
    
    def is_valid_image(self, img_info, min_size=30):
        width = img_info["width"]
        height = img_info["height"]
        
        if width < min_size or height < min_size:
            self.log("DEBUG", f"跳过过小图片: {img_info['filename']} ({width}x{height})")
            return False
        
        if img_info["source"] == "xobject":
            try:
                img = Image.open(io.BytesIO(img_info["bytes"]))
                
                if img.mode in ('L', '1'):
                    pixels = list(img.getdata())
                    if len(set(pixels)) <= 2:
                        self.log("DEBUG", f"跳过空白/纯色图片: {img_info['filename']}")
                        return False
                
                if img.mode == 'RGB':
                    pixels = list(img.getdata())
                    if len(set(pixels)) <= 3:
                        self.log("DEBUG", f"跳过空白/纯色图片: {img_info['filename']}")
                        return False
            except:
                pass
        
        return True
    
    def compute_phash(self, img_info):
        try:
            img = Image.open(io.BytesIO(img_info["bytes"]))
            img = img.resize((32, 32), Image.Resampling.LANCZOS).convert('L')
            pixels = list(img.getdata())
            
            avg = sum(pixels) / len(pixels)
            bits = "".join(str(1 if p > avg else 0) for p in pixels)
            
            return hashlib.md5(bits.encode()).hexdigest()
        except:
            return ""
    
    def filter_images(self):
        self.log("INFO", "开始过滤图片")
        
        valid_images = []
        seen_hashes = set()
        
        for img_info in self.images_info:
            if not self.is_valid_image(img_info):
                self.skipped_count += 1
                continue
            
            img_hash = self.compute_phash(img_info)
            if img_hash and img_hash in seen_hashes:
                self.log("DEBUG", f"跳过重复图片: {img_info['filename']}")
                self.skipped_count += 1
                continue
            
            seen_hashes.add(img_hash)
            img_info["phash"] = img_hash
            valid_images.append(img_info)
        
        self.images_info = valid_images
        self.log("INFO", f"过滤后剩余 {len(self.images_info)} 张有效图片")
    
    def generate_alt_text(self, img_info):
        source_text = "XObject图像" if img_info["source"] == "xobject" else "页面栅格化"
        alt_text = f"图片{img_info['page_num']}-{img_info['img_index']}: {source_text}，第{img_info['page_num']}页，尺寸{img_info['width']}x{img_info['height']}像素。"
        
        return alt_text
    
    def write_alt_text(self):
        self.log("INFO", "开始写入替代文本")
        
        pdf = pikepdf.open(self.pdf_path)
        
        xobject_success = 0
        figure_success = 0
        
        for img_info in self.images_info:
            self.processed_count += 1
            alt_text = self.generate_alt_text(img_info)
            
            try:
                page_index = img_info["page_num"] - 1
                if page_index < len(pdf.pages):
                    page = pdf.pages[page_index]
                    
                    if '/Resources' in page and '/XObject' in page['/Resources']:
                        xobjects = page['/Resources']['/XObject']
                        
                        img_found = False
                        for name in xobjects.keys():
                            xobj = xobjects[name]
                            
                            if '/Subtype' in xobj and xobj['/Subtype'] == '/Image':
                                xobj['/Alt'] = alt_text
                                img_found = True
                                xobject_success += 1
                                self.success_count += 1
                                self.log("SUCCESS", f"页面{img_info['page_num']} - XObject图像: {alt_text[:50]}...")
                                break
                        
                        if img_found:
                            continue
                
                if img_info["source"] == "raster":
                    self.figure_alts.append({
                        "page_num": img_info["page_num"],
                        "alt_text": alt_text
                    })
            
            except Exception as e:
                self.failed_count += 1
                self.log("ERROR", f"页面{img_info['page_num']} - {img_info['filename']}: {str(e)}")
        
        if self.figure_alts:
            self.log("INFO", "尝试为结构树中的Figure元素添加Alt文本")
            
            if '/StructTreeRoot' in pdf.Root:
                struct_tree = pdf.Root['/StructTreeRoot']
                
                def add_alt_to_figure(item):
                    nonlocal figure_success
                    
                    if isinstance(item, pikepdf.Dictionary):
                        struct_type = str(item.get('/S', '')) if item.get('/S') else ''
                        
                        if struct_type == '/Figure':
                            item['/Alt'] = "页面图像内容"
                            figure_success += 1
                            self.success_count += 1
                            self.log("SUCCESS", f"结构树Figure元素添加Alt文本 ({figure_success})")
                        
                        if '/K' in item:
                            add_alt_to_figure(item['/K'])
                    
                    elif isinstance(item, pikepdf.Array):
                        for child in item:
                            add_alt_to_figure(child)
                    
                    elif hasattr(item, 'get_object'):
                        add_alt_to_figure(item.get_object())
                
                add_alt_to_figure(struct_tree)
        
        output_filename = f"{self.pdf_path.stem}_with_alt.pdf"
        output_path = self.output_dir / output_filename
        
        pdf.save(output_path)
        pdf.close()
        
        self.log("INFO", f"处理完成，输出文件: {output_path}")
        if xobject_success > 0:
            self.log("INFO", f"XObject图像Alt文本: {xobject_success} 个")
        if figure_success > 0:
            self.log("INFO", f"结构树Figure Alt文本: {figure_success} 个")
    
    def verify_struct_tree(self):
        try:
            output_path = self.output_dir / f"{self.pdf_path.stem}_with_alt.pdf"
            if not output_path.exists():
                return False
            
            pdf = pikepdf.open(output_path)
            if '/StructTreeRoot' in pdf.Root:
                self.log("SUCCESS", "结构树保留成功")
                pdf.close()
                return True
            else:
                self.log("ERROR", "结构树丢失")
                pdf.close()
                return False
        except Exception as e:
            self.log("ERROR", f"验证结构树失败: {str(e)}")
            return False
    
    def write_log_md(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"log_{timestamp}.md"
        log_path = self.log_dir / log_filename
        
        md_content = f"""# PDF替代文本生成日志

## 基本信息
- **时间戳**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
- **输入文件**: {self.pdf_path.name}
- **文件大小**: {self.pdf_path.stat().st_size / 1024:.2f} KB

## 处理统计
| 项目 | 数量 |
|------|------|
| 提取图片总数 | {len(self.images_info) + self.skipped_count} |
| 过滤后有效图片 | {len(self.images_info)} |
| 跳过图片（过小/空白/重复） | {self.skipped_count} |
| 成功写入替代文本 | {self.success_count} |
| 写入失败 | {self.failed_count} |

## 结构树验证
- **状态**: {'✓ 保留成功' if self.verify_struct_tree() else '✗ 丢失'}

## 详细记录

"""
        
        for i, img_info in enumerate(self.images_info):
            source_text = "XObject" if img_info["source"] == "xobject" else "栅格化"
            md_content += f"""### 图片 {i+1}: {img_info['filename']}
- **页码**: {img_info['page_num']}
- **尺寸**: {img_info['width']} x {img_info['height']}
- **来源**: {source_text}
- **状态**: {'成功' if i < self.success_count else '跳过'}

"""
        
        md_content += """## 日志详情
```
"""
        md_content += "\n".join(self.log_entries)
        md_content += """
```
"""
        
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        
        self.log("INFO", f"日志已写入: {log_path}")
    
    def run(self):
        start_time = time.time()
        self.log("INFO", "=" * 60)
        self.log("INFO", "开始处理PDF替代文本")
        self.log("INFO", "=" * 60)
        
        try:
            self.extract_images()
            self.filter_images()
            self.write_alt_text()
            self.write_log_md()
            
            elapsed_time = time.time() - start_time
            self.log("INFO", "=" * 60)
            self.log("INFO", f"处理完成！总耗时: {elapsed_time:.2f}秒")
            self.log("INFO", f"统计: 提取{len(self.images_info)+self.skipped_count}张 → 有效{len(self.images_info)}张 → 成功{self.success_count}张 → 失败{self.failed_count}张")
            self.log("INFO", "=" * 60)
            
        except Exception as e:
            self.log("ERROR", f"处理失败: {str(e)}")
            self.write_log_md()
            raise


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("用法: python pdf_alt_text.py <PDF文件路径>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    if not os.path.exists(pdf_path):
        print(f"错误: 文件不存在 - {pdf_path}")
        sys.exit(1)
    
    generator = PDFAltTextGenerator(pdf_path)
    generator.run()