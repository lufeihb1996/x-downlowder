from http.server import BaseHTTPRequestHandler
import urllib.parse
import json
import yt_dlp

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed_path.query)
        url = query.get('url', [None])[0]

        if not url:
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "缺少 url 参数"}).encode('utf-8'))
            return

        try:
            ydl_opts = {
                'no_warnings': True,
                'noplaylist': True,
                'quiet': True,
                'skip_download': True
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                
                formats = []
                for f in info.get('formats', []):
                    # Filter for mp4 container containing height resolution
                    if f.get('url') and (f.get('ext') == 'mp4' or f.get('container') == 'mp4') and f.get('height'):
                        formats.append({
                            'formatId': f.get('format_id'),
                            'resolution': f"{f.get('width', '?')}x{f.get('height')}",
                            'height': f.get('height'),
                            'width': f.get('width', 0),
                            'ext': f.get('ext'),
                            'url': f.get('url')
                        })

                # Sort by height descending
                formats.sort(key=lambda x: x['height'], reverse=True)
                
                # Deduplicate by resolution dimensions
                unique_formats = []
                seen = set()
                for f in formats:
                    if f['resolution'] not in seen:
                        seen.add(f['resolution'])
                        unique_formats.append(f)

                res_data = {
                    'title': info.get('title') or info.get('description') or 'Twitter 视频',
                    'thumbnail': info.get('thumbnail') or (info.get('thumbnails') and info.get('thumbnails')[0].get('url')) or '',
                    'duration': info.get('duration') or None,
                    'formats': unique_formats
                }

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(res_data).encode('utf-8'))

        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps({"error": f"解析视频失败：{str(e)}"}).encode('utf-8'))
