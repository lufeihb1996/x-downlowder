require('dotenv').config();
const express = require('express');
const path = require('path');
const axios = require('axios');
const youtubedl = require('youtube-dl-exec');

const app = express();
const PORT = process.env.PORT || 8090;

const DOWNLOAD_USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36';

app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

// Video Parsing API
app.get('/api/video/parse', async (req, res) => {
  const url = String(req.query.url || '').trim();
  if (!url) {
    return res.status(400).json({ error: '请提供视频链接' });
  }

  try {
    const info = await youtubedl(url, {
      dumpSingleJson: true,
      noWarnings: true,
      noPlaylist: true,
      userAgent: DOWNLOAD_USER_AGENT
    });

    const formats = (info.formats || [])
      .filter((f) => f.url && (f.ext === 'mp4' || f.container === 'mp4') && f.height)
      .map((f) => ({
        formatId: f.format_id,
        resolution: `${f.width || '?'}x${f.height}`,
        height: f.height,
        width: f.width || 0,
        ext: f.ext,
        url: f.url
      }))
      .sort((a, b) => b.height - a.height);

    // Deduplicate by resolution dimensions
    const uniqueFormats = [];
    const seenDimensions = new Set();
    for (const f of formats) {
      if (!seenDimensions.has(f.resolution)) {
        seenDimensions.add(f.resolution);
        uniqueFormats.push(f);
      }
    }

    res.json({
      title: info.title || info.description || 'Twitter 视频',
      thumbnail: info.thumbnail || (info.thumbnails && info.thumbnails[0]?.url) || '',
      duration: info.duration || null,
      formats: uniqueFormats
    });
  } catch (error) {
    console.error('Parse formats error:', error.message);
    res.status(500).json({ error: `解析视频失败：${error.message || '请确保是合规的公开视频链接。'}` });
  }
});

// Proxy Download API
app.get('/api/video/download-proxy', async (req, res) => {
  const videoUrl = String(req.query.url || '').trim();
  if (!videoUrl) {
    return res.status(400).send('缺少视频链接');
  }

  try {
    const response = await axios.get(videoUrl, {
      responseType: 'stream',
      timeout: 60000,
      headers: {
        'User-Agent': DOWNLOAD_USER_AGENT,
        'Referer': 'https://x.com/' // Spoof referrer to bypass 403 blocks
      }
    });

    res.setHeader('Content-Type', response.headers['content-type'] || 'video/mp4');
    res.setHeader('Content-Length', response.headers['content-length'] || '');
    res.setHeader('Content-Disposition', `attachment; filename="x-video-${Date.now()}.mp4"`);

    response.data.pipe(res);
  } catch (error) {
    console.error('Download proxy error:', error.message);
    res.status(500).send(`视频下载代理出错：${error.message}`);
  }
});

app.listen(PORT, () => {
  console.log('====================================================');
  console.log(`X Video Downloader 已启动: http://localhost:${PORT}`);
  console.log('====================================================');
});
