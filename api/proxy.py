from http.server import BaseHTTPRequestHandler
import urllib.parse
import urllib.request
import time

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        url = query.get('url', [None])[0]

        if not url:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"Missing url parameter")
            return

        try:
            req = urllib.request.Request(
                url,
                headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                    'Referer': 'https://x.com/' # Spoof referer to bypass Twitter CDN protection
                }
            )
            with urllib.request.urlopen(req, timeout=60) as response:
                self.send_response(200)
                self.send_header('Content-Type', 'application/octet-stream')
                self.send_header('Content-Length', response.headers.get('Content-Length') or '')
                self.send_header('Content-Disposition', f'attachment; filename="x-video-{int(time.time())}.mp4"')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.send_header('Access-Control-Expose-Headers', 'Content-Length, Content-Disposition')
                self.end_headers()
                
                # Stream content in chunks to save memory
                chunk_size = 1024 * 64
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(f"视频下载代理出错：{str(e)}".encode('utf-8'))
