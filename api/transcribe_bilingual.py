import sys
import os
import yt_dlp
import subprocess
from faster_whisper import WhisperModel

# Optional local translation imports
try:
    import argostranslate.package
    import argostranslate.translate
    HAS_ARGOS = True
except ImportError:
    HAS_ARGOS = False

# Optional Kimi translation imports
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

def format_timestamp(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def download_video_and_extract_audio(url):
    print("========== 第一步：下载视频并提取音频 ==========")
    video_filename = "temp_video.mp4"
    audio_filename = "temp_audio.mp3"
    
    if os.path.exists(video_filename):
        try:
            os.remove(video_filename)
        except Exception:
            pass
            
    # 1. 下载视频画面与音频的最佳合并格式
    ydl_opts = {
        'format': 'best',
        'outtmpl': 'temp_video.mp4',
        'quiet': True
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])
        
    if not os.path.exists(video_filename):
        raise FileNotFoundError("视频文件下载失败")
        
    # 2. 使用 FFmpeg 快速提取 16kHz 单声道音频用于识别
    if os.path.exists(audio_filename):
        try:
            os.remove(audio_filename)
        except Exception:
            pass
            
    cmd = ["ffmpeg", "-y", "-i", video_filename, "-vn", "-ar", "16000", "-ac", "1", "-c:a", "libmp3lame", audio_filename]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(audio_filename):
        print(f"视频与音频提取成功: {video_filename}, {audio_filename}")
        return video_filename, audio_filename
    else:
        raise FileNotFoundError("音频提取失败")

def transcribe(audio_path):
    print("\n========== 第二步：载入 Whisper 模型并识别字幕 ==========")
    model_size = "base"
    print(f"正在加载 Whisper '{model_size}' 模型...")
    
    results = []
    detected_lang = 'en'
    
    # 优先尝试 PyTorch 原生 Whisper，避开 Windows 上 ctranslate2 的 DLL 冲突
    try:
        import whisper
        print("使用 PyTorch Whisper 引擎识别...")
        model = whisper.load_model(model_size)
        res = model.transcribe(audio_path)
        detected_lang = res.get('language', 'en')
        print(f"检测到音频主语言: '{detected_lang}'")
        for seg in res.get('segments', []):
            results.append({
                'start': format_timestamp(seg['start']),
                'end': format_timestamp(seg['end']),
                'text': seg['text'].strip()
            })
    except Exception as e1:
        print(f"PyTorch Whisper 未就绪 ({e1})，尝试切换至 faster-whisper...")
        from faster_whisper import WhisperModel
        model = WhisperModel(model_size, device="cpu", compute_type="int8", cpu_threads=1)
        segments, info = model.transcribe(audio_path, beam_size=5, vad_filter=True)
        detected_lang = info.language
        print(f"检测到音频主语言: '{detected_lang}' (概率: {info.language_probability:.2f})")
        for segment in segments:
            results.append({
                'start': format_timestamp(segment.start),
                'end': format_timestamp(segment.end),
                'text': segment.text.strip()
            })

    print(f"听写完成，共识别到 {len(results)} 句字幕。")
    return results, detected_lang

def translate_local_argos(text, from_lang, to_lang="zh"):
    if from_lang == to_lang:
        return text
    try:
        if from_lang == 'ja' and to_lang == 'zh':
            # Pivot translation ja -> en -> zh
            en_text = argostranslate.translate.translate(text, "ja", "en")
            return argostranslate.translate.translate(en_text, "en", "zh")
        else:
            return argostranslate.translate.translate(text, from_lang, to_lang)
    except Exception as e:
        print(f"本地 Argos 翻译单行失败: {str(e)}")
        return ""

def translate_cloud_kimi(text_list, from_lang):
    api_key = os.environ.get("MOONSHOT_API_KEY")
    if not api_key:
        dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "x-automation", ".env")
        if os.path.exists(dotenv_path):
            with open(dotenv_path, "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("MOONSHOT_API_KEY="):
                        api_key = line.split("=")[1].strip().strip('"').strip("'")
                        break
                        
    if not api_key:
        print("未检测到 MOONSHOT_API_KEY，跳过云端 Kimi 翻译。")
        return None

    print(f"正在使用云端 Kimi 翻译 {len(text_list)} 句字幕...")
    try:
        client = OpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")
        
        prompt = f"你是一个精通{from_lang}和中文的专业视频翻译助手。请将以下{from_lang}文本翻译成中文。直接输出翻译结果，保持行数和对应关系完全一致，每行只输出一句中文翻译，不要输出任何额外解释或时间戳：\n"
        for text in text_list:
            prompt += f"{text}\n"
            
        completion = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": "你是一个只输出翻译结果的工具，不要和用户闲聊。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
        )
        
        translated_raw = completion.choices[0].message.content.strip()
        translated_lines = [line.strip() for line in translated_raw.split("\n") if line.strip()]
        
        if len(translated_lines) >= len(text_list):
            return translated_lines[:len(text_list)]
        else:
            print(f"警告：Kimi 返回翻译行数 ({len(translated_lines)}) 少于输入行数 ({len(text_list)})，将降级处理。")
            return None
    except Exception as e:
        print(f"Kimi 翻译出错: {str(e)}")
        return None

def process_subtitles(segments, detected_lang):
    print("\n========== 第三步：翻译并合并生成双语字幕 ==========")
    texts = [seg['text'] for seg in segments]
    
    translated_texts = None
    if HAS_OPENAI:
        translated_texts = translate_cloud_kimi(texts, detected_lang)
        
    if not translated_texts:
        if HAS_ARGOS:
            print("正在使用本地 Argos 翻译模型逐句翻译...")
            try:
                argostranslate.package.update_package_index()
                available = argostranslate.package.get_available_packages()
                installed = argostranslate.package.get_installed_packages()
                for f, t in [('ja', 'en'), ('en', 'zh')]:
                    if not any(p.from_code == f and p.to_code == t for p in installed):
                        pkg = next(filter(lambda x: x.from_code == f and x.to_code == t, available))
                        argostranslate.package.install_from_path(pkg.download())
            except Exception as ex:
                print(f"本地翻译模型初始化失败: {ex}")
                
            translated_texts = []
            for t in texts:
                trans = translate_local_argos(t, detected_lang)
                translated_texts.append(trans)
        else:
            print("警告：未安装 argostranslate，且云端翻译不可用，将只输出原文字幕。")
            translated_texts = [""] * len(texts)
            
    srt_path = "bilingual.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments):
            f.write(f"{idx + 1}\n")
            f.write(f"{seg['start']} --> {seg['end']}\n")
            f.write(f"{seg['text']}\n")
            
            zh_trans = translated_texts[idx]
            if zh_trans and zh_trans != seg['text']:
                f.write(f"{zh_trans}\n")
            f.write("\n")
            
    print(f"[Success] 双语对照字幕已成功生成并保存为: {os.path.abspath(srt_path)}")
    return srt_path

def burn_subtitles(video_path, srt_path):
    print("\n========== 第四步：使用 FFmpeg 压制硬字幕 ==========")
    output_path = "output_subtitled.mp4"
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass
            
    # Windows 路径转义，防止 FFmpeg 的 subtitles 滤镜因为反斜杠报错
    escaped_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
    
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles='{escaped_srt_path}':force_style='FontSize=16,PrimaryColour=&HFFFFFF,OutlineColour=&H000000'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        output_path
    ]
    
    print("正在进行视频渲染压制，请稍候...")
    # 打印完整命令供调试
    # print(f"执行命令: {' '.join(cmd)}")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    if os.path.exists(output_path):
        print(f"[Success] 视频双语字幕压制成功！成品已保存为: {os.path.abspath(output_path)}")
        return output_path
    else:
        raise RuntimeError("FFmpeg 压制硬字幕失败")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("使用说明: python transcribe_bilingual.py <推特视频网址或本地音频文件路径>")
        sys.exit(1)
        
    input_source = sys.argv[1]
    
    temp_files = []
    try:
        # 1. 下载视频或处理本地视频/音频
        if input_source.startswith("http://") or input_source.startswith("https://"):
            video_file, audio_file = download_video_and_extract_audio(input_source)
            temp_files.append(video_file)
            temp_files.append(audio_file)
        else:
            if not os.path.exists(input_source):
                print(f"错误: 本地文件不存在 {input_source}")
                sys.exit(1)
            
            ext = os.path.splitext(input_source)[1].lower()
            if ext in ['.mp4', '.mkv', '.mov', '.avi', '.webm', '.flv']:
                video_file = input_source
                audio_file = "temp_audio.wav"
                print(f"========== 第一步：从本地视频提取 16kHz 音频 ==========")
                print(f"输入视频: {video_file}")
                subprocess.run(["ffmpeg", "-y", "-i", video_file, "-vn", "-ar", "16000", "-ac", "1", audio_file],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                temp_files.append(audio_file)
            else:
                audio_file = input_source
                video_file = None
                
        # 2. Whisper 语音识别
        segments, detected_lang = transcribe(audio_file)
        
        if not segments:
            print("未能在音频中听写出任何文字，无法生成字幕。")
            sys.exit(0)
            
        # 3. 翻译并生成双语对照字幕文件
        srt_file = process_subtitles(segments, detected_lang)
        
        # 4. 如果有原视频，则进行硬字幕压制
        if video_file and os.path.exists(video_file):
            burn_subtitles(video_file, srt_file)
            
    except Exception as e:
        print(f"\n[Error] 运行失败: {str(e)}")
    finally:
        # 清理临时文件
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                    print(f"清理临时文件: {temp_file}")
                except Exception as ex:
                    print(f"无法清理临时文件: {ex}")
