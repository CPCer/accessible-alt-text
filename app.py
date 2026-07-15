import os
import sys
import uuid
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from pdf_alt_text import PDFAltTextGenerator

app = Flask(__name__)
CORS(app)

UPLOAD_DIR = Path("uploads")
OUTPUT_DIR = Path("output")
LOG_DIR = Path("logs")
EXTRACTED_IMAGES_DIR = Path("extracted_images")

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)
EXTRACTED_IMAGES_DIR.mkdir(exist_ok=True)

ALLOWED_EXTENSIONS = {'pdf'}

processing_tasks = {}


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


@app.route('/api/upload', methods=['POST'])
def upload_pdf():
    if 'file' not in request.files:
        return jsonify({"error": "未上传文件"}), 400
    
    file = request.files['file']
    
    if file.filename == '':
        return jsonify({"error": "文件名不能为空"}), 400
    
    if not allowed_file(file.filename):
        return jsonify({"error": "只支持PDF文件"}), 400
    
    task_id = str(uuid.uuid4())
    filename = f"{task_id}_{file.filename}"
    file_path = UPLOAD_DIR / filename
    
    file.save(str(file_path))
    
    processing_tasks[task_id] = {
        'status': 'uploaded',
        'filename': file.filename,
        'original_filename': file.filename,
        'upload_path': str(file_path),
        'output_path': None,
        'log_path': None,
        'images_info': [],
        'log_entries': [],
        'stats': {
            'total_extracted': 0,
            'valid_images': 0,
            'skipped_count': 0,
            'success_count': 0,
            'failed_count': 0
        }
    }
    
    return jsonify({
        "task_id": task_id,
        "filename": file.filename,
        "message": "文件上传成功"
    }), 200


@app.route('/api/process', methods=['POST'])
def process_pdf():
    data = request.get_json()
    task_id = data.get('task_id')
    
    if task_id not in processing_tasks:
        return jsonify({"error": "任务不存在"}), 400
    
    task = processing_tasks[task_id]
    
    if task['status'] == 'processing':
        return jsonify({"error": "正在处理中，请稍后"}), 400
    
    task['status'] = 'processing'
    
    try:
        generator = PDFAltTextGenerator(
            pdf_path=task['upload_path'],
            output_dir=str(OUTPUT_DIR),
            log_dir=str(LOG_DIR)
        )
        generator.run()

        output_filename = f"{Path(task['upload_path']).stem}_with_alt.pdf"
        task['output_path'] = str(OUTPUT_DIR / output_filename)
        task['log_entries'] = generator.log_entries
        task['stats'] = {
            'total_extracted': len(generator.images_info) + generator.skipped_count,
            'valid_images': len(generator.images_info),
            'skipped_count': generator.skipped_count,
            'success_count': generator.success_count,
            'failed_count': generator.failed_count
        }

        # Save extracted images to disk for frontend preview
        task_images_dir = EXTRACTED_IMAGES_DIR / task_id
        task_images_dir.mkdir(exist_ok=True)
        for img in generator.images_info:
            img_path = task_images_dir / img['filename']
            with open(img_path, 'wb') as f:
                f.write(img['bytes'])

        images_info = []
        for img in generator.images_info:
            images_info.append({
                'id': f"img_{img['page_num']}_{img['img_index']}",
                'page_num': img['page_num'],
                'img_index': img['img_index'],
                'width': img['width'],
                'height': img['height'],
                'ext': img['ext'],
                'source': img['source'],
                'filename': img['filename'],
                'alt_text': generator.generate_alt_text(img),
                'image_url': f"image/{task_id}/{img['filename']}",
                'decorative': False,
                'generated': True
            })
        task['images_info'] = images_info
        
        task['status'] = 'completed'
        
        return jsonify({
            "task_id": task_id,
            "status": "completed",
            "stats": task['stats'],
            "message": "处理完成"
        }), 200
        
    except Exception as e:
        task['status'] = 'failed'
        task['error'] = str(e)
        
        return jsonify({
            "task_id": task_id,
            "status": "failed",
            "error": str(e)
        }), 500


@app.route('/api/results/<task_id>', methods=['GET'])
def get_results(task_id):
    if task_id not in processing_tasks:
        return jsonify({"error": "任务不存在"}), 400
    
    task = processing_tasks[task_id]
    
    return jsonify({
        "task_id": task_id,
        "status": task['status'],
        "filename": task['filename'],
        "stats": task['stats'],
        "images": task.get('images_info', []),
        "output_path": task.get('output_path'),
        "error": task.get('error')
    }), 200


@app.route('/api/log/<task_id>', methods=['GET'])
def get_log(task_id):
    if task_id not in processing_tasks:
        return jsonify({"error": "任务不存在"}), 400
    
    task = processing_tasks[task_id]
    
    return jsonify({
        "task_id": task_id,
        "log_entries": task.get('log_entries', [])
    }), 200


@app.route('/api/download/<task_id>', methods=['GET'])
def download_result(task_id):
    if task_id not in processing_tasks:
        return jsonify({"error": "任务不存在"}), 400
    
    task = processing_tasks[task_id]
    
    if task['status'] != 'completed' or not task['output_path']:
        return jsonify({"error": "处理未完成或无输出文件"}), 400
    
    output_path = Path(task['output_path'])
    
    if not output_path.exists():
        return jsonify({"error": "输出文件不存在"}), 404
    
    return send_from_directory(
        str(output_path.parent),
        output_path.name,
        as_attachment=True,
        download_name=f"{task['original_filename'].replace('.pdf', '')}_with_alt.pdf"
    )


@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({"status": "ok", "message": "服务运行正常"}), 200


@app.route('/api/pdf/<task_id>', methods=['GET'])
def serve_pdf(task_id):
    if task_id not in processing_tasks:
        return jsonify({"error": "任务不存在"}), 400

    task = processing_tasks[task_id]
    upload_path = Path(task['upload_path'])

    if not upload_path.exists():
        return jsonify({"error": "文件不存在"}), 404

    return send_from_directory(str(upload_path.parent), upload_path.name)


@app.route('/api/image/<task_id>/<filename>', methods=['GET'])
def serve_extracted_image(task_id, filename):
    img_dir = EXTRACTED_IMAGES_DIR / task_id

    if not img_dir.exists():
        return jsonify({"error": "图片不存在"}), 404

    return send_from_directory(str(img_dir), filename)


@app.route('/', methods=['GET'])
def index():
    return send_file('pdf-alt-text-demo.html')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)