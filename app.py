import os
import uuid
import requests
from flask import Flask, request, jsonify, send_file
from playwright.sync_api import sync_playwright

app = Flask(__name__)
DOWNLOAD_DIR = "/app/downloads"
BASE_URL = "https://www.kdocs.cn"  # 金山文档域名

def convert_to_pdf(doc_url):
    """使用无头浏览器转换文档为PDF"""
    filename = f"{str(uuid.uuid4())}.pdf"
    output_path = os.path.join(DOWNLOAD_DIR, filename)
    
    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context()
        page = context.new_page()
        
        # 访问文档页面
        page.goto(doc_url)
        
        # 等待文档加载完成（根据实际页面调整选择器）
        page.wait_for_selector('.kdocs-header', timeout=30000)
        
        # 点击导出按钮
        page.click('button:has-text("文件")')
        page.click('text=导出为')
        page.click('text=PDF')
        
        # 等待下载开始
        with page.expect_download() as download_info:
            page.click('button:has-text("导出")')
        download = download_info.value
        
        # 保存PDF文件
        download.save_as(output_path)
        browser.close()
    
    return filename

@app.route('/convert', methods=['POST'])
def convert_handler():
    """处理转换请求"""
    data = request.json
    if not data or 'url' not in data:
        return jsonify(error="Missing document URL"), 400
    
    try:
        # 验证金山文档链接
        if BASE_URL not in data['url']:
            return jsonify(error="Invalid WPS URL"), 400
            
        pdf_name = convert_to_pdf(data['url'])
        return jsonify(
            download_url=f"http://{request.host}/download/{pdf_name}",
            filename=pdf_name
        )
    except Exception as e:
        return jsonify(error=str(e)), 500

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """提供文件下载"""
    file_path = os.path.join(DOWNLOAD_DIR, filename)
    if not os.path.exists(file_path):
        return jsonify(error="File not found"), 404
    return send_file(file_path, as_attachment=True)


# 在app.py中添加
API_KEY = "YOUR_SECRET_KEY"

@app.before_request
def check_auth():
    if request.endpoint in ['convert_handler']:
        if request.headers.get('X-API-KEY') != API_KEY:
            return jsonify(error="Unauthorized"), 401

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)