import sys
import os
import wave
import json
import subprocess
from vosk import Model, KaldiRecognizer
from openai import OpenAI

def format_timestamp(seconds):
    ms = int((seconds - int(seconds)) * 1000)
    s = int(seconds) % 60
    m = (int(seconds) // 60) % 60
    h = int(seconds) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def extract_audio(video_path, audio_path="temp_audio.wav"):
    print("========== 第一步：使用 FFmpeg 提取 16kHz 单声道 WAV 音频 ==========")
    if os.path.exists(audio_path):
        try: os.remove(audio_path)
        except Exception: pass
    cmd = ["ffmpeg", "-y", "-i", video_path, "-vn", "-ar", "16000", "-ac", "1", audio_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if not os.path.exists(audio_path):
        raise FileNotFoundError("音频提取失败")
    print(f"音频提取成功: {audio_path}")
    return audio_path

def transcribe_vosk(audio_path):
    print("\n========== 第二步：使用 Vosk 引擎离线识别语音 ==========")
    model_dir = "models/vosk-model-small-cn-0.22"
    if not os.path.exists(model_dir):
        print("未检测到本地 Vosk 模型，正在自动下载 vosk-model-small-cn-0.22...")
        import urllib.request
        import zipfile
        os.makedirs("models", exist_ok=True)
        zip_path = "models/vosk-model-small-cn-0.22.zip"
        url = "https://alphacephei.com/vosk/models/vosk-model-small-cn-0.22.zip"
        urllib.request.urlretrieve(url, zip_path)
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall("models")
        if os.path.exists(zip_path):
            os.remove(zip_path)

    print(f"已加载 Vosk 模型: {model_dir}")
    model = Model(model_dir)

    wf = wave.open(audio_path, "rb")
    if wf.getnchannels() != 1 or wf.getsampwidth() != 2 or wf.getcomptype() != "NONE":
        raise ValueError("音频格式不规范")

    rec = KaldiRecognizer(model, wf.getframerate())
    rec.SetWords(True)

    results = []
    while True:
        data = wf.readframes(4000)
        if len(data) == 0:
            break
        if rec.AcceptWaveform(data):
            res = json.loads(rec.Result())
            if res.get("text", "").strip():
                results.append(res)
    res_final = json.loads(rec.FinalResult())
    if res_final.get("text", "").strip():
        results.append(res_final)

    wf.close()
    
    # 整理出带有时间戳和段落文本的字幕块
    segments = []
    for item in results:
        text = item.get("text", "").replace(" ", "").strip()
        if not text:
            continue
        words = item.get("result", [])
        if words:
            start_t = words[0]["start"]
            end_t = words[-1]["end"]
        else:
            start_t = 0
            end_t = 0
        segments.append({
            "start": format_timestamp(start_t),
            "end": format_timestamp(end_t),
            "text": text
        })

    print(f"语音识别完成，共识别到 {len(segments)} 段内容。")
    return segments

def translate_and_punctuate_kimi(segments):
    print("\n========== 第三步：使用 Kimi AI 智能断句与标点整理 ==========")
    api_key = "sk-YhKMmbvw9CFxNMqaqNOSssfTPq7L9YUqt7BU1rjVLh0gRNeW"
    client = OpenAI(api_key=api_key, base_url="https://api.moonshot.cn/v1")

    raw_texts = [s['text'] for s in segments]
    prompt = "你是一个视频字幕专家。请为以下语音识别无标点文本加上标点符号，保持文本含义和行数完全一致，每行输出一句：\n" + "\n".join(raw_texts)

    try:
        completion = client.chat.completions.create(
            model="moonshot-v1-8k",
            messages=[
                {"role": "system", "content": "你是一个只输出带标点对应文本的系统。"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3
        )
        lines = [l.strip() for l in completion.choices[0].message.content.strip().split("\n") if l.strip()]
        if len(lines) == len(segments):
            for i in range(len(segments)):
                segments[i]['text'] = lines[i]
            print("Kimi 标点与语义整理完成。")
    except Exception as e:
        print(f"Kimi 标点优化失败: {e}，保留原始识别结果。")

    srt_path = "bilingual.srt"
    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, seg in enumerate(segments):
            f.write(f"{idx + 1}\n")
            f.write(f"{seg['start']} --> {seg['end']}\n")
            f.write(f"{seg['text']}\n\n")

    print(f"字幕文件保存至: {os.path.abspath(srt_path)}")
    return srt_path

def burn_subtitles(video_path, srt_path):
    print("\n========== 第四步：使用 FFmpeg 压制硬字幕 ==========")
    dir_name = os.path.dirname(video_path)
    base_name = os.path.splitext(os.path.basename(video_path))[0]
    output_path = os.path.join(dir_name, f"{base_name}_subtitled.mp4")

    escaped_srt_path = srt_path.replace("\\", "/").replace(":", "\\:")
    cmd = [
        "ffmpeg", "-y", "-i", video_path,
        "-vf", f"subtitles='{escaped_srt_path}':force_style='FontSize=18,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,MarginV=25'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        output_path
    ]

    print("正在进行 FFmpeg 渲染压制...")
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    if os.path.exists(output_path):
        print(f"\n🎉 [SUCCESS] 字幕视频制作完成！")
        print(f"成品输出位置: {output_path}")
        return output_path
    else:
        raise RuntimeError("FFmpeg 渲染压制失败")

if __name__ == "__main__":
    target_video = sys.argv[1] if len(sys.argv) > 1 else r"C:\Users\lufei\Desktop\847c72e8f0fed74cbc6512743b638df1.mp4"
    audio_path = extract_audio(target_video)
    segments = transcribe_vosk(audio_path)
    if segments:
        srt_path = translate_and_punctuate_kimi(segments)
        burn_subtitles(target_video, srt_path)
    else:
        print("未识别到声音。")
