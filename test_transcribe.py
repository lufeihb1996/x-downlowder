import sys
import os
import yt_dlp
from faster_whisper import WhisperModel

def format_timestamp(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def download_audio(url):
    print("========== 第一步：下载视频并提取音频 ==========")
    output_filename = "temp_audio"
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_filename,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
    
    audio_path = f"{output_filename}.mp3"
    if os.path.exists(audio_path):
        print(f"音频提取成功: {audio_path}")
        return audio_path
    else:
        raise FileNotFoundError("音频文件提取失败")

def transcribe(audio_path):
    print("\n========== 第二步：载入 Whisper 模型并识别字幕 ==========")
    # 第一次运行会从 HuggingFace 自动下载模型，因为使用 VPN 所以能正常下载。
    # 我们使用 base 模型，体积约 140MB，在 CPU 上运行极快且中英文识别率非常好。
    model_size = "base"
    print(f"正在加载 Whisper '{model_size}' 模型 (首次加载会自动下载)...")
    
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    
    print("开始语音识别，请稍候...")
    segments, info = model.transcribe(audio_path, beam_size=5)
    
    print(f"\n检测到音频主语言: '{info.language}' (概率: {info.language_probability:.2f})")
    print("-" * 50)
    
    srt_path = "video_transcription.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for index, segment in enumerate(segments, 1):
            start = format_timestamp(segment.start)
            end = format_timestamp(segment.end)
            text = segment.text.strip()
            
            # 实时输出到终端
            print(f"[{start} --> {end}] {text}")
            
            # 写入 SRT 字幕格式
            f.write(f"{index}\n{start} --> {end}\n{text}\n\n")
            
    print("-" * 50)
    print(f"[Success] 语音识别完成！字幕文件已成功保存为: {os.path.abspath(srt_path)}")
    return srt_path

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用说明: python test_transcribe.py <推特链接或本地音频文件路径>")
        sys.exit(1)
        
    input_source = sys.argv[1]
    
    temp_files = []
    try:
        # 判断是网址还是本地文件
        if input_source.startswith("http://") or input_source.startswith("https://"):
            audio_file = download_audio(input_source)
            temp_files.append(audio_file)
        else:
            audio_file = input_source
            if not os.path.exists(audio_file):
                print(f"错误: 找不到本地文件 {audio_file}")
                sys.exit(1)
        
        # 运行语音识别
        transcribe(audio_file)
        
    except Exception as e:
        print(f"\n[Error] 发生错误: {str(e)}")
        
    finally:
        # 清理临时下载的音频文件
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"清理临时音频缓存: {temp_file}")
                except Exception as ex:
                    print(f"无法清理临时文件: {ex}")
