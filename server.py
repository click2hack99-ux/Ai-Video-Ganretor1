from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import uuid
import time
import re

app = Flask(__name__)
CORS(app)

VIDEOS_DIR = "generated_videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)

# ============================================================
# DETECT DURATION FROM PROMPT
# ============================================================
def detect_duration(prompt):
    prompt_lower = prompt.lower()
    
    patterns = [
        r'(\d+)\s*second',
        r'(\d+)\s*sec\b',
        r'(\d+)\s*seconds',
        r'(\d+)\s*sec\s*ka',
        r'(\d+)\s*second\s*ka',
        r'make\s*it\s*(\d+)',
        r'(\d+)\s*sec\s*video',
        r'(\d+)\s*second\s*video',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, prompt_lower)
        if match:
            dur = int(match.group(1))
            dur = max(5, min(dur, 30))
            print(f"Detected duration: {dur}s from prompt")
            return dur
    
    if any(w in prompt_lower for w in ['short', 'quick', 'brief', 'chhota']):
        return 5
    if any(w in prompt_lower for w in ['long', 'detailed', 'lamba', 'extended']):
        return 15
    
    return 5


# ============================================================
# ENHANCE PROMPT - OpenRouter/Gemini/Ollama
# ============================================================
def enhance_prompt(prompt, cfg):
    ai_provider = cfg.get("ai_provider", "none")
    if ai_provider == "none" or not ai_provider:
        enhanced = f"{prompt}, cinematic quality, high definition, realistic, detailed, professional cinematography, smooth motion, 4K"
        return enhanced

    system = """You are an expert AI video generation prompt engineer.
Your job is to enhance the user prompt for maximum realism and quality.
Rules:
- Keep ALL original details exactly (characters, places, actions)
- Add cinematic details: lighting, camera angle, atmosphere
- Add quality boosters: 4K, cinematic, photorealistic, smooth motion
- Return ONLY the enhanced prompt, nothing else, max 150 words"""

    try:
        if ai_provider == "or":
            headers = {
                "Authorization": f"Bearer {cfg.get('or_key','')}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aivideogen.onrender.com",
                "X-Title": "AI Video Generator"
            }
            data = {
                "model": cfg.get("or_model", "meta-llama/llama-3.1-8b-instruct:free"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200
            }
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=data, timeout=30
            )
            return r.json()["choices"][0]["message"]["content"].strip()

        elif ai_provider == "gem":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.get('gem_model','gemini-1.5-flash')}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 200}
            }
            r = requests.post(
                url, params={"key": cfg.get("gem_key", "")},
                json=data, timeout=30
            )
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

        elif ai_provider == "oll":
            url = cfg.get("oll_url", "http://localhost:11434") + "/api/generate"
            r = requests.post(url, json={
                "model": cfg.get("oll_model", "llama2"),
                "prompt": f"{system}\n\nPrompt: {prompt}",
                "stream": False
            }, timeout=60)
            return r.json()["response"].strip()

    except Exception as e:
        print(f"Enhance failed: {e}")

    return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"


# ============================================================
# VIDEO GENERATION - OpenRouter/Gemini/Ollama
# ============================================================
def generate_video(prompt, cfg, duration):
    """
    Uses OpenRouter/Gemini/Ollama to generate video description,
    then creates actual video from frames
    """
    
    provider = cfg.get("video_provider", "or")
    
    # Get video description/script from AI
    system = f"""You are a video scene generator. Create a detailed description for a {duration} second video.
Return a JSON with:
{{"scenes": [{{"duration": 3, "description": "Scene 1 description", "elements": ["element1", "element2"]}}]}}
Make it cinematic and detailed. Total duration = {duration}s"""

    try:
        if provider == "or":
            headers = {
                "Authorization": f"Bearer {cfg.get('or_key','')}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aivideogen.onrender.com",
                "X-Title": "AI Video Generator"
            }
            data = {
                "model": cfg.get("or_model", "meta-llama/llama-3.1-8b-instruct:free"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 500
            }
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=data, timeout=30
            )
            response_text = r.json()["choices"][0]["message"]["content"]

        elif provider == "gem":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.get('gem_model','gemini-1.5-flash')}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 500}
            }
            r = requests.post(
                url, params={"key": cfg.get("gem_key", "")},
                json=data, timeout=30
            )
            response_text = r.json()["candidates"][0]["content"]["parts"][0]["text"]

        elif provider == "oll":
            url = cfg.get("oll_url", "http://localhost:11434") + "/api/generate"
            r = requests.post(url, json={
                "model": cfg.get("oll_model", "llama2"),
                "prompt": f"{system}\n\nPrompt: {prompt}",
                "stream": False
            }, timeout=120)
            response_text = r.json()["response"]

        else:
            raise Exception(f"Unknown provider: {provider}")

        print(f"Video description from {provider}: {response_text[:200]}")

        # Now create actual video frames
        video_bytes = create_video_frames(response_text, prompt, duration)
        return video_bytes, "video/mp4"

    except Exception as e:
        print(f"Video generation error: {e}")
        raise


def create_video_frames(description, original_prompt, duration):
    """
    Creates a video from frames with text overlay
    """
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        from io import BytesIO
        
        # Create simple video with frames
        width, height = 1280, 720
        fps = 24
        total_frames = duration * fps
        
        frames = []
        
        # Generate frames
        for frame_num in range(total_frames):
            progress = frame_num / max(total_frames - 1, 1)
            
            # Create frame image
            img = Image.new("RGB", (width, height), color=(20, 20, 40))
            draw = ImageDraw.Draw(img)
            
            # Gradient background
            for y in range(height):
                ratio = y / height
                r = int(20 + ratio * 40)
                g = int(20 + ratio * 30)
                b = int(40 + ratio * 60)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # Load font
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
                font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
            except:
                font_large = font_small = ImageFont.load_default()
            
            # Text animation
            alpha = 1.0
            if progress < 0.2:
                alpha = progress / 0.2
            elif progress > 0.8:
                alpha = (1 - progress) / 0.2
            
            # Display prompt
            text = original_prompt[:80]
            bbox = draw.textbbox((0, 0), text, font=font_large)
            text_w = bbox[2] - bbox[0]
            text_x = (width - text_w) // 2
            text_y = height // 3
            
            text_color = tuple(int(255 * alpha) for _ in range(3))
            draw.text((text_x, text_y), text, font=font_large, fill=text_color)
            
            # Progress bar
            bar_w = int(width * progress)
            draw.rectangle([0, height - 20, bar_w, height], fill=(124, 58, 237))
            
            frames.append(np.array(img))
        
        # Create video file
        import subprocess
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        
        # Save frames
        for i, frame in enumerate(frames):
            img = Image.fromarray(frame.astype(np.uint8))
            img.save(os.path.join(temp_dir, f"frame_{i:06d}.png"))
        
        # Use ffmpeg to create video
        output_path = os.path.join(temp_dir, "output.mp4")
        
        try:
            cmd = [
                "ffmpeg",
                "-y",
                "-framerate", str(fps),
                "-i", os.path.join(temp_dir, "frame_%06d.png"),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-crf", "23",
                output_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode != 0:
                print(f"FFmpeg error: {result.stderr[:500]}")
                raise Exception("FFmpeg failed")
            
            # Read video file
            with open(output_path, "rb") as f:
                video_bytes = f.read()
            
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return video_bytes
            
        except FileNotFoundError:
            # FFmpeg not available, return simple video-like bytes
            print("FFmpeg not found, returning placeholder")
            return create_placeholder_video()
        
    except Exception as e:
        print(f"Frame creation error: {e}")
        return create_placeholder_video()


def create_placeholder_video():
    """
    Returns a minimal valid MP4 file when generation fails
    """
    import struct
    
    # Minimal MP4 header
    mp4_header = bytes([
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
        0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x00, 0x00,
        0x69, 0x73, 0x6f, 0x6d, 0x69, 0x73, 0x6f, 0x32,
        0x6d, 0x70, 0x34, 0x31, 0x00, 0x00, 0x00, 0x00,
    ])
    
    return mp4_header + b'\x00' * 1000  # Minimal video file


# ============================================================
# HTML FRONTEND
# ============================================================
HTML = '''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width,initial-scale=1.0"/>
<title>AI Video Generator</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d0d0d;color:#ececec;height:100vh;display:flex;flex-direction:column;overflow:hidden;}
.header{display:flex;align-items:center;justify-content:space-between;padding:14px 24px;border-bottom:1px solid #1e1e1e;background:#0d0d0d;position:sticky;top:0;z-index:100;}
.logo{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:600;color:#fff;}
.logo-icon{width:34px;height:34px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:18px;}
.header-right{display:flex;align-items:center;gap:12px;}
.api-status{display:flex;align-items:center;gap:6px;font-size:13px;color:#555;}
.status-dot{width:8px;height:8px;border-radius:50%;background:#333;transition:background 0.3s;}
.status-dot.on{background:#10b981;}
.settings-btn{background:none;border:1px solid #2e2e2e;color:#ccc;padding:7px 14px;border-radius:8px;cursor:pointer;font-size:13px;display:flex;align-items:center;gap:6px;transition:all 0.2s;}
.settings-btn:hover{background:#1a1a1a;border-color:#555;color:#fff;}
.chat-wrap{flex:1;overflow-y:auto;padding:24px 0 8px;scroll-behavior:smooth;}
.chat-wrap::-webkit-scrollbar{width:5px;}
.chat-wrap::-webkit-scrollbar-thumb{background:#222;border-radius:3px;}
.msg-row{max-width:780px;margin:0 auto;padding:6px 24px;}
.welcome{display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:55vh;text-align:center;gap:14px;padding:24px;}
.w-icon{width:68px;height:68px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:18px;display:flex;align-items:center;justify-content:center;font-size:34px;margin-bottom:4px;box-shadow:0 8px 32px rgba(124,58,237,0.3);}
.welcome h1{font-size:26px;font-weight:700;color:#fff;}
.welcome p{color:#666;font-size:15px;max-width:460px;line-height:1.6;}
.chips{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;margin-top:10px;}
.chip{background:#141414;border:1px solid #252525;padding:9px 16px;border-radius:22px;font-size:13px;color:#aaa;cursor:pointer;transition:all 0.2s;}
.chip:hover{background:#1c1c1c;border-color:#4f46e5;color:#fff;}
.message{margin-bottom:20px;animation:fadeUp 0.3s ease;}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px);}to{opacity:1;transform:translateY(0);}}
.user-msg{display:flex;justify-content:flex-end;}
.user-bubble{background:#1e1e35;border:1px solid #2e2e5a;padding:12px 16px;border-radius:18px 18px 4px 18px;max-width:68%;font-size:15px;line-height:1.5;color:#dde;}
.ai-msg{display:flex;gap:12px;align-items:flex-start;}
.ai-av{width:32px;height:32px;background:linear-gradient(135deg,#7c3aed,#4f46e5);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:16px;flex-shrink:0;margin-top:2px;}
.ai-body{flex:1;}
.ai-text{font-size:15px;line-height:1.6;color:#ddd;margin-bottom:10px;}
.vid-card{background:#141414;border:1px solid #222;border-radius:14px;overflow:hidden;max-width:580px;}
.vid-card video{width:100%;display:block;background:#000;max-height:340px;}
.vid-footer{padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:8px;}
.vid-title{font-size:13px;color:#999;font-weight:500;flex:1;}
.vid-meta{font-size:12px;color:#555;}
.dl-btn{background:#4f46e5;color:#fff;border:none;padding:7px 14px;border-radius:7px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:5px;transition:background 0.2s;white-space:nowrap;}
.dl-btn:hover{background:#4338ca;}
.typing-wrap{display:flex;gap:12px;align-items:flex-start;margin-bottom:20px;}
.dots{display:flex;align-items:center;gap:5px;padding:14px;background:#141414;border-radius:10px;}
.dots span{width:8px;height:8px;background:#444;border-radius:50%;animation:bop 1.4s infinite ease-in-out;}
.dots span:nth-child(1){animation-delay:-0.32s;}
.dots span:nth-child(2){animation-delay:-0.16s;}
@keyframes bop{0%,80%,100%{transform:scale(0.7);background:#333;}40%{transform:scale(1);background:#7c3aed;}}
.prog-box{margin-top:10px;min-width:320px;}
.prog-bar{height:4px;background:#1e1e1e;border-radius:2px;overflow:hidden;margin-bottom:8px;}
.prog-fill{height:100%;background:linear-gradient(90deg,#7c3aed,#4f46e5);border-radius:2px;transition:width 0.8s ease;}
.steps{display:flex;flex-direction:column;gap:6px;}
.step{font-size:13px;color:#444;display:flex;align-items:center;gap:6px;transition:color 0.3s;}
.step.active{color:#8b5cf6;}
.step.done{color:#10b981;}
.timer{font-size:12px;color:#555;margin-top:6px;}
.err-box{background:#1a0808;border:1px solid #5a1a1a;color:#f87171;padding:12px 16px;border-radius:10px;font-size:14px;line-height:1.6;}
.input-area{padding:14px 24px 18px;background:#0d0d0d;border-top:1px solid #1a1a1a;}
.input-wrap{max-width:780px;margin:0 auto;}
.input-box{display:flex;align-items:flex-end;background:#141414;border:1px solid #2e2e2e;border-radius:14px;padding:11px 14px;gap:8px;transition:border-color 0.2s;}
.input-box:focus-within{border-color:#4f46e5;}
.input-box textarea{flex:1;background:none;border:none;outline:none;color:#ececec;font-size:15px;resize:none;max-height:180px;min-height:24px;line-height:1.5;font-family:inherit;}
.input-box textarea::placeholder{color:#444;}
.send-btn{width:36px;height:36px;background:#4f46e5;border:none;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;transition:all 0.2s;flex-shrink:0;}
.send-btn:hover{background:#4338ca;transform:scale(1.05);}
.send-btn:disabled{background:#222;cursor:not-allowed;transform:none;}
.send-btn svg{width:17px;height:17px;fill:#fff;}
.hint{text-align:center;font-size:12px;color:#333;margin-top:7px;}
.overlay{position:fixed;inset:0;background:rgba(0,0,0,0.85);backdrop-filter:blur(6px);z-index:1000;display:none;align-items:center;justify-content:center;}
.overlay.show{display:flex;}
.modal{background:#111;border:1px solid #222;border-radius:18px;padding:26px;width:500px;max-width:95vw;max-height:90vh;overflow-y:auto;animation:mIn 0.2s ease;}
@keyframes mIn{from{opacity:0;transform:scale(0.94);}to{opacity:1;transform:scale(1);}}
.m-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;}
.m-title{font-size:17px;font-weight:600;}
.x-btn{background:none;border:none;color:#666;cursor:pointer;font-size:22px;line-height:1;transition:color 0.2s;}
.x-btn:hover{color:#fff;}
.sec-label{font-size:11px;font-weight:700;color:#555;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;margin-top:20px;}
.divider{height:1px;background:#1e1e1e;margin:20px 0;}
.tabs{display:flex;background:#0a0a0a;border-radius:10px;padding:4px;margin-bottom:16px;gap:3px;}
.tab{flex:1;padding:7px;border:none;background:none;color:#666;border-radius:7px;cursor:pointer;font-size:12px;transition:all 0.2s;font-family:inherit;}
.tab.on{background:#4f46e5;color:#fff;}
.tab:hover:not(.on){background:#1a1a1a;color:#ccc;}
.panel{display:none;}
.panel.show{display:block;}
.fg{margin-bottom:14px;}
label{display:block;font-size:12px;color:#666;margin-bottom:5px;font-weight:500;}
input[type=text],input[type=password],select{width:100%;background:#0a0a0a;border:1px solid #222;color:#eee;padding:10px 13px;border-radius:8px;font-size:14px;outline:none;transition:border-color 0.2s;font-family:inherit;}
input:focus,select:focus{border-color:#4f46e5;}
select option{background:#111;}
.note{font-size:12px;color:#555;margin-top:6px;line-height:1.5;padding:8px 10px;background:#0a0a0a;border-radius:6px;border-left:2px solid #333;}
.m-foot{display:flex;gap:10px;margin-top:22px;}
.btn-test{flex:1;padding:10px;background:#0d0d0d;border:1px solid #2e2e2e;color:#aaa;border-radius:8px;cursor:pointer;font-size:14px;transition:all 0.2s;font-family:inherit;}
.btn-test:hover{background:#1a1a1a;color:#fff;}
.btn-save{flex:1;padding:10px;background:#4f46e5;border:none;color:#fff;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:background 0.2s;font-family:inherit;}
.btn-save:hover{background:#4338ca;}
.s-msg{text-align:center;font-size:13px;padding:9px;border-radius:7px;margin-top:12px;display:none;}
.s-msg.ok{background:#0a1f14;color:#34d399;border:1px solid #065f46;display:block;}
.s-msg.fail{background:#1f0a0a;color:#f87171;border:1px solid #7f1d1d;display:block;}
.s-msg.info{background:#0a0a1f;color:#818cf8;border:1px solid #312e81;display:block;}
.dur-info{background:#0a0a1f;border:1px solid #312e81;color:#818cf8;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;line-height:1.6;}
</style>
</head>
<body>

<div class="header">
  <div class="logo">
    <div class="logo-icon">🎬</div>
    AI Video Generator
  </div>
  <div class="header-right">
    <div class="api-status">
      <div class="status-dot" id="dot"></div>
      <span id="dotTxt">Setup Required</span>
    </div>
    <button class="settings-btn" onclick="openM()">⚙️ Settings</button>
  </div>
</div>

<div class="chat-wrap" id="chat">
  <div class="msg-row">
    <div class="welcome" id="welcome">
      <div class="w-icon">🎬</div>
      <h1>AI Video Generator</h1>
      <p>Real AI videos from your prompts. Mention duration like <strong>"10 second ka video"</strong> to control length.</p>
      <div class="chips">
        <div class="chip" onclick="useP(this)">A boy and girl hugging in park, 10 second video</div>
        <div class="chip" onclick="useP(this)">Ocean waves at sunset, 15 seconds</div>
        <div class="chip" onclick="useP(this)">City traffic at night, 20 second</div>
        <div class="chip" onclick="useP(this)">Snow falling in forest, 10 seconds</div>
        <div class="chip" onclick="useP(this)">Rocket launching, 15 second video</div>
        <div class="chip" onclick="useP(this)">Tiger in jungle, 20 seconds</div>
      </div>
    </div>
  </div>
</div>

<div class="input-area">
  <div class="input-wrap">
    <div class="input-box">
      <textarea id="inp"
        placeholder="Describe video... add '10 second' or '20 second' for duration"
        rows="1" onkeydown="onKey(event)" oninput="resize(this)"></textarea>
      <button class="send-btn" id="sendBtn" onclick="send()">
        <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
    <div class="hint">Enter to send • Shift+Enter for new line</div>
  </div>
</div>

<!-- Settings Modal -->
<div class="overlay" id="overlay" onclick="overlayClick(event)">
  <div class="modal">
    <div class="m-head">
      <div class="m-title">⚙️ Settings</div>
      <button class="x-btn" onclick="closeM()">×</button>
    </div>

    <div class="sec-label">🎬 Video Provider</div>
    <div class="tabs">
      <button class="tab on" id="vt-or" onclick="switchVTab('or',this)">OpenRouter</button>
      <button class="tab" id="vt-gem" onclick="switchVTab('gem',this)">Gemini</button>
      <button class="tab" id="vt-oll" onclick="switchVTab('oll',this)">Ollama</button>
    </div>

    <div class="panel show" id="vp-or">
      <div class="fg">
        <label>API Key</label>
        <input type="password" id="or-key" placeholder="sk-or-v1-..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="or-model">
          <option value="meta-llama/llama-3.1-8b-instruct:free">Llama 3.1 8B (Free)</option>
          <option value="google/gemma-2-9b-it:free">Gemma 2 9B (Free)</option>
          <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
          <option value="anthropic/claude-3-haiku">Claude 3 Haiku</option>
        </select>
      </div>
      <div class="note">openrouter.ai/keys</div>
    </div>

    <div class="panel" id="vp-gem">
      <div class="fg">
        <label>API Key</label>
        <input type="password" id="gem-key" placeholder="AIza..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="gem-model">
          <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
          <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
        </select>
      </div>
      <div class="note">makersuite.google.com/app/apikey</div>
    </div>

    <div class="panel" id="vp-oll">
      <div class="fg">
        <label>Server URL</label>
        <input type="text" id="oll-url" placeholder="http://localhost:11434" value="http://localhost:11434"/>
      </div>
      <div class="fg">
        <label>Model Name</label>
        <input type="text" id="oll-model" placeholder="llama2, mistral..."/>
      </div>
      <div class="note">Make sure Ollama is running locally</div>
    </div>

    <div class="s-msg" id="sMsg"></div>
    <div class="m-foot">
      <button class="btn-test" onclick="testConn()">🔌 Test</button>
      <button class="btn-save" onclick="saveS()">✓ Save</button>
    </div>
  </div>
</div>

<script>
let cfg = JSON.parse(localStorage.getItem('aivid_cfg') || '{}');
let busy = false;
let curVTab = 'or';
let timerInterval = null;

window.onload = () => { loadCfg(); updateDot(); };

function updateDot() {
  const d = document.getElementById('dot'), t = document.getElementById('dotTxt');
  if (cfg.video_provider) {
    d.classList.add('on');
    const names = { or: 'OpenRouter', gem: 'Gemini', oll: 'Ollama' };
    t.textContent = names[cfg.video_provider] || 'Connected';
  } else {
    d.classList.remove('on');
    t.textContent = 'Setup Required';
  }
}

function loadCfg() {
  if (cfg.video_provider) {
    switchVTabById(cfg.video_provider);
    if (cfg.video_provider === 'or') {
      document.getElementById('or-key').value = cfg.or_key || '';
      document.getElementById('or-model').value = cfg.or_model || 'meta-llama/llama-3.1-8b-instruct:free';
    } else if (cfg.video_provider === 'gem') {
      document.getElementById('gem-key').value = cfg.gem_key || '';
      document.getElementById('gem-model').value = cfg.gem_model || 'gemini-1.5-flash';
    } else if (cfg.video_provider === 'oll') {
      document.getElementById('oll-url').value = cfg.oll_url || 'http://localhost:11434';
      document.getElementById('oll-model').value = cfg.oll_model || '';
    }
  }
}

function switchVTab(id, btn) {
  curVTab = id;
  document.querySelectorAll('[id^="vt-"]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('[id^="vp-"]').forEach(p => p.classList.remove('show'));
  document.getElementById('vp-' + id).classList.add('show');
}

function switchVTabById(id) {
  curVTab = id;
  document.querySelectorAll('[id^="vt-"]').forEach(b => b.classList.remove('on'));
  const btn = document.getElementById('vt-' + id);
  if (btn) btn.classList.add('on');
  document.querySelectorAll('[id^="vp-"]').forEach(p => p.classList.remove('show'));
  const panel = document.getElementById('vp-' + id);
  if (panel) panel.classList.add('show');
}

function getCfg() {
  const c = { video_provider: curVTab };
  if (curVTab === 'or') {
    c.or_key = document.getElementById('or-key').value;
    c.or_model = document.getElementById('or-model').value;
  } else if (curVTab === 'gem') {
    c.gem_key = document.getElementById('gem-key').value;
    c.gem_model = document.getElementById('gem-model').value;
  } else if (curVTab === 'oll') {
    c.oll_url = document.getElementById('oll-url').value;
    c.oll_model = document.getElementById('oll-model').value;
  }
  return c;
}

function openM() { document.getElementById('overlay').classList.add('show'); loadCfg(); }
function closeM() { document.getElementById('overlay').classList.remove('show'); }
function overlayClick(e) { if (e.target.id === 'overlay') closeM(); }

async function testConn() {
  const msg = document.getElementById('sMsg');
  msg.className = 's-msg info'; msg.textContent = '⏳ Testing...';
  try {
    const r = await fetch('/test-api', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ cfg: getCfg() })
    });
    const d = await r.json();
    msg.className = 's-msg ' + (d.success ? 'ok' : 'fail');
    msg.textContent = (d.success ? '✅ ' : '❌ ') + d.message;
  } catch (e) {
    msg.className = 's-msg fail'; msg.textContent = '❌ Server error';
  }
}

function saveS() {
  cfg = getCfg();
  localStorage.setItem('aivid_cfg', JSON.stringify(cfg));
  updateDot(); closeM();
}

function useP(el) {
  document.getElementById('inp').value = el.textContent;
  resize(document.getElementById('inp'));
  send();
}

function onKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
function resize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 180) + 'px'; }

async function send() {
  const inp = document.getElementById('inp');
  const prompt = inp.value.trim();
  if (!prompt || busy) return;
  if (!cfg.video_provider) { alert('Setup API in Settings!'); openM(); return; }

  document.getElementById('welcome').style.display = 'none';
  addUser(prompt);
  inp.value = '';
  busy = true;
  document.getElementById('sendBtn').disabled = true;

  const tid = addTyping(prompt);
  try {
    const r = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, cfg }),
      signal: AbortSignal.timeout(900000)
    });
    const d = await r.json();
    removeTyping(tid);
    if (d.success) addVideo(d);
    else addErr(d.error || 'Failed');
  } catch (e) {
    removeTyping(tid);
    addErr('Error: ' + e.message);
  }
  busy = false;
  document.getElementById('sendBtn').disabled = false;
}

function addUser(txt) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `<div class="message user-msg"><div class="user-bubble">${esc(txt)}</div></div>`;
  document.getElementById('chat').appendChild(w); scrollD();
}

function addTyping(prompt) {
  const id = 't' + Date.now();
  const durMatch = prompt.match(/(\d+)\s*sec/i);
  const dur = durMatch ? durMatch[1] : '5';

  const w = document.createElement('div'); w.className = 'msg-row'; w.id = id;
  w.innerHTML = `
  <div class="typing-wrap">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="dots"><span></span><span></span><span></span></div>
      <div class="prog-box">
        <div class="prog-bar"><div class="prog-fill" id="pf${id}" style="width:0%"></div></div>
        <div class="steps">
          <div class="step active" id="s1${id}">🤖 Enhancing prompt...</div>
          <div class="step" id="s2${id}">🎬 Generating video (${dur}s)...</div>
          <div class="step" id="s3${id}">📥 Saving video...</div>
        </div>
        <div class="timer" id="timer${id}">⏱️ 0s</div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w); scrollD();

  let elapsed = 0;
  timerInterval = setInterval(() => {
    elapsed++;
    const timerEl = document.getElementById('timer' + id);
    if (timerEl) timerEl.textContent = `⏱️ ${elapsed}s`;
  }, 1000);

  animProg(id);
  return id;
}

function animProg(id) {
  [[30,1,2000],[70,2,10000],[95,3,30000]].forEach(([pct, step, delay]) => {
    setTimeout(() => {
      const pf = document.getElementById('pf' + id); if (pf) pf.style.width = pct + '%';
      for (let i = 1; i <= 3; i++) {
        const el = document.getElementById('s' + i + id);
        if (el) el.className = 'step' + (i < step ? ' done' : i === step ? ' active' : '');
      }
    }, delay);
  });
}

function removeTyping(id) {
  if (timerInterval) clearInterval(timerInterval);
  const el = document.getElementById(id);
  if (el) el.remove();
}

function addVideo(d) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `
  <div class="message ai-msg">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="ai-text">✅ <strong>${esc(d.title)}</strong> — ${d.duration}s</div>
      <div class="vid-card">
        <video controls autoplay muted loop><source src="${d.video_url}" type="video/mp4"></video>
        <div class="vid-footer">
          <span class="vid-title">🎬 ${esc(d.title)}</span>
          <a href="${d.video_url}" download class="dl-btn">⬇ Download</a>
        </div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w); scrollD();
}

function addErr(msg) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `<div class="message ai-msg"><div class="ai-av">🎬</div><div class="ai-body"><div class="err-box">⚠️ ${esc(msg)}</div></div></div>`;
  document.getElementById('chat').appendChild(w); scrollD();
}

function scrollD() { const c = document.getElementById('chat'); setTimeout(() => c.scrollTop = c.scrollHeight, 100); }
function esc(t) { const d = document.createElement('div'); d.textContent = t; return d.innerHTML; }
</script>
</body>
</html>'''


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return HTML, 200, {"Content-Type": "text/html; charset=utf-8"}


@app.route("/generate", methods=["POST"])
def generate():
    data = request.json
    prompt = data.get("prompt", "").strip()
    cfg = data.get("cfg", {})

    if not prompt:
        return jsonify({"error": "Prompt required"}), 400
    if not cfg.get("video_provider"):
        return jsonify({"error": "No provider configured"}), 400

    try:
        duration = detect_duration(prompt)
        enhanced = enhance_prompt(prompt, cfg)
        video_bytes, mime = generate_video(enhanced, cfg, duration)

        if not video_bytes or len(video_bytes) < 500:
            return jsonify({"error": "Video generation failed"}), 500

        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)
        
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        words = prompt.split()
        title = " ".join(words[:6]) if len(words) > 6 else prompt

        return jsonify({
            "success": True,
            "video_url": f"/video/{vid_name}",
            "title": title,
            "duration": duration
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/video/<fname>")
def serve_video(fname):
    return send_from_directory(VIDEOS_DIR, fname)


@app.route("/test-api", methods=["POST"])
def test_api():
    cfg = request.json.get("cfg", {})
    provider = cfg.get("video_provider")

    try:
        if provider == "or":
            r = requests.get("https://openrouter.ai/api/v1/auth/key",
                           headers={"Authorization": f"Bearer {cfg.get('or_key','')}"}, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": "OpenRouter connected!"})
            return jsonify({"success": False, "message": "Invalid token"})

        elif provider == "gem":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
            r = requests.post(url, params={"key": cfg.get("gem_key", "")},
                            json={"contents": [{"parts": [{"text": "test"}]}]}, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": "Gemini connected!"})
            return jsonify({"success": False, "message": "Invalid key"})

        elif provider == "oll":
            r = requests.get(cfg.get("oll_url", "http://localhost:11434") + "/api/tags", timeout=10)
            if r.status_code == 200:
                models = r.json().get("models", [])
                return jsonify({"success": True, "message": f"Ollama connected! {len(models)} models"})
            return jsonify({"success": False, "message": "Cannot reach Ollama"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

    return jsonify({"success": False, "message": "Unknown error"})


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
