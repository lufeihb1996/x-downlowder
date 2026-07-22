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

  // Utility to format bytes
  function formatBytes(bytes) {
    if (!bytes || bytes <= 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

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
      const res = await fetch(`/api/parse?url=${encodeURIComponent(rawUrl)}`);
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

        const proxyDownloadUrl = `/api/proxy?url=${encodeURIComponent(f.url)}`;
        const filename = `x-video-${f.height || 'hd'}p.mp4`;

        item.innerHTML = `
          <div class="res-main-row">
            <div class="res-info">
              <span class="badge ${badgeClass}">${badgeText}</span>
              <span class="res-dimensions">${f.resolution}</span>
            </div>
            <button type="button" class="btn-download" data-url="${proxyDownloadUrl}" data-filename="${filename}">
              <i class="fa-solid fa-arrow-down-to-bracket"></i>
              <span>下载</span>
            </button>
          </div>
          <div class="download-progress-box" style="display: none;">
            <div class="progress-track">
              <div class="progress-fill" style="width: 0%;"></div>
            </div>
            <div class="progress-meta">
              <span class="progress-status"><i class="fa-solid fa-cloud-arrow-down"></i> 准备下载...</span>
              <span class="progress-metrics">0 B / 0 B</span>
              <span class="progress-percent">0%</span>
            </div>
          </div>
        `;

        const btnDownload = item.querySelector('.btn-download');
        const progressBox = item.querySelector('.download-progress-box');
        const progressFill = item.querySelector('.progress-fill');
        const progressStatus = item.querySelector('.progress-status');
        const progressMetrics = item.querySelector('.progress-metrics');
        const progressPercent = item.querySelector('.progress-percent');
        const btnText = btnDownload.querySelector('span');
        const btnIcon = btnDownload.querySelector('i');

        btnDownload.addEventListener('click', async () => {
          if (btnDownload.classList.contains('loading')) return;

          // UI state: Start downloading
          btnDownload.classList.add('loading');
          btnDownload.disabled = true;
          btnIcon.className = 'fa-solid fa-spinner fa-spin';
          btnText.textContent = '下载中';

          progressBox.style.display = 'flex';
          progressFill.className = 'progress-fill';
          progressFill.style.width = '0%';
          progressStatus.innerHTML = '<i class="fa-solid fa-cloud-arrow-down"></i> 正在请求视频流...';
          progressStatus.classList.remove('success');
          progressMetrics.textContent = '0 B / 0 B';
          progressPercent.textContent = '0%';

          try {
            const response = await fetch(proxyDownloadUrl);
            if (!response.ok) {
              throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const contentLength = response.headers.get('content-length');
            const totalBytes = contentLength ? parseInt(contentLength, 10) : 0;

            const reader = response.body.getReader();
            const chunks = [];
            let loadedBytes = 0;
            let lastTime = performance.now();
            let lastLoaded = 0;
            let speedText = '0 MB/s';

            progressStatus.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> 正在下载视频流...';

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;

              chunks.push(value);
              loadedBytes += value.length;

              const now = performance.now();
              const timeDiff = (now - lastTime) / 1000;
              if (timeDiff >= 0.3) {
                const bytesDiff = loadedBytes - lastLoaded;
                const speed = bytesDiff / timeDiff;
                speedText = `${formatBytes(speed)}/s`;
                lastTime = now;
                lastLoaded = loadedBytes;
              }

              if (totalBytes > 0) {
                const percent = Math.min(100, Math.round((loadedBytes / totalBytes) * 100));
                progressFill.style.width = `${percent}%`;
                progressPercent.textContent = `${percent}%`;
                progressMetrics.textContent = `${formatBytes(loadedBytes)} / ${formatBytes(totalBytes)} (${speedText})`;
                btnText.textContent = `${percent}%`;
              } else {
                progressFill.style.width = '100%';
                progressPercent.textContent = '--%';
                progressMetrics.textContent = `${formatBytes(loadedBytes)} (${speedText})`;
              }
            }

            // Complete!
            progressFill.style.width = '100%';
            progressFill.classList.add('completed');
            progressPercent.textContent = '100%';
            progressMetrics.textContent = `${formatBytes(loadedBytes)} · 下载完成`;
            progressStatus.innerHTML = '<i class="fa-solid fa-circle-check"></i> 已保存至浏览器下载区';
            progressStatus.classList.add('success');

            btnIcon.className = 'fa-solid fa-check';
            btnText.textContent = '已完成';
            btnDownload.classList.remove('loading');
            btnDownload.classList.add('success');

            // Trigger file save directly in page without navigating away
            const blob = new Blob(chunks, { type: 'application/octet-stream' });
            const blobUrl = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = blobUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(() => URL.revokeObjectURL(blobUrl), 10000);

            // Reset button state after 3 seconds
            setTimeout(() => {
              btnDownload.disabled = false;
              btnDownload.classList.remove('success');
              btnIcon.className = 'fa-solid fa-arrow-down-to-bracket';
              btnText.textContent = '再次下载';
            }, 3000);

          } catch (err) {
            console.error('Download progress error:', err);
            progressStatus.innerHTML = '<i class="fa-solid fa-triangle-exclamation"></i> 下载请求异常，使用普通通道';
            progressMetrics.textContent = '使用浏览器默认通道下载...';
            
            // Fallback: direct in-page download without opening a new tab
            const a = document.createElement('a');
            a.href = proxyDownloadUrl;
            a.download = filename;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);

            setTimeout(() => {
              btnDownload.disabled = false;
              btnDownload.classList.remove('loading');
              btnIcon.className = 'fa-solid fa-arrow-down-to-bracket';
              btnText.textContent = '下载';
            }, 2000);
          }
        });

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
