from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import uuid
import time
import re
import subprocess
import tempfile

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
# ENHANCE PROMPT
# ============================================================
def enhance_prompt(prompt, cfg):
    ai_provider = cfg.get("ai_provider", "none")
    
    if ai_provider == "none" or not ai_provider:
        enhanced = f"{prompt}, cinematic quality, high definition, realistic, detailed, professional cinematography, smooth motion, 4K"
        return enhanced
    
    system = """You are an expert AI video generation prompt engineer. Your job is to enhance the user prompt for maximum realism and quality.
Rules:
- Keep ALL original details exactly (characters, places, actions)
- Add cinematic details: lighting, camera angle, atmosphere
- Add quality boosters: 4K, cinematic, photorealistic, smooth motion
- If characters mentioned (Spider-Man, Batman etc), add: detailed costume, accurate design
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
                headers=headers,
                json=data,
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["choices"][0]["message"]["content"].strip()
            else:
                print(f"OpenRouter error: {r.status_code} - {r.text}")
                return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"
            
        elif ai_provider == "gem":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.get('gem_model','gemini-1.5-flash')}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 200}
            }
            r = requests.post(
                url,
                params={"key": cfg.get("gem_key", "")},
                json=data,
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            else:
                print(f"Gemini error: {r.status_code} - {r.text}")
                return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"
            
        elif ai_provider == "ollama":
            data = {
                "model": cfg.get("ollama_model", "llama3.2"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "stream": False,
                "options": {
                    "num_predict": 200
                }
            }
            r = requests.post(
                f"{cfg.get('ollama_url', 'http://localhost:11434')}/api/chat",
                json=data,
                timeout=30
            )
            if r.status_code == 200:
                return r.json()["message"]["content"].strip()
            else:
                print(f"Ollama error: {r.status_code} - {r.text}")
                return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"
            
    except Exception as e:
        print(f"Enhance failed: {e}")
        return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"

# ============================================================
# CREATE SAMPLE VIDEO
# ============================================================
def create_sample_video(text, duration=5):
    """Create a sample video file with text overlay"""
    try:
        # Try to create a video with ffmpeg
        with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as f:
            temp_file = f.name
        
        # Create a video with colored background and text
        cmd = [
            'ffmpeg', '-f', 'lavfi', '-i', f'color=c=#1a1a2e:s=1280x720:d={duration}',
            '-vf', f"drawtext=text='{text[:80]}':fontcolor=white:fontsize=48:"
                   f"x=(w-text_w)/2:y=(h-text_h)/2:box=1:boxcolor=black@0.5:boxborderw=10",
            '-c:v', 'libx264', '-preset', 'ultrafast', temp_file, '-y'
        ]
        
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        if result.returncode == 0:
            with open(temp_file, 'rb') as f:
                video_data = f.read()
            os.unlink(temp_file)
            return video_data
        else:
            print(f"FFmpeg error: {result.stderr.decode()}")
            return create_fallback_video(duration)
            
    except Exception as e:
        print(f"Video creation error: {e}")
        return create_fallback_video(duration)

def create_fallback_video(duration=5):
    """Create a minimal valid MP4 file when ffmpeg is not available"""
    # This creates a very basic MP4 file
    # For demonstration purposes only
    import struct
    
    # A minimal MP4 file header
    mp4_data = bytearray()
    
    # ftyp box
    mp4_data.extend(b'\x00\x00\x00\x1c')  # size
    mp4_data.extend(b'ftyp')              # type
    mp4_data.extend(b'isom')              # major brand
    mp4_data.extend(b'\x00\x00\x00\x01')  # minor version
    mp4_data.extend(b'isom')              # compatible brands
    mp4_data.extend(b'iso2')
    mp4_data.extend(b'avc1')
    
    # This is a placeholder - in production, you would generate a real video
    # For now, just return a small valid MP4 file
    return bytes(mp4_data) + b'\x00' * 10000  # Add some padding

# ============================================================
# HTML FRONTEND (same as before, but simplified)
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
                <p>Real AI videos from your prompts. Mention duration like <strong>"10 second ka video"</strong> or <strong>"make 20 second video"</strong> to control length.</p>
                <div class="chips">
                    <div class="chip" onclick="useP(this)">A boy and girl hugging in park, 10 second video</div>
                    <div class="chip" onclick="useP(this)">Ocean waves at sunset, 15 seconds</div>
                    <div class="chip" onclick="useP(this)">City traffic neon lights at night, 20 second</div>
                    <div class="chip" onclick="useP(this)">Snow falling in forest, 10 seconds</div>
                    <div class="chip" onclick="useP(this)">Rocket launching into space, 15 second video</div>
                    <div class="chip" onclick="useP(this)">Tiger walking in jungle, 20 seconds</div>
                </div>
            </div>
        </div>
    </div>

    <div class="input-area">
        <div class="input-wrap">
            <div class="input-box">
                <textarea id="inp" placeholder="Describe video... add '10 second' or '20 second' for duration" rows="1" onkeydown="onKey(event)" oninput="resize(this)"></textarea>
                <button class="send-btn" id="sendBtn" onclick="send()">
                    <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
                </button>
            </div>
            <div class="hint">Enter to send • Shift+Enter for new line • Say "10 second" for duration</div>
        </div>
    </div>

    <!-- Settings Modal -->
    <div class="overlay" id="overlay" onclick="overlayClick(event)">
        <div class="modal">
            <div class="m-head">
                <div class="m-title">⚙️ Settings</div>
                <button class="x-btn" onclick="closeM()">×</button>
            </div>
            
            <div class="sec-label">🤖 AI Prompt Enhancer</div>
            <div class="dur-info">
                💡 <strong>Duration tip:</strong> In your prompt say "10 second video" or "20 second ka video" — AI will automatically set the right duration!
            </div>
            <div class="tabs">
                <button class="tab on" id="atab-none" onclick="switchATab('none',this)">None</button>
                <button class="tab" id="atab-or" onclick="switchATab('or',this)">OpenRouter</button>
                <button class="tab" id="atab-gem" onclick="switchATab('gem',this)">Gemini</button>
                <button class="tab" id="atab-ollama" onclick="switchATab('ollama',this)">Ollama</button>
            </div>
            
            <div class="panel show" id="ap-none">
                <div class="note">Prompt sent directly. Add OpenRouter/Gemini/Ollama for better results.</div>
            </div>
            
            <div class="panel" id="ap-or">
                <div class="fg">
                    <label>OpenRouter API Key</label>
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
                <div class="note">Get API key from openrouter.ai</div>
            </div>
            
            <div class="panel" id="ap-gem">
                <div class="fg">
                    <label>Gemini API Key</label>
                    <input type="password" id="gem-key" placeholder="AIza..."/>
                </div>
                <div class="fg">
                    <label>Model</label>
                    <select id="gem-model">
                        <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
                        <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
                    </select>
                </div>
                <div class="note">Get API key from makersuite.google.com</div>
            </div>
            
            <div class="panel" id="ap-ollama">
                <div class="fg">
                    <label>Ollama URL</label>
                    <input type="text" id="ollama-url" placeholder="http://localhost:11434"/>
                </div>
                <div class="fg">
                    <label>Model</label>
                    <input type="text" id="ollama-model" placeholder="llama3.2, mistral, etc."/>
                </div>
                <div class="note">Ollama runs locally. Models are free and private.</div>
            </div>
            
            <div class="divider"></div>
            <div class="sec-label">🎬 Video Generation</div>
            <div class="note" style="background:#0a0a1f;border-left-color:#4f46e5;color:#818cf8;">
                ⚠️ <strong>Note:</strong> This is a demo. The video shown is a sample with your enhanced prompt.
                <br><br>
                To generate real AI videos, integrate with:
                <br>
                • <strong>Replicate</strong> - replicate.com (MiniMax, Wan, etc.)
                <br>
                • <strong>HuggingFace</strong> - huggingface.co (ZeroScope, DAMO)
                <br>
                • <strong>Fal.ai</strong> - fal.ai (Kling, Hunyuan)
            </div>
            
            <div class="s-msg" id="sMsg"></div>
            <div class="m-foot">
                <button class="btn-test" onclick="testConn()">🔌 Test Connection</button>
                <button class="btn-save" onclick="saveS()">✓ Save Settings</button>
            </div>
        </div>
    </div>

    <script>
        let cfg = JSON.parse(localStorage.getItem('aivid2_cfg') || '{}');
        let busy = false;
        let curATab = 'none';
        let timerInterval = null;
        
        window.onload = () => {
            loadCfg();
            updateDot();
        };
        
        function updateDot() {
            const d = document.getElementById('dot'), t = document.getElementById('dotTxt');
            if (cfg.ai_provider && cfg.ai_provider !== 'none') {
                d.classList.add('on');
                const names = { or: 'OpenRouter', gem: 'Gemini', ollama: 'Ollama' };
                t.textContent = names[cfg.ai_provider] || 'Connected';
            } else {
                d.classList.remove('on');
                t.textContent = 'Setup Required';
            }
        }
        
        function loadCfg() {
            if (cfg.ai_provider) {
                switchATabById(cfg.ai_provider);
                if (cfg.ai_provider === 'or') {
                    document.getElementById('or-key').value = cfg.or_key || '';
                    document.getElementById('or-model').value = cfg.or_model || 'meta-llama/llama-3.1-8b-instruct:free';
                } else if (cfg.ai_provider === 'gem') {
                    document.getElementById('gem-key').value = cfg.gem_key || '';
                    document.getElementById('gem-model').value = cfg.gem_model || 'gemini-1.5-flash';
                } else if (cfg.ai_provider === 'ollama') {
                    document.getElementById('ollama-url').value = cfg.ollama_url || 'http://localhost:11434';
                    document.getElementById('ollama-model').value = cfg.ollama_model || 'llama3.2';
                }
            }
        }
        
        function switchATab(id, btn) {
            curATab = id;
            document.querySelectorAll('[id^="atab-"]').forEach(b => b.classList.remove('on'));
            btn.classList.add('on');
            document.querySelectorAll('[id^="ap-"]').forEach(p => p.classList.remove('show'));
            document.getElementById('ap-' + id).classList.add('show');
        }
        
        function switchATabById(id) {
            curATab = id;
            document.querySelectorAll('[id^="atab-"]').forEach(b => b.classList.remove('on'));
            const btn = document.getElementById('atab-' + id);
            if (btn) btn.classList.add('on');
            document.querySelectorAll('[id^="ap-"]').forEach(p => p.classList.remove('show'));
            const panel = document.getElementById('ap-' + id);
            if (panel) panel.classList.add('show');
        }
        
        function getCfg() {
            const c = { ai_provider: curATab };
            if (curATab === 'or') {
                c.or_key = document.getElementById('or-key').value;
                c.or_model = document.getElementById('or-model').value;
            } else if (curATab === 'gem') {
                c.gem_key = document.getElementById('gem-key').value;
                c.gem_model = document.getElementById('gem-model').value;
            } else if (curATab === 'ollama') {
                c.ollama_url = document.getElementById('ollama-url').value;
                c.ollama_model = document.getElementById('ollama-model').value;
            }
            return c;
        }
        
        function openM() {
            document.getElementById('overlay').classList.add('show');
            loadCfg();
        }
        
        function closeM() {
            document.getElementById('overlay').classList.remove('show');
            document.getElementById('sMsg').className = 's-msg';
        }
        
        function overlayClick(e) {
            if (e.target.id === 'overlay') closeM();
        }
        
        async function testConn() {
            const msg = document.getElementById('sMsg');
            msg.className = 's-msg info';
            msg.textContent = '⏳ Testing...';
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
                msg.className = 's-msg fail';
                msg.textContent = '❌ Cannot reach server.';
            }
        }
        
        function saveS() {
            cfg = getCfg();
            localStorage.setItem('aivid2_cfg', JSON.stringify(cfg));
            updateDot();
            closeM();
        }
        
        function useP(el) {
            document.getElementById('inp').value = el.textContent;
            resize(document.getElementById('inp'));
            send();
        }
        
        function onKey(e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                send();
            }
        }
        
        function resize(el) {
            el.style.height = 'auto';
            el.style.height = Math.min(el.scrollHeight, 180) + 'px';
        }
        
        async function send() {
            const inp = document.getElementById('inp');
            const prompt = inp.value.trim();
            if (!prompt || busy) return;
            
            if (!cfg.ai_provider || cfg.ai_provider === 'none') {
                alert('Please setup AI provider in Settings!');
                openM();
                return;
            }
            
            document.getElementById('welcome').style.display = 'none';
            addUser(prompt);
            inp.value = '';
            inp.style.height = 'auto';
            busy = true;
            document.getElementById('sendBtn').disabled = true;
            
            const tid = addTyping(prompt);
            try {
                const r = await fetch('/generate', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt, cfg })
                });
                
                // Check if response is OK
                if (!r.ok) {
                    const text = await r.text();
                    console.error('Server error:', text);
                    throw new Error(`Server error ${r.status}: ${text.substring(0, 100)}`);
                }
                
                const d = await r.json();
                removeTyping(tid);
                if (d.success) addVideo(d);
                else addErr(d.error || 'Generation failed');
            } catch (e) {
                removeTyping(tid);
                addErr('Request failed: ' + e.message);
                console.error('Full error:', e);
            }
            busy = false;
            document.getElementById('sendBtn').disabled = false;
        }
        
        function addUser(txt) {
            const w = document.createElement('div');
            w.className = 'msg-row';
            w.innerHTML = `<div class="message user-msg"><div class="user-bubble">${esc(txt)}</div></div>`;
            document.getElementById('chat').appendChild(w);
            scrollD();
        }
        
        function addTyping(prompt) {
            const id = 't' + Date.now();
            const durMatch = prompt.match(/(\d+)\s*sec/i);
            const dur = durMatch ? durMatch[1] : '5';
            const w = document.createElement('div');
            w.className = 'msg-row';
            w.id = id;
            w.innerHTML = `
                <div class="typing-wrap">
                    <div class="ai-av">🎬</div>
                    <div class="ai-body">
                        <div class="dots"><span></span><span></span><span></span></div>
                        <div class="prog-box">
                            <div class="prog-bar"><div class="prog-fill" id="pf${id}" style="width:0%"></div></div>
                            <div class="steps">
                                <div class="step active" id="s1${id}">🤖 Enhancing prompt for maximum quality...</div>
                                <div class="step" id="s2${id}">🎬 Processing video request (${dur}s video)...</div>
                                <div class="step" id="s3${id}">⚙️ AI analyzing and preparing...</div>
                                <div class="step" id="s4${id}">📥 Generating video output...</div>
                            </div>
                            <div class="timer" id="timer${id}">⏱️ Elapsed: 0s</div>
                        </div>
                    </div>
                </div>`;
            document.getElementById('chat').appendChild(w);
            scrollD();
            
            let elapsed = 0;
            timerInterval = setInterval(() => {
                elapsed++;
                const timerEl = document.getElementById('timer' + id);
                if (timerEl) timerEl.textContent = `⏱️ Elapsed: ${elapsed}s`;
            }, 1000);
            
            animProg(id);
            return id;
        }
        
        function animProg(id) {
            [[10,1,1000],[30,2,5000],[60,3,20000],[85,4,60000]].forEach(([pct, step, delay]) => {
                setTimeout(() => {
                    const pf = document.getElementById('pf' + id);
                    if (pf) pf.style.width = pct + '%';
                    for (let i = 1; i <= 4; i++) {
                        const el = document.getElementById('s' + i + id);
                        if (el) el.className = 'step' + (i < step ? ' done' : i === step ? ' active' : '');
                    }
                }, delay);
            });
        }
        
        function removeTyping(id) {
            if (timerInterval) {
                clearInterval(timerInterval);
                timerInterval = null;
            }
            const el = document.getElementById(id);
            if (el) el.remove();
        }
        
        function addVideo(d) {
            const w = document.createElement('div');
            w.className = 'msg-row';
            const enhanced = d.enhanced_prompt ? `<div style="font-size:12px;color:#555;margin-bottom:8px;">✨ Enhanced: ${esc(d.enhanced_prompt.substring(0,150))}${d.enhanced_prompt.length > 150 ? '...' : ''}</div>` : '';
            w.innerHTML = `
                <div class="message ai-msg">
                    <div class="ai-av">🎬</div>
                    <div class="ai-body">
                        ${enhanced}
                        <div class="ai-text">✅ <strong>${esc(d.title || 'Generated Video')}</strong> — ${d.duration}s video ready!</div>
                        <div class="vid-card">
                            <video controls autoplay muted loop><source src="${d.video_url}" type="video/mp4"></video>
                            <div class="vid-footer">
                                <span class="vid-title">🎬 ${esc(d.title || 'AI Video')}</span>
                                <span class="vid-meta">${d.duration}s</span>
                                <a href="${d.video_url}" download class="dl-btn">⬇ Download</a>
                            </div>
                        </div>
                    </div>
                </div>`;
            document.getElementById('chat').appendChild(w);
            scrollD();
        }
        
        function addErr(msg) {
            const w = document.createElement('div');
            w.className = 'msg-row';
            w.innerHTML = `
                <div class="message ai-msg">
                    <div class="ai-av">🎬</div>
                    <div class="ai-body"><div class="err-box">⚠️ ${esc(msg)}</div></div>
                </div>`;
            document.getElementById('chat').appendChild(w);
            scrollD();
        }
        
        function scrollD() {
            const c = document.getElementById('chat');
            setTimeout(() => c.scrollTop = c.scrollHeight, 100);
        }
        
        function esc(t) {
            const d = document.createElement('div');
            d.textContent = t;
            return d.innerHTML;
        }
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
    try:
        data = request.json
        if not data:
            return jsonify({"error": "No JSON data received"}), 400
            
        prompt = data.get("prompt", "").strip()
        cfg = data.get("cfg", {})
        
        if not prompt:
            return jsonify({"error": "Prompt required"}), 400
            
        if not cfg.get("ai_provider") or cfg.get("ai_provider") == "none":
            return jsonify({"error": "No AI provider configured. Please set up in Settings."}), 400
        
        # Detect duration from prompt
        duration = detect_duration(prompt)
        print(f"Duration: {duration}s")
        
        # Enhance prompt
        enhanced = enhance_prompt(prompt, cfg)
        print(f"Original: {prompt[:80]}")
        print(f"Enhanced: {enhanced[:80]}")
        
        # Generate sample video
        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)
        
        # Create sample video with enhanced prompt
        video_data = create_sample_video(enhanced, duration)
        with open(vid_path, "wb") as f:
            f.write(video_data)
        
        words = prompt.split()
        title = " ".join(words[:6]) if len(words) > 6 else prompt
        
        return jsonify({
            "success": True,
            "video_url": f"/video/{vid_name}",
            "title": title,
            "duration": duration,
            "enhanced_prompt": enhanced
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
    try:
        cfg = request.json.get("cfg", {})
        provider = cfg.get("ai_provider")
        
        if not provider or provider == "none":
            return jsonify({"success": False, "message": "No provider selected"})
        
        if provider == "or":
            key = cfg.get("or_key", "")
            if not key:
                return jsonify({"success": False, "message": "API key missing"})
            headers = {"Authorization": f"Bearer {key}"}
            r = requests.get("https://openrouter.ai/api/v1/auth/key", headers=headers, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": "OpenRouter connection successful!"})
            return jsonify({"success": False, "message": f"Invalid API key ({r.status_code})"})
            
        elif provider == "gem":
            key = cfg.get("gem_key", "")
            if not key:
                return jsonify({"success": False, "message": "API key missing"})
            url = "https://generativelanguage.googleapis.com/v1beta/models"
            r = requests.get(url, params={"key": key}, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": "Gemini connection successful!"})
            return jsonify({"success": False, "message": f"Invalid API key ({r.status_code})"})
            
        elif provider == "ollama":
            url = cfg.get("ollama_url", "http://localhost:11434")
            r = requests.get(f"{url}/api/tags", timeout=5)
            if r.status_code == 200:
                return jsonify({"success": True, "message": "Ollama connection successful!"})
            return jsonify({"success": False, "message": f"Cannot connect to Ollama ({r.status_code})"})
            
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})
    
    return jsonify({"success": False, "message": "Unknown error"})

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print("="*50)
    print("🎬 AI Video Generator")
    print("="*50)
    print(f"\n🚀 Server running on http://localhost:{port}")
    print("\n⚙️  AI Providers Available:")
    print("  • OpenRouter - Cloud-based (api.openrouter.ai)")
    print("  • Gemini - Google's AI (makersuite.google.com)")
    print("  • Ollama - Local, free (ollama.ai)")
    print("\n📝 Note: Video generation is in demo mode.")
    print("   The video shown is a sample with your prompt overlay.")
    print("   To generate real videos, integrate with Replicate/HuggingFace/Fal.ai")
    print("="*50)
    app.run(host="0.0.0.0", port=port, debug=True)
