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
        self.figure_elements = []  # Track all Figure elements with preview info
        self.reading_order = []  # Reading order per page: list of {type, content, bbox}

    def log(self, level, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level.upper()}] {message}"
        self.log_entries.append(entry)
        print(entry)

    def is_inside(self, inner, outer, margin=1.0):
        """Check if inner rect is completely inside outer rect"""
        return (inner.x0 >= outer.x0 - margin and inner.y0 >= outer.y0 - margin and
                inner.x1 <= outer.x1 + margin and inner.y1 <= outer.y1 + margin and
                (inner.x1 - inner.x0) < (outer.x1 - outer.x0) - margin)

    def get_significant_drawings(self, page):
        """Extract significant drawings (figures) from a page, filtering out small/nested ones"""
        drawings = page.get_drawings()

        # Filter by area
        candidates = []
        for d in drawings:
            rect = d.get('rect')
            area = rect.width * rect.height
            if area > 80:
                candidates.append(rect)

        # Remove drawings that are completely inside another drawing
        significant = []
        for rect in candidates:
            is_nested = False
            for other in candidates:
                if rect is not other and self.is_inside(rect, other):
                    is_nested = True
                    break
            if not is_nested:
                significant.append(rect)

        # Sort by y coordinate (top to bottom), then x (left to right)
        significant.sort(key=lambda r: (round(r.y0, 2), r.x0))
        return significant

    def crop_figure_preview(self, page_pixmap, pdf_rect, page_rect):
        """Crop a figure preview from the rasterized page"""
        scale_x = page_pixmap.width / page_rect.width
        scale_y = page_pixmap.height / page_rect.height

        x0 = max(0, int(pdf_rect.x0 * scale_x))
        y0 = max(0, int(pdf_rect.y0 * scale_y))
        x1 = min(page_pixmap.width, int(pdf_rect.x1 * scale_x))
        y1 = min(page_pixmap.height, int(pdf_rect.y1 * scale_y))

        if x1 <= x0 or y1 <= y0:
            return None

        img = Image.open(io.BytesIO(page_pixmap.tobytes("png")))
        cropped = img.crop((x0, y0, x1, y1))
        return cropped

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
            self.log("INFO", "未找到XObject图像，尝试页面栅格化并提取Figure预览")

            zoom = self.dpi / 72
            mat = fitz.Matrix(zoom, zoom)

            for page_num in range(total_pages):
                page = doc.load_page(page_num)

                # Rasterize the page
                pix = page.get_pixmap(matrix=mat)
                page_bytes = pix.tobytes("png")
                page_rect = page.rect

                # Get significant drawings (figures)
                significant_rects = self.get_significant_drawings(page)

                # Build reading order for this page
                page_reading_order = []
                text_blocks = []

                # Extract text blocks
                blocks = page.get_text("dict")["blocks"]
                for block in blocks:
                    if block["type"] == 0:  # text block
                        text_blocks.append({
                            "type": "text",
                            "bbox": block["bbox"],
                            "y0": block["bbox"][1],
                            "content": ""
                        })
                        for line in block.get("lines", []):
                            for span in line.get("spans", []):
                                text_blocks[-1]["content"] += span.get("text", "")

                # Merge text blocks and figure blocks by y coordinate
                all_items = []
                for tb in text_blocks:
                    all_items.append({
                        "type": "text",
                        "bbox": tb["bbox"],
                        "y0": tb["y0"],
                        "content": tb["content"].strip()
                    })
                for rect in significant_rects:
                    all_items.append({
                        "type": "figure",
                        "bbox": (rect.x0, rect.y0, rect.x1, rect.y1),
                        "y0": rect.y0,
                        "content": ""  # Will be filled with alt text later
                    })

                # Sort by y coordinate
                all_items.sort(key=lambda x: round(x["y0"], 2))
                page_reading_order = all_items

                # Create figure entries with cropped preview
                for fig_idx, rect in enumerate(significant_rects):
                    cropped = self.crop_figure_preview(pix, rect, page_rect)
                    if cropped:
                        preview_bytes = io.BytesIO()
                        cropped.save(preview_bytes, format="PNG")
                        preview_bytes = preview_bytes.getvalue()
                    else:
                        preview_bytes = page_bytes  # Fallback to full page

                    img_info = {
                        "page_num": page_num + 1,
                        "img_index": fig_idx,
                        "xref": None,
                        "width": int(rect.width * (self.dpi / 72)),
                        "height": int(rect.height * (self.dpi / 72)),
                        "bytes": preview_bytes,
                        "ext": "png",
                        "filename": f"page_{page_num+1}_figure_{fig_idx}.png",
                        "source": "figure",
                        "pdf_rect": (rect.x0, rect.y0, rect.x1, rect.y1)
                    }
                    self.images_info.append(img_info)

                # Store reading order for this page
                self.reading_order.append({
                    "page_num": page_num + 1,
                    "items": page_reading_order
                })

                self.log("INFO", f"页面{page_num+1}: 提取到 {len(significant_rects)} 个Figure元素，阅读顺序含 {len(page_reading_order)} 项")

        doc.close()
        self.log("INFO", f"共提取到 {len(self.images_info)} 张图片")

    def is_valid_image(self, img_info, min_size=30):
        width = img_info["width"]
        height = img_info["height"]

        # For figure elements (cropped from page), use smaller min_size
        # because icons/logos can be small
        effective_min = 5 if img_info["source"] == "figure" else min_size

        if width < effective_min or height < effective_min:
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
        source_text = "XObject图像" if img_info["source"] == "xobject" else "Figure元素"
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

                if img_info["source"] == "figure":
                    self.figure_alts.append({
                        "page_num": img_info["page_num"],
                        "alt_text": alt_text,
                        "width": img_info["width"],
                        "height": img_info["height"],
                        "pdf_rect": img_info.get("pdf_rect")
                    })

            except Exception as e:
                self.failed_count += 1
                self.log("ERROR", f"页面{img_info['page_num']} - {img_info['filename']}: {str(e)}")

        if self.figure_alts:
            self.log("INFO", "尝试为结构树中的Figure元素添加Alt文本")

            if '/StructTreeRoot' in pdf.Root:
                struct_tree = pdf.Root['/StructTreeRoot']
                figure_alt_idx = [0]

                def add_alt_to_figure(item):
                    nonlocal figure_success

                    if isinstance(item, pikepdf.Dictionary):
                        struct_type = str(item.get('/S', '')) if item.get('/S') else ''

                        if struct_type == '/Figure':
                            alt_idx = figure_alt_idx[0] % len(self.figure_alts)
                            alt_text = self.figure_alts[alt_idx]["alt_text"]
                            item['/Alt'] = alt_text
                            figure_alt_idx[0] += 1
                            figure_success += 1
                            self.success_count += 1
                            self.log("SUCCESS", f"结构树Figure元素添加Alt文本 ({figure_success}): {alt_text[:50]}...")

                            # Record Figure element info with preview
                            self.figure_elements.append({
                                'page_num': self.figure_alts[alt_idx]["page_num"],
                                'figure_index': figure_success,
                                'alt_text': alt_text,
                                'source': 'figure',
                                'width': self.figure_alts[alt_idx].get('width', 0),
                                'height': self.figure_alts[alt_idx].get('height', 0),
                                'pdf_rect': self.figure_alts[alt_idx].get('pdf_rect')
                            })

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

        # Update reading order with alt text
        self._update_reading_order_with_alt()

    def _update_reading_order_with_alt(self):
        """Update reading order items with alt text for figures"""
        figure_idx = 0
        for page_order in self.reading_order:
            for item in page_order["items"]:
                if item["type"] == "figure":
                    if figure_idx < len(self.figure_elements):
                        item["content"] = self.figure_elements[figure_idx]["alt_text"]
                        item["figure_idx"] = figure_idx
                        figure_idx += 1

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

## 阅读顺序
"""

        for page_order in self.reading_order:
            md_content += f"\n### 第 {page_order['page_num']} 页\n"
            for i, item in enumerate(page_order["items"]):
                if item["type"] == "text":
                    md_content += f"{i+1}. 文本: \"{item['content'][:60]}{'...' if len(item['content']) > 60 else ''}\"\n"
                else:
                    md_content += f"{i+1}. Figure: {item['content'][:60]}{'...' if len(item.get('content','')) > 60 else ''}\n"

        md_content += """
## 详细记录

"""
        for i, img_info in enumerate(self.images_info):
            source_text = "XObject" if img_info["source"] == "xobject" else "Figure"
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
