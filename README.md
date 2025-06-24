# wps2pdf


要实现这个服务，以下是完整的解决方案，包含Docker服务端部署和iOS快捷指令配置：

### 一、服务端实现（部署到群晖Docker）

1. **创建项目目录结构**：
   ```
   wps2pdf/
   ├── app.py
   ├── requirements.txt
   ├── Dockerfile
   └── downloads/ (空目录)
   ```

2. **app.py** (Flask服务核心)：
```python
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
        page.click('text=导出为")
        page.click('text=PDF")
        
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
```

3. **requirements.txt**：
```
flask
playwright
requests
```

4. **Dockerfile**：
```Dockerfile
FROM python:3.9-slim

# 安装无头浏览器依赖
RUN apt-get update && \
    apt-get install -y \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt && \
    playwright install chromium && \
    playwright install-deps chromium

VOLUME /app/downloads
EXPOSE 5000
CMD ["python", "app.py"]
```

### 二、群晖Docker部署步骤

1. 将项目文件夹上传到群晖
2. 打开Docker套件 → 映像 → 新增 → 从Dockerfile构建
3. 设置构建路径为项目目录
4. 构建完成后创建容器：
   - 映射端口：`5000:5000`
   - 挂载卷：`/host/path/downloads:/app/downloads`
   - 设置重启策略：总是重新启动

5. 启动容器后获取群晖IP：`http://<群晖IP>:5000/convert`

### 三、iOS快捷指令配置

1. **创建快捷指令**：
   - 名称：`WPS转PDF`
   - 添加操作：
     ```
     1. 获取剪贴板内容 → 存储到变量 (docUrl)
     2. URL：http://<群晖IP>:5000/convert
     3. 方法：POST
     4. 请求体：JSON
        {
          "url": "{docUrl}"
        }
     5. 获取URL内容
     6. 从JSON中获取值：
         键路径：download_url
     7. 下载URL
     8. 存储文件 (选择位置)
     ```

2. **使用方式**：
   1. 在金山文档APP分享获取链接
   2. 复制链接到剪贴板
   3. 运行快捷指令
   4. 自动接收并保存PDF文件

### 四、安全增强建议（可选）

1. **添加API密钥验证**：
   ```python
   # 在app.py中添加
   API_KEY = "YOUR_SECRET_KEY"

   @app.before_request
   def check_auth():
       if request.endpoint in ['convert_handler']:
           if request.headers.get('X-API-KEY') != API_KEY:
               return jsonify(error="Unauthorized"), 401
   ```

2. **快捷指令中添加Header**：
   - 在HTTP请求步骤中添加头：
     ```
     Key: X-API-KEY
     Value: YOUR_SECRET_KEY
     ```

### 五、注意事项

1. **首次启动准备**：
   - Docker首次构建时会下载Chromium（约200MB）
   - 群晖需开启5000端口访问权限

2. **文档访问要求**：
   - 目标文档必须设置为"任何人可查看"（金山文档权限要求）
   - 转换大文档时可能需要增加超时时间

3. **性能优化**：
   ```python
   # 在convert函数中添加优化参数
   browser = p.chromium.launch(
       headless=True,
       args=['--disable-gpu', '--single-process']
   )
   ```

4. **清理机制**（添加定时任务）：
   ```python
   # 在app.py中添加定时清理
   import schedule
   import threading
   import time

   def clean_files():
       """定期删除旧文件"""
       for file in os.listdir(DOWNLOAD_DIR):
           file_path = os.path.join(DOWNLOAD_DIR, file)
           if os.path.isfile(file_path):
               # 删除超过1小时的文件
               if time.time() - os.path.getctime(file_path) > 3600:
                   os.remove(file_path)

   def scheduler_thread():
       while True:
           schedule.run_pending()
           time.sleep(60)

   # 在main中添加
   if __name__ == '__main__':
       schedule.every().hour.do(clean_files)
       t = threading.Thread(target=scheduler_thread)
       t.daemon = True
       t.start()
       app.run(host='0.0.0.0', port=5000)
   ```

这个方案实现了完整的文档转换流水线：
1. iOS快捷指令提交文档链接
2. Docker服务使用无头浏览器转换PDF
3. 返回下载链接自动保存到设备

转换成功率取决于金山文档页面的稳定性，如果遇到界面更新可能需要调整CSS选择器。建议定期维护Docker镜像以确保浏览器兼容性。
