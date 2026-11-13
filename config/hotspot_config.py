# hotspot_config.py
"""
Configuration and server logic for the hotspot file upload functionality.
This module handles the HTTP server and file upload processing.
"""

import os
import http.server
import socketserver
import threading
from datetime import datetime
import fitz  # PyMuPDF
from docx import Document
import time
import qrcode
from io import BytesIO
import pytz
import json
import socket

def get_local_ip():
    """Automatically detect the PC's active local network IP address."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.137.1"

def get_total_pages(file_path):
    """Get total pages from PDF or DOCX files."""
    try:
        if file_path.lower().endswith('.pdf'):
            with fitz.open(file_path) as pdf:
                return pdf.page_count
                
        elif file_path.lower().endswith(('.doc', '.docx')):
            try:
                with open(file_path, 'rb') as f:
                    doc = Document(f)
                page_breaks = 0
                for para in doc.paragraphs:
                    for run in para.runs:
                        xml = run._element.xml
                        if 'w:br' in xml and 'type="page"' in xml:
                            page_breaks += 1
                if page_breaks > 0:
                    return page_breaks + 1
                para_count = len(doc.paragraphs)
                return max(1, (para_count // 33) + (1 if para_count % 33 else 0))
            except Exception:
                return 1
    except Exception as e:
        print(f"Error getting total pages: {e}")
        return 1

class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler for file uploads and serving web pages."""
    
    upload_dir = None
    callback = None
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def do_GET(self):
        """Unified, smart GET handler to correctly serve HTML templates, success pages, and static assets."""
        path = self.path.split('?')[0]
        
        # 1. Root URL - Serve the main upload portal template
        if path == '/' or path == '':
            file_path = os.path.join(self.base_path, 'templates', 'hotspot.html')
            if not os.path.exists(file_path):
                file_path = os.path.join(self.base_path, 'templates', 'index.html')
            content_type = 'text/html'
            
        # 2. Success Validation Page with "Upload Another File" button
        elif path in ('/success', '/success.html'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            success_html = """
            <!DOCTYPE html>
            <html>
            <head>
                <meta name="viewport" content="width=device-width, initial-scale=1">
                <title>Upload Successful</title>
                <style>
                    body { font-family: sans-serif; text-align: center; padding: 40px 20px; background-color: #f0f2f5; }
                    .box { background: white; padding: 30px; border-radius: 12px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); max-width: 400px; margin: auto; }
                    h2 { color: #2e7d32; margin-top: 0; }
                    p { color: #555; font-size: 16px; line-height: 1.5; }
                    .btn { display: inline-block; margin-top: 20px; padding: 12px 24px; background: #007bff; color: white; text-decoration: none; border-radius: 8px; font-weight: bold; }
                    .btn:hover { background: #0056b3; }
                </style>
            </head>
            <body>
                <div class="box">
                    <h2>✅ Upload Successful!</h2>
                    <p>Your file has been received and loaded onto the kiosk preview screen.</p>
                    <p><b>Please look at the kiosk monitor</b> to configure your print settings.</p>
                    <a href="/" class="btn">Upload Another File</a>
                </div>
            </body>
            </html>
            """
            self.wfile.write(success_html.encode('utf-8'))
            return
            
        # 3. Static Assets (CSS, JS, Images with flexible path fallback lookup)
        else:
            clean_path = path.lstrip('/')
            file_path = os.path.join(self.base_path, clean_path)
            
            if not os.path.exists(file_path):
                potential_static = os.path.join(self.base_path, 'static', clean_path)
                if os.path.exists(potential_static):
                    file_path = potential_static
                else:
                    if clean_path.startswith('static/'):
                        potential_sub = os.path.join(self.base_path, 'static', clean_path[7:])
                        if os.path.exists(potential_sub):
                            file_path = potential_sub

            if file_path.endswith('.css'):
                content_type = 'text/css'
            elif file_path.endswith('.js'):
                content_type = 'application/javascript'
            elif file_path.endswith('.png'):
                content_type = 'image/png'
            elif file_path.endswith(('.jpg', '.jpeg')):
                content_type = 'image/jpeg'
            elif file_path.endswith('.html'):
                content_type = 'text/html'
            else:
                content_type = 'application/octet-stream'

        if os.path.exists(file_path) and os.path.isfile(file_path):
            try:
                with open(file_path, 'rb') as f:
                    self.send_response(200)
                    self.send_header('Content-type', content_type)
                    self.end_headers()
                    self.wfile.write(f.read())
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                self.wfile.write(b"Internal Server Error")
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"404 Not Found")

    def do_POST(self):
            """Handle POST requests for file uploads with binary safety for PDFs and DOCXs."""
            if self.path == '/upload':
                content_type = self.headers.get('Content-Type', '')
                if 'multipart/form-data' not in content_type:
                    self.send_response(400)
                    self.end_headers()
                    return
                
                try:
                    content_length = int(self.headers.get('Content-Length', 0))
                    body = self.rfile.read(content_length)
                    
                    boundary = content_type.split('boundary=')[1].encode()
                    parts = body.split(b'--' + boundary)
                    
                    filename = None
                    file_content = None
                    
                    for part in parts:
                        if b'filename=' in part:
                            header_end = part.find(b'\r\n\r\n')
                            header_offset = 4
                            if header_end == -1:
                                header_end = part.find(b'\n\n')
                                header_offset = 2
                                
                            if header_end != -1:
                                headers_text = part[:header_end].decode('utf-8', errors='ignore')
                                for line in headers_text.splitlines():
                                    if 'filename=' in line:
                                        for p in line.split(';'):
                                            if 'filename=' in p:
                                                filename = p.split('filename=')[1].strip().strip('"')
                                                break
                                
                                content = part[header_end + header_offset:]
                                if content.endswith(b'\r\n'):
                                    content = content[:-2]
                                elif content.endswith(b'\n'):
                                    content = content[:-1]
                                if content.endswith(b'--'):
                                    content = content[:-2]
                                if content.endswith(b'\r\n'):
                                    content = content[:-2]
                                elif content.endswith(b'\n'):
                                    content = content[:-1]
                                    
                                file_content = content
                                break
                    
                    if not filename or not file_content:
                        self.send_response(400)
                        self.send_header('Content-type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({'status': 'error', 'message': 'No file uploaded'}).encode('utf-8'))
                        return
                    
                    # --- OFFLINE JOB CREATION & PATH FIX ---
                    import time
                    import json
                    job_id = f"LOCAL-{int(time.time())}"
                    
                    saved_filename = f"{job_id}_{filename}"
                    filepath = os.path.join(self.upload_dir, saved_filename)
                    
                    # Write raw binary bytes safely without corruption
                    with open(filepath, 'wb') as f:
                        f.write(file_content)
                    
                    job_data = {
                        'job_id': job_id,
                        'file_name': filename,
                        'file_path': filepath,
                        'path': filepath,
                        'download_url': '',
                        'status': 'pending',
                        'details': [{
                            'num_copies': 1,
                            'page_range': 'all',
                            'color_mode': 'colored',
                            'page_size': 'Letter',
                            'scale_mode': 'fit'
                        }]
                    }
                    
                    if self.callback:
                        self.callback(filepath, job_data)
                    
                    self.send_response(200)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    
                    response = {'status': 'success', 'filename': filename, 'redirect': '/success'}
                    self.wfile.write(json.dumps(response).encode('utf-8'))
                    print(f"Successfully uploaded and saved {filename}")
                    
                except Exception as e:
                    print(f"Error during binary file upload: {e}")
                    self.send_response(500)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'status': 'error', 'message': str(e)}).encode('utf-8'))

    def send_error(self, code, message=None, explain=None):
        if code == 404:
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
        else:
            super().send_error(code, message, explain)

class HotspotServer:
    """Manages the HTTP server for hotspot file transfers."""
    
    def __init__(self, port=8080, upload_directory=None, callback=None):
        self.port = port
        self.upload_directory = upload_directory or HotspotConfig.get_upload_directory()
        self.callback = callback
        self.server = None
        self.server_thread = None
        
        os.makedirs(self.upload_directory, exist_ok=True)
        
        SimpleHTTPRequestHandler.upload_dir = self.upload_directory
        SimpleHTTPRequestHandler.callback = self.callback
    
    def start(self):
        try:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            print(f"Server started automatically on port {self.port}")
            print(f"Files will be saved to: {self.upload_directory}")
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def _run_server(self):
        try:
            with socketserver.TCPServer(("0.0.0.0", self.port), SimpleHTTPRequestHandler) as httpd:
                self.server = httpd
                print(f"HTTP Server successfully bound to port {self.port}")
                httpd.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
    
    def stop(self):
        if self.server:
            print("Shutting down server...")
            self.server.shutdown()
            self.server = None
    
    def update_callback(self, callback):
        self.callback = callback
        SimpleHTTPRequestHandler.callback = callback

class HotspotConfig:
    """Configuration settings for the hotspot."""
    
    HOTSPOT_NAME = "PrinTech Hotspot"
    HOTSPOT_PASSWORD = "printech123"
    DEFAULT_PORT = 8080
    
    @classmethod
    def get_hotspot_url(cls, port=None):
        port = port or cls.DEFAULT_PORT
        active_ip = get_local_ip()
        return f"http://{active_ip}:{port}"
    
    @classmethod
    def get_upload_directory(cls):
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")
    
    @classmethod
    def generate_qr_code(cls, port=None, output_path=None):
        port = port or cls.DEFAULT_PORT
        url = cls.get_hotspot_url(port)
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(url)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if output_path:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path)
            print(f"QR code saved to: {output_path}")
        
        return img

def save_file_to_firebase(file_path, file_name):
    """Compatibility wrapper for offline mode: creates local job data without Firebase."""
    total_pages = get_total_pages(file_path)
    file_size = os.path.getsize(file_path) if os.path.exists(file_path) else 0
    job_id = f"LOCAL-{int(time.time())}"
    
    job_data = {
        'job_id': job_id,
        'file_name': file_name,
        'file_size': file_size,
        'total_pages': total_pages,
        'status': 'pending',
        'local_path': file_path,
        'file_path': file_path,
        'upload_source': 'usb',
        'details': [{
            'file_name': file_name,
            'page_range': 'all',
            'color_mode': 'colored',
            'num_copies': 1,
            'page_size': 'Letter',
            'scale_mode': 'fit'
        }]
    }
    print(f"[Offline Mode] Local job data created for USB/File: {file_name}")
    return job_data