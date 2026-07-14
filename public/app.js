document.addEventListener('DOMContentLoaded', () => {
  // DOM Elements
  const videoUrlInput = document.getElementById('video-url');
  const btnPaste = document.getElementById('btn-paste');
  const btnParse = document.getElementById('btn-parse');
  
  const loadingCard = document.getElementById('loading-card');
  const errorCard = document.getElementById('error-card');
  const errorMessage = document.getElementById('error-message');
  const btnErrorRetry = document.getElementById('btn-error-retry');
  
  const resultCard = document.getElementById('result-card');
  const videoThumbnail = document.getElementById('video-thumbnail');
  const videoDuration = document.getElementById('video-duration');
  const videoTitle = document.getElementById('video-title');
  const resolutionsList = document.getElementById('resolutions-list');

  // Register PWA Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/sw.js')
        .then((reg) => console.log('Service Worker registered successfully:', reg.scope))
        .catch((err) => console.error('Service Worker registration failed:', err));
    });
  }

  // Paste from clipboard handler
  btnPaste.addEventListener('click', async () => {
    try {
      if (!navigator.clipboard) {
        alert('您的浏览器不支持或未授权读取剪贴板，请手动粘贴。');
        return;
      }
      const text = await navigator.clipboard.readText();
      videoUrlInput.value = text.trim();
      videoUrlInput.focus();
    } catch (err) {
      console.warn('Clipboard read error:', err);
      alert('无法读取剪贴板，请手动粘贴。');
    }
  });

  // Key event listeners
  videoUrlInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') {
      startParse();
    }
  });

  btnParse.addEventListener('click', startParse);
  btnErrorRetry.addEventListener('click', () => {
    errorCard.style.display = 'none';
    videoUrlInput.focus();
  });

  // Core parsing logic
  async function startParse() {
    const rawUrl = videoUrlInput.value.trim();
    if (!rawUrl) {
      showError('请输入有效的 Twitter/X 视频推文链接');
      return;
    }

    // Basic URL validation
    try {
      const parsedUrl = new URL(rawUrl);
      if (!['x.com', 'twitter.com', 'mobile.twitter.com'].some(domain => parsedUrl.hostname.endsWith(domain))) {
        showError('链接不是有效的 Twitter/X 地址，请检查域名');
        return;
      }
    } catch (e) {
      showError('您输入的不是有效的网络链接');
      return;
    }

    // UI state: Show Loading
    hideAllCards();
    loadingCard.style.display = 'block';

    try {
      const res = await fetch(`/api/video/parse?url=${encodeURIComponent(rawUrl)}`);
      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.error || '解析失败');
      }

      // Populate Video Metadata
      videoThumbnail.src = data.thumbnail || 'placeholder-thumb.png';
      videoTitle.textContent = data.title || 'Twitter Video';

      if (data.duration) {
        const mins = Math.floor(data.duration / 60);
        const secs = Math.floor(data.duration % 60);
        videoDuration.textContent = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
        videoDuration.style.display = 'block';
      } else {
        videoDuration.style.display = 'none';
      }

      // Populate Resolutions list
      resolutionsList.innerHTML = '';
      if (!data.formats || data.formats.length === 0) {
        throw new Error('未能在推文中检测到可用视频流');
      }

      data.formats.forEach((f) => {
        const item = document.createElement('div');
        item.className = 'resolution-item';

        // Find shorter dimension for vertical resolution classification
        const [w, h] = (f.resolution || '').split('x').map(Number);
        const shortSide = Math.min(w || h, h || w);

        let badgeText = '标清';
        let badgeClass = 'badge-sd';
        
        if (shortSide >= 1080) {
          badgeText = '超清 1080P';
          badgeClass = 'badge-uhd';
        } else if (shortSide >= 720) {
          badgeText = '高清 720P';
          badgeClass = 'badge-hd';
        } else if (shortSide >= 480) {
          badgeText = '清晰 480P';
          badgeClass = 'badge-sd';
        } else {
          badgeText = '普通';
          badgeClass = 'badge-ld';
        }

        const proxyDownloadUrl = `/api/video/download-proxy?url=${encodeURIComponent(f.url)}`;

        item.innerHTML = `
          <div class="res-info">
            <span class="badge ${badgeClass}">${badgeText}</span>
            <span class="res-dimensions">${f.resolution}</span>
          </div>
          <a href="${proxyDownloadUrl}" download="x-video-${f.height}p.mp4" target="_blank" class="btn-download">
            <i class="fa-solid fa-arrow-down-to-bracket"></i> 下载
          </a>
        `;
        resolutionsList.appendChild(item);
      });

      // Show Result Card
      loadingCard.style.display = 'none';
      resultCard.style.display = 'flex';
    } catch (err) {
      console.error('Fetch parse error:', err);
      loadingCard.style.display = 'none';
      showError(err.message || '网络连接异常，请重试');
    }
  }

  function showError(msg) {
    errorMessage.textContent = msg;
    errorCard.style.display = 'block';
  }

  function hideAllCards() {
    loadingCard.style.display = 'none';
    errorCard.style.display = 'none';
    resultCard.style.display = 'none';
  }
});
