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
    
    # Direct number + second pattern
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
            # Clamp to model limits
            dur = max(5, min(dur, 30))
            print(f"Detected duration: {dur}s from prompt")
            return dur
    
    # Keywords
    if any(w in prompt_lower for w in ['short', 'quick', 'brief', 'chhota']):
        return 5
    if any(w in prompt_lower for w in ['long', 'detailed', 'lamba', 'extended']):
        return 15
    
    # Default
    return 5


# ============================================================
# ENHANCE PROMPT
# ============================================================
def enhance_prompt(prompt, cfg):
    ai_provider = cfg.get("ai_provider", "none")
    if ai_provider == "none" or not ai_provider:
        # Auto enhance without AI
        enhanced = f"{prompt}, cinematic quality, high definition, realistic, detailed, professional cinematography, smooth motion, 4K"
        return enhanced

    system = """You are an expert AI video generation prompt engineer.
Your job is to enhance the user prompt for maximum realism and quality.
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

    except Exception as e:
        print(f"Enhance failed: {e}")

    return prompt + ", cinematic, photorealistic, 4K, smooth motion, high quality"


# ============================================================
# HUGGINGFACE VIDEO GENERATION
# ============================================================
def generate_hf(prompt, cfg, duration):
    model = cfg.get("hf_model", "cerspense/zeroscope_v2_XL")
    token = cfg.get("hf_key", "")
    
    # Calculate frames based on duration
    fps = 8
    num_frames = min(duration * fps, 200)
    num_frames = max(num_frames, 24)
    
    print(f"HF Model: {model}, Duration: {duration}s, Frames: {num_frames}")
    
    api_url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Model specific params
    if "zeroscope" in model:
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_frames": num_frames,
                "num_inference_steps": 50,
                "guidance_scale": 17.5,
                "width": 576,
                "height": 320,
            }
        }
    elif "damo" in model or "text-to-video" in model:
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_frames": min(num_frames, 64),
                "num_inference_steps": 50,
                "guidance_scale": 9.0,
            }
        }
    else:
        payload = {
            "inputs": prompt,
            "parameters": {
                "num_frames": num_frames,
                "num_inference_steps": 50,
                "guidance_scale": 9.0,
            }
        }

    max_retries = 5
    for attempt in range(max_retries):
        print(f"HF attempt {attempt+1}/{max_retries}")
        try:
            r = requests.post(api_url, headers=headers, json=payload, timeout=600)
            print(f"HF status: {r.status_code}, size: {len(r.content)}")

            if r.status_code == 200:
                content_type = r.headers.get("content-type", "")
                if len(r.content) > 5000:
                    return r.content, "video/mp4"
                try:
                    err = r.json()
                    raise Exception(f"HF returned JSON instead of video: {err}")
                except json.JSONDecodeError:
                    return r.content, "video/mp4"

            elif r.status_code == 503:
                try:
                    resp_json = r.json()
                    wait = float(resp_json.get("estimated_time", 30))
                    wait = min(wait, 60)
                    print(f"Model loading, waiting {wait:.0f}s...")
                except:
                    wait = 30
                time.sleep(wait)

            elif r.status_code == 401:
                raise Exception("Invalid HuggingFace token. Check your API key.")
            
            elif r.status_code == 429:
                print("Rate limited, waiting 30s...")
                time.sleep(30)
            
            elif r.status_code == 500:
                err_text = r.text[:300]
                print(f"HF 500 error: {err_text}")
                # Try with fewer frames
                if "num_frames" in payload.get("parameters", {}):
                    payload["parameters"]["num_frames"] = max(16, payload["parameters"]["num_frames"] // 2)
                    print(f"Retrying with {payload['parameters']['num_frames']} frames")
                time.sleep(10)
            else:
                raise Exception(f"HF API error {r.status_code}: {r.text[:200]}")

        except requests.Timeout:
            print(f"HF timeout on attempt {attempt+1}")
            if attempt < max_retries - 1:
                time.sleep(10)
            else:
                raise Exception("HuggingFace timeout - model taking too long")

    raise Exception("HuggingFace: all retries failed")


# ============================================================
# REPLICATE VIDEO GENERATION  
# ============================================================
def generate_replicate(prompt, cfg, duration):
    token = cfg.get("rep_key", "")
    model = cfg.get("rep_model", "minimax/video-01")
    
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json",
        "Prefer": "wait"
    }

    # Build input based on model
    inp = {"prompt": prompt}

    if "minimax" in model:
        # MiniMax supports 5-30 seconds
        inp.update({
            "duration": min(duration, 30),
            "resolution": "1080p",
            "quality": "quality_1080p"
        })

    elif "wan" in model:
        fps = 16
        num_frames = duration * fps
        if "480p" in model:
            num_frames = min(num_frames, 81)
            inp.update({
                "num_frames": num_frames,
                "fps": fps,
                "resolution": "480p",
                "sample_steps": 30,
                "sample_guide_scale": 5.0,
            })
        elif "720p" in model:
            num_frames = min(num_frames, 121)
            inp.update({
                "num_frames": num_frames,
                "fps": fps,
                "resolution": "720p",
                "sample_steps": 30,
                "sample_guide_scale": 5.0,
            })

    elif "luma" in model or "ray" in model:
        # Luma Ray supports duration
        inp.update({
            "duration": f"{min(duration, 9)}s",
            "aspect_ratio": "16:9",
            "loop": False
        })

    elif "hunyuan" in model:
        fps = 24
        num_frames = min(duration * fps, 129)
        inp.update({
            "num_frames": num_frames,
            "fps": fps,
            "width": 1280,
            "height": 720,
            "num_inference_steps": 50,
            "guidance_scale": 6.0,
            "flow_shift": 7.0,
        })

    elif "mochi" in model:
        fps = 24
        num_frames = min(duration * fps, 200)
        inp.update({
            "num_frames": num_frames,
        })

    elif "cogvideo" in model or "cog" in model:
        fps = 8
        num_frames = min(duration * fps, 49)
        inp.update({
            "num_frames": num_frames,
            "num_inference_steps": 50,
            "guidance_scale": 6.0,
            "fps": fps,
        })

    else:
        # Generic fallback
        fps = 16
        inp.update({
            "num_frames": min(duration * fps, 150),
            "fps": fps,
        })

    print(f"Replicate model: {model}")
    print(f"Replicate input: {inp}")

    # Try models endpoint first
    try:
        r = requests.post(
            f"https://api.replicate.com/v1/models/{model}/predictions",
            headers=headers,
            json={"input": inp},
            timeout=30
        )
        print(f"Replicate submit status: {r.status_code}")
        
        if r.status_code not in [200, 201]:
            raise Exception(f"Model endpoint failed: {r.status_code}")
        
        prediction = r.json()

    except Exception as e:
        print(f"Models endpoint failed: {e}, trying versions endpoint...")
        # Fallback to versions endpoint
        r = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={"model": model, "input": inp},
            timeout=30
        )
        if r.status_code not in [200, 201]:
            raise Exception(f"Replicate error {r.status_code}: {r.text[:300]}")
        prediction = r.json()

    pred_id = prediction.get("id")
    if not pred_id:
        raise Exception(f"No prediction ID: {prediction}")

    print(f"Polling prediction: {pred_id}")
    
    # Poll with longer timeout for longer videos
    max_polls = 180  # 15 min max
    for i in range(max_polls):
        time.sleep(5)
        try:
            poll = requests.get(
                f"https://api.replicate.com/v1/predictions/{pred_id}",
                headers=headers, timeout=30
            )
            data = poll.json()
            status = data.get("status")
            
            if i % 6 == 0:  # Log every 30s
                print(f"Poll {i}: status={status}")

            if status == "succeeded":
                output = data.get("output")
                video_url = None
                
                if isinstance(output, str):
                    video_url = output
                elif isinstance(output, list) and len(output) > 0:
                    video_url = output[0]
                elif isinstance(output, dict):
                    video_url = output.get("url") or output.get("video")
                
                if not video_url:
                    raise Exception(f"No video URL in output: {output}")
                
                print(f"Downloading video from: {video_url[:80]}")
                vid_r = requests.get(video_url, timeout=300)
                
                if vid_r.status_code == 200 and len(vid_r.content) > 1000:
                    return vid_r.content, "video/mp4"
                raise Exception(f"Video download failed: {vid_r.status_code}")

            elif status == "failed":
                err = data.get("error", "Unknown error")
                raise Exception(f"Replicate failed: {err}")
            
            elif status == "canceled":
                raise Exception("Prediction was canceled")

        except requests.RequestException as e:
            print(f"Poll error: {e}")
            time.sleep(5)

    raise Exception("Replicate timeout after 15 minutes")


# ============================================================
# FAL.AI VIDEO GENERATION
# ============================================================
def generate_fal(prompt, cfg, duration):
    api_key = cfg.get("fal_key", "")
    model = cfg.get("fal_model", "fal-ai/kling-video/v1.5/standard/text-to-video")

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }

    payload = {"prompt": prompt}

    if "kling" in model:
        payload.update({
            "duration": str(min(duration, 10)),
            "aspect_ratio": "16:9",
            "negative_prompt": "blurry, low quality, distorted"
        })
    elif "wan" in model:
        fps = 16
        payload.update({
            "num_frames": min(duration * fps, 200),
            "frames_per_second": fps,
        })
    elif "ltx" in model:
        fps = 24
        payload.update({
            "num_frames": min(duration * fps, 257),
            "frames_per_second": fps,
            "negative_prompt": "blurry, distorted, low quality"
        })
    elif "hunyuan" in model:
        payload.update({
            "video_length": min(duration, 10),
            "resolution": "720p",
        })
    else:
        payload.update({
            "duration": str(min(duration, 10)),
        })

    print(f"Fal.ai model: {model}, duration: {duration}s")
    print(f"Fal payload: {payload}")

    # Submit to queue
    r = requests.post(
        f"https://queue.fal.run/{model}",
        headers=headers, json=payload, timeout=60
    )

    print(f"Fal submit status: {r.status_code}")

    if r.status_code not in [200, 201, 202]:
        raise Exception(f"Fal.ai submit error {r.status_code}: {r.text[:300]}")

    data = r.json()
    print(f"Fal submit response: {str(data)[:200]}")

    request_id = data.get("request_id")

    if not request_id:
        # Maybe direct response
        video = data.get("video", {})
        url = video.get("url") if isinstance(video, dict) else str(video)
        if url and url.startswith("http"):
            vid_r = requests.get(url, timeout=300)
            return vid_r.content, "video/mp4"
        raise Exception(f"No request_id in response: {data}")

    print(f"Fal request_id: {request_id}")

    # Poll
    max_polls = 180
    for i in range(max_polls):
        time.sleep(5)
        try:
            poll = requests.get(
                f"https://queue.fal.run/{model}/requests/{request_id}/status",
                headers=headers, timeout=30
            )
            status_data = poll.json()
            status = status_data.get("status")
            
            if i % 6 == 0:
                print(f"Fal poll {i}: {status}")

            if status == "COMPLETED":
                result_r = requests.get(
                    f"https://queue.fal.run/{model}/requests/{request_id}",
                    headers=headers, timeout=30
                )
                out = result_r.json()
                print(f"Fal result: {str(out)[:200]}")

                # Try different output formats
                video_url = None
                if "video" in out:
                    v = out["video"]
                    if isinstance(v, dict):
                        video_url = v.get("url")
                    elif isinstance(v, str):
                        video_url = v
                elif "videos" in out:
                    videos = out["videos"]
                    if videos and isinstance(videos[0], dict):
                        video_url = videos[0].get("url")
                    elif videos:
                        video_url = str(videos[0])
                elif "output" in out:
                    video_url = out["output"]

                if video_url:
                    vid_r = requests.get(video_url, timeout=300)
                    if vid_r.status_code == 200:
                        return vid_r.content, "video/mp4"

                raise Exception(f"Could not extract video URL from: {out}")

            elif status in ["FAILED", "ERROR"]:
                raise Exception(f"Fal.ai failed: {status_data}")

        except requests.RequestException as e:
            print(f"Fal poll error: {e}")

    raise Exception("Fal.ai timeout after 15 minutes")


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
      <textarea id="inp"
        placeholder="Describe video... add '10 second' or '20 second' for duration"
        rows="1" onkeydown="onKey(event)" oninput="resize(this)"></textarea>
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

    <div class="sec-label">🎬 Video Generation API</div>

    <div class="dur-info">
      💡 <strong>Duration tip:</strong> In your prompt say "10 second video" or "20 second ka video" — AI will automatically set the right duration!
    </div>

    <div class="tabs">
      <button class="tab on" id="vtab-hf"  onclick="switchVTab('hf',this)">HuggingFace</button>
      <button class="tab" id="vtab-rep"    onclick="switchVTab('rep',this)">Replicate</button>
      <button class="tab" id="vtab-fal"    onclick="switchVTab('fal',this)">Fal.ai</button>
    </div>

    <div class="panel show" id="vp-hf">
      <div class="fg">
        <label>HuggingFace API Token</label>
        <input type="password" id="hf-key" placeholder="hf_..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="hf-model">
          <option value="cerspense/zeroscope_v2_XL">ZeroScope v2 XL ⭐ Best Quality</option>
          <option value="cerspense/zeroscope_v2_576w">ZeroScope v2 576w (Faster)</option>
          <option value="damo-vilab/text-to-video-ms-1.7b">DAMO Text-to-Video</option>
        </select>
      </div>
      <div class="note">Max ~8-10 sec on HuggingFace Pro. Free token: huggingface.co/settings/tokens</div>
    </div>

    <div class="panel" id="vp-rep">
      <div class="fg">
        <label>Replicate API Token</label>
        <input type="password" id="rep-key" placeholder="r8_..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="rep-model">
          <option value="minimax/video-01">MiniMax Video-01 ⭐ Best (up to 30s)</option>
          <option value="wan-ai/wan2.1-t2v-720p">Wan 2.1 720p (up to 10s)</option>
          <option value="wan-ai/wan2.1-t2v-480p">Wan 2.1 480p (up to 8s)</option>
          <option value="luma/ray">Luma Ray (up to 9s)</option>
          <option value="tencent/hunyuan-video">HunyuanVideo (up to 8s)</option>
        </select>
      </div>
      <div class="note">MiniMax supports up to 30 seconds! replicate.com/account/api-tokens</div>
    </div>

    <div class="panel" id="vp-fal">
      <div class="fg">
        <label>Fal.ai API Key</label>
        <input type="password" id="fal-key" placeholder="your-fal-key..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="fal-model">
          <option value="fal-ai/kling-video/v1.5/standard/text-to-video">Kling 1.5 Standard (up to 10s)</option>
          <option value="fal-ai/kling-video/v1.5/pro/text-to-video">Kling 1.5 Pro ⭐ Best</option>
          <option value="fal-ai/wan/v2.1/1.3b/text-to-video">Wan 2.1 1.3B (Fast)</option>
          <option value="fal-ai/ltx-video">LTX Video (Fast)</option>
          <option value="fal-ai/hunyuan-video">HunyuanVideo</option>
        </select>
      </div>
      <div class="note">Kling 1.5 Pro = best quality. fal.ai/dashboard/keys</div>
    </div>

    <div class="divider"></div>
    <div class="sec-label">🤖 AI Prompt Enhancer (Optional but Recommended)</div>

    <div class="tabs">
      <button class="tab on" id="atab-none" onclick="switchATab('none',this)">None</button>
      <button class="tab" id="atab-or"     onclick="switchATab('or',this)">OpenRouter</button>
      <button class="tab" id="atab-gem"    onclick="switchATab('gem',this)">Gemini</button>
    </div>

    <div class="panel show" id="ap-none">
      <div class="note">Prompt sent directly. Add OpenRouter/Gemini for better results.</div>
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
let curVTab = 'hf';
let curATab = 'none';
let timerInterval = null;

window.onload = () => { loadCfg(); updateDot(); };

function updateDot() {
  const d = document.getElementById('dot'), t = document.getElementById('dotTxt');
  if (cfg.video_provider) {
    d.classList.add('on');
    const names = { hf: 'HuggingFace', rep: 'Replicate', fal: 'Fal.ai' };
    t.textContent = names[cfg.video_provider] || 'Connected';
  } else {
    d.classList.remove('on');
    t.textContent = 'Setup Required';
  }
}

function loadCfg() {
  if (cfg.video_provider) {
    switchVTabById(cfg.video_provider);
    if (cfg.video_provider === 'hf') {
      document.getElementById('hf-key').value = cfg.hf_key || '';
      document.getElementById('hf-model').value = cfg.hf_model || 'cerspense/zeroscope_v2_XL';
    } else if (cfg.video_provider === 'rep') {
      document.getElementById('rep-key').value = cfg.rep_key || '';
      document.getElementById('rep-model').value = cfg.rep_model || 'minimax/video-01';
    } else if (cfg.video_provider === 'fal') {
      document.getElementById('fal-key').value = cfg.fal_key || '';
      document.getElementById('fal-model').value = cfg.fal_model || 'fal-ai/kling-video/v1.5/standard/text-to-video';
    }
  }
  if (cfg.ai_provider) {
    switchATabById(cfg.ai_provider);
    if (cfg.ai_provider === 'or') {
      document.getElementById('or-key').value = cfg.or_key || '';
      document.getElementById('or-model').value = cfg.or_model || 'meta-llama/llama-3.1-8b-instruct:free';
    } else if (cfg.ai_provider === 'gem') {
      document.getElementById('gem-key').value = cfg.gem_key || '';
      document.getElementById('gem-model').value = cfg.gem_model || 'gemini-1.5-flash';
    }
  }
}

function switchVTab(id, btn) {
  curVTab = id;
  document.querySelectorAll('[id^="vtab-"]').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('[id^="vp-"]').forEach(p => p.classList.remove('show'));
  document.getElementById('vp-' + id).classList.add('show');
}
function switchVTabById(id) {
  curVTab = id;
  document.querySelectorAll('[id^="vtab-"]').forEach(b => b.classList.remove('on'));
  const btn = document.getElementById('vtab-' + id);
  if (btn) btn.classList.add('on');
  document.querySelectorAll('[id^="vp-"]').forEach(p => p.classList.remove('show'));
  const panel = document.getElementById('vp-' + id);
  if (panel) panel.classList.add('show');
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
  const c = { video_provider: curVTab };
  if (curVTab === 'hf') {
    c.hf_key = document.getElementById('hf-key').value;
    c.hf_model = document.getElementById('hf-model').value;
  } else if (curVTab === 'rep') {
    c.rep_key = document.getElementById('rep-key').value;
    c.rep_model = document.getElementById('rep-model').value;
  } else if (curVTab === 'fal') {
    c.fal_key = document.getElementById('fal-key').value;
    c.fal_model = document.getElementById('fal-model').value;
  }
  c.ai_provider = curATab;
  if (curATab === 'or') {
    c.or_key = document.getElementById('or-key').value;
    c.or_model = document.getElementById('or-model').value;
  } else if (curATab === 'gem') {
    c.gem_key = document.getElementById('gem-key').value;
    c.gem_model = document.getElementById('gem-model').value;
  }
  return c;
}

function openM() { document.getElementById('overlay').classList.add('show'); loadCfg(); }
function closeM() { document.getElementById('overlay').classList.remove('show'); document.getElementById('sMsg').className = 's-msg'; }
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
    msg.className = 's-msg fail'; msg.textContent = '❌ Cannot reach server.';
  }
}

function saveS() {
  cfg = getCfg();
  localStorage.setItem('aivid2_cfg', JSON.stringify(cfg));
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
  if (!cfg.video_provider) { alert('Please setup API in Settings!'); openM(); return; }

  document.getElementById('welcome').style.display = 'none';
  addUser(prompt);
  inp.value = ''; inp.style.height = 'auto';
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
    else addErr(d.error || 'Generation failed');
  } catch (e) {
    removeTyping(tid);
    addErr('Request failed: ' + e.message);
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

  // Detect duration for display
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
          <div class="step active" id="s1${id}">🤖 Enhancing prompt for maximum quality...</div>
          <div class="step" id="s2${id}">🎬 Sending to video AI (${dur}s video)...</div>
          <div class="step" id="s3${id}">⚙️ AI generating real video frames...</div>
          <div class="step" id="s4${id}">📥 Downloading & saving video...</div>
        </div>
        <div class="timer" id="timer${id}">⏱️ Elapsed: 0s (longer videos take more time)</div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w); scrollD();

  // Timer
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
      const pf = document.getElementById('pf' + id); if (pf) pf.style.width = pct + '%';
      for (let i = 1; i <= 4; i++) {
        const el = document.getElementById('s' + i + id);
        if (el) el.className = 'step' + (i < step ? ' done' : i === step ? ' active' : '');
      }
    }, delay);
  });
}

function removeTyping(id) {
  if (timerInterval) { clearInterval(timerInterval); timerInterval = null; }
  const el = document.getElementById(id); if (el) el.remove();
}

function addVideo(d) {
  const w = document.createElement('div'); w.className = 'msg-row';
  const enhanced = d.enhanced_prompt ? `<div style="font-size:12px;color:#555;margin-bottom:8px;">Enhanced: ${esc(d.enhanced_prompt.substring(0,100))}...</div>` : '';
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
  document.getElementById('chat').appendChild(w); scrollD();
}

function addErr(msg) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `
  <div class="message ai-msg">
    <div class="ai-av">🎬</div>
    <div class="ai-body"><div class="err-box">⚠️ ${esc(msg)}</div></div>
  </div>`;
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
        return jsonify({"error": "No video API configured"}), 400

    try:
        # Detect duration from prompt
        duration = detect_duration(prompt)
        print(f"Duration: {duration}s")

        # Enhance prompt
        enhanced = enhance_prompt(prompt, cfg)
        print(f"Original: {prompt[:80]}")
        print(f"Enhanced: {enhanced[:80]}")

        # Generate
        provider = cfg.get("video_provider")
        if provider == "hf":
            video_bytes, mime = generate_hf(enhanced, cfg, duration)
        elif provider == "rep":
            video_bytes, mime = generate_replicate(enhanced, cfg, duration)
        elif provider == "fal":
            video_bytes, mime = generate_fal(enhanced, cfg, duration)
        else:
            return jsonify({"error": f"Unknown provider: {provider}"}), 400

        if not video_bytes or len(video_bytes) < 1000:
            return jsonify({"error": "Empty video returned from API"}), 500

        # Save
        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        print(f"Saved: {vid_name} ({len(video_bytes)/1024:.0f} KB)")

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
    cfg = request.json.get("cfg", {})
    provider = cfg.get("video_provider")
    if not provider:
        return jsonify({"success": False, "message": "No provider selected"})
    try:
        if provider == "hf":
            token = cfg.get("hf_key", "")
            if not token:
                return jsonify({"success": False, "message": "Token missing"})
            r = requests.get("https://huggingface.co/api/whoami",
                             headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": f"Connected as {r.json().get('name','User')}!"})
            return jsonify({"success": False, "message": f"Invalid token ({r.status_code})"})

        elif provider == "rep":
            token = cfg.get("rep_key", "")
            if not token:
                return jsonify({"success": False, "message": "Token missing"})
            r = requests.get("https://api.replicate.com/v1/account",
                             headers={"Authorization": f"Token {token}"}, timeout=10)
            if r.status_code == 200:
                return jsonify({"success": True, "message": f"Connected as {r.json().get('username','User')}!"})
            return jsonify({"success": False, "message": f"Invalid token ({r.status_code})"})

        elif provider == "fal":
            key = cfg.get("fal_key", "")
            if not key:
                return jsonify({"success": False, "message": "Key missing"})
            return jsonify({"success": True, "message": "Fal.ai key saved!"})

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
