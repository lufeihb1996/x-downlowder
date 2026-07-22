import os
import sys
import urllib.parse
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

# Reconfigure stdout/stderr for UTF-8 on Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

# Add current directory to sys.path to allow importing from api package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api.parse as parse_module
import api.proxy as proxy_module

class LocalDevHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        public_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'public')
        super().__init__(*args, directory=public_dir, **kwargs)

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        if path == '/api/parse' or path == '/api/parse/':
            parse_module.handler.do_GET(self)
        elif path == '/api/proxy' or path == '/api/proxy/':
            proxy_module.handler.do_GET(self)
        else:
            super().do_GET()

def run(port=8088):
    server_address = ('0.0.0.0', port)
    httpd = ThreadingHTTPServer(server_address, LocalDevHandler)
    print("==================================================")
    print(f"X-Downloader 本地服务已成功启动！")
    print(f"本地访问地址: http://localhost:{port}")
    print("==================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n服务已停止。")
        httpd.server_close()

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8088
    run(port)
