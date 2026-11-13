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
                # Count manual page breaks
                page_breaks = 0
                for para in doc.paragraphs:
                    for run in para.runs:
                        xml = run._element.xml
                        if 'w:br' in xml and 'type="page"' in xml:
                            page_breaks += 1
                if page_breaks > 0:
                    return page_breaks + 1
                # Fallback: Estimate by paragraphs
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
    # Base path points to project root
    base_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    def do_GET(self):
        """Handle GET requests for serving HTML pages and static files."""
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            html_path = os.path.join(self.base_path, 'templates', 'hotspot.html')
            try:
                with open(html_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                self.wfile.write(html_content.encode())
            except FileNotFoundError:
                self.send_error(404, 'Template file not found: hotspot.html')
                
        elif self.path.startswith('/success'):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            
            success_path = os.path.join(self.base_path, 'templates', 'hotspot_uploaded.html')
            try:
                with open(success_path, 'r', encoding='utf-8') as f:
                    html_content = f.read()
                self.wfile.write(html_content.encode())
            except FileNotFoundError:
                self.send_error(404, 'Template file not found: hotspot_uploaded.html')
                
        elif self.path.startswith('/upload'):
            self.send_response(302)
            self.send_header('Location', '/')
            self.end_headers()
            
        elif self.path.startswith('/static/'):
            file_path = os.path.join(self.base_path, self.path[1:])
            try:
                with open(file_path, 'rb') as f:
                    content = f.read()
                
                if self.path.endswith('.css'):
                    content_type = 'text/css'
                elif self.path.endswith('.js'):
                    content_type = 'application/javascript'
                elif self.path.endswith('.jpg') or self.path.endswith('.jpeg'):
                    content_type = 'image/jpeg'
                elif self.path.endswith('.png'):
                    content_type = 'image/png'
                else:
                    content_type = 'application/octet-stream'
                
                self.send_response(200)
                self.send_header('Content-type', content_type)
                self.end_headers()
                self.wfile.write(content)
            except FileNotFoundError:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found')
        else:
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests for file uploads."""
        if self.path == '/upload':
            content_type = self.headers.get('Content-Type', '')
            if 'multipart/form-data' not in content_type:
                self.send_response(400)
                self.end_headers()
                return
            
            try:
                boundary = content_type.split('boundary=')[1].encode()
                remainbytes = int(self.headers['Content-Length'])
                line = self.rfile.readline()
                remainbytes -= len(line)
                
                if boundary not in line:
                    self.send_response(400)
                    self.end_headers()
                    return
                
                line = self.rfile.readline()
                remainbytes -= len(line)
                
                filename = None
                for part in line.decode().split(';'):
                    if 'filename=' in part:
                        filename = part.split('filename=')[1].strip().strip('"')
                        break
                
                if not filename:
                    self.send_response(400)
                    self.end_headers()
                    return
                
                line = self.rfile.readline()
                remainbytes -= len(line)
                line = self.rfile.readline()
                remainbytes -= len(line)
                
                filepath = os.path.join(self.upload_dir, filename)
                base, ext = os.path.splitext(filepath)
                counter = 1
                while os.path.exists(filepath):
                    filepath = f"{base}_{counter}{ext}"
                    counter += 1
                
                with open(filepath, 'wb') as f:
                    preline = self.rfile.readline()
                    remainbytes -= len(preline)
                    
                    while remainbytes > 0:
                        line = self.rfile.readline()
                        remainbytes -= len(line)
                        
                        if boundary in line:
                            preline = preline[0:-1]
                            if preline.endswith(b'\r'):
                                preline = preline[0:-1]
                            f.write(preline)
                            break
                        else:
                            f.write(preline)
                            preline = line
                
                # --- OFFLINE JOB CREATION ---
                import time
                import json
                job_id = f"LOCAL-{int(time.time())}"
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
                
                # Trigger kiosk OptionsScreen
                if self.callback:
                    self.callback(filepath, job_data)
                
                # Send JSON success response back to frontend JS
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'status': 'success', 'filename': filename}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print(f"Successfully uploaded {filename}")
                
            except Exception as e:
                print(f"Error during file upload: {e}")
                # Send JSON response back to the frontend JavaScript with a redirect
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                
                response = {'status': 'success', 'filename': filename, 'redirect': '/success'}
                self.wfile.write(json.dumps(response).encode('utf-8'))
                print(f"Successfully uploaded {filename}")

    def do_GET(self):
        """Handle GET requests, serving the portal or the success validation page."""
        if self.path in ('/success', '/success.html'):
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
        else:
            # Fall back to default file serving for CSS, JS, and the root upload page
            super().do_GET()

    def send_error(self, code, message=None, explain=None):
        """Override the default 404 error page to redirect back to the upload screen."""
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
        
        # Create upload directory if it doesn't exist
        os.makedirs(self.upload_directory, exist_ok=True)
        
        # Configure the request handler
        SimpleHTTPRequestHandler.upload_dir = self.upload_directory
        SimpleHTTPRequestHandler.callback = self.callback
    
    def start(self):
        """Start the HTTP server in a separate thread."""
        try:
            self.server_thread = threading.Thread(target=self._run_server, daemon=True)
            self.server_thread.start()
            
            print(f"Server started automatically on port {self.port}")
            print(f"Files will be saved to: {self.upload_directory}")
            
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def _run_server(self):
        """Internal method to run the HTTP server."""
        try:
            with socketserver.TCPServer(("0.0.0.0", self.port), SimpleHTTPRequestHandler) as httpd:
                self.server = httpd
                print(f"HTTP Server successfully bound to port {self.port}")
                httpd.serve_forever()
        except Exception as e:
            print(f"Server error: {e}")
    
    def stop(self):
        """Stop the HTTP server."""
        if self.server:
            print("Shutting down server...")
            self.server.shutdown()
            self.server = None
    
    def update_callback(self, callback):
        self.callback = callback
        SimpleHTTPRequestHandler.callback = callback

class HotspotConfig:
    """Configuration settings for the hotspot."""
    
    # Default hotspot settings
    HOTSPOT_NAME = "PrinTech Hotspot"
    HOTSPOT_PASSWORD = "printech123"
    HOTSPOT_IP = "192.168.137.1"
    DEFAULT_PORT = 8080
    
    @classmethod
    def get_hotspot_url(cls, port=None):
        """Get the full hotspot URL."""
        port = port or cls.DEFAULT_PORT
        return f"http://{cls.HOTSPOT_IP}:{port}"
    
    @classmethod
    def get_upload_directory(cls):
        """Save directly to the main app's downloads folder."""
        return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "downloads")
    
    @classmethod
    def generate_qr_code(cls, port=None, output_path=None):
        """Generate a QR code for the hotspot file upload URL."""
        port = port or cls.DEFAULT_PORT
        url = f"http://{cls.HOTSPOT_IP}:{port}"
        
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