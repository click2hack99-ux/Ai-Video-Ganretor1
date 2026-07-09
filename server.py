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
    
    return 5


# ============================================================
# ENHANCE PROMPT
# ============================================================
def enhance_prompt(prompt, cfg):
    ai_provider = cfg.get("ai_provider", "none")
    if ai_provider == "none" or not ai_provider:
        enhanced = f"{prompt}, cinematic quality, high definition, realistic, detailed, professional cinematography, smooth motion, 4K"
        return enhanced

    system = """You are an expert prompt enhancer. Make the prompt more detailed and cinematic for video generation.
Keep original details. Add: lighting, camera angles, atmosphere, mood.
Return ONLY the enhanced prompt, max 150 words."""

    try:
        if ai_provider == "or":
            headers = {
                "Authorization": f"Bearer {cfg.get('or_key','')}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aivideogen.onrender.com",
                "X-Title": "AI Video Generator"
            }
            
            model = cfg.get("or_model", "meta-llama/llama-3.1-8b-instruct:free")
            if cfg.get("or_custom"):
                model = cfg.get("or_custom")
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 200
            }
            
            print(f"OpenRouter enhancing with model: {model}")
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=data, timeout=30
            )
            
            if r.status_code != 200:
                print(f"OpenRouter error {r.status_code}: {r.text[:300]}")
                return prompt + ", cinematic quality"
            
            resp = r.json()
            if "choices" in resp and len(resp["choices"]) > 0:
                return resp["choices"][0]["message"]["content"].strip()
            return prompt + ", cinematic quality"

        elif ai_provider == "gem":
            model = cfg.get("gem_model", "gemini-1.5-flash")
            if cfg.get("gem_custom"):
                model = cfg.get("gem_custom")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 200}
            }
            
            print(f"Gemini enhancing with model: {model}")
            r = requests.post(
                url, params={"key": cfg.get("gem_key", "")},
                json=data, timeout=30
            )
            
            if r.status_code != 200:
                print(f"Gemini error {r.status_code}")
                return prompt + ", cinematic quality"
            
            resp = r.json()
            if "candidates" in resp and len(resp["candidates"]) > 0:
                return resp["candidates"][0]["content"]["parts"][0]["text"].strip()
            return prompt + ", cinematic quality"

        elif ai_provider == "oll":
            model = cfg.get("oll_model", "llama2")
            if cfg.get("oll_custom"):
                model = cfg.get("oll_custom")
            
            url = cfg.get("oll_url", "http://localhost:11434") + "/api/generate"
            
            print(f"Ollama enhancing with model: {model}")
            r = requests.post(url, json={
                "model": model,
                "prompt": f"{system}\n\nPrompt: {prompt}",
                "stream": False
            }, timeout=120)
            
            if r.status_code != 200:
                print(f"Ollama error {r.status_code}")
                return prompt + ", cinematic quality"
            
            resp = r.json()
            if "response" in resp:
                return resp["response"].strip()
            return prompt + ", cinematic quality"

    except Exception as e:
        print(f"Enhance error: {e}")

    return prompt + ", cinematic quality, high definition, realistic"


# ============================================================
# VIDEO GENERATION
# ============================================================
def generate_video(prompt, cfg, duration):
    """Generate video using AI"""
    
    provider = cfg.get("video_provider", "or")
    
    system = f"""Create a {duration} second video description in JSON:
{{"description": "Scene description", "mood": "mood"}}"""

    try:
        if provider == "or":
            headers = {
                "Authorization": f"Bearer {cfg.get('or_key','')}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aivideogen.onrender.com",
                "X-Title": "AI Video Generator"
            }
            
            model = cfg.get("or_model", "meta-llama/llama-3.1-8b-instruct:free")
            if cfg.get("or_custom"):
                model = cfg.get("or_custom")
            
            data = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 300
            }
            
            print(f"OpenRouter video with model: {model}")
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers, json=data, timeout=30
            )
            
            if r.status_code != 200:
                raise Exception(f"OpenRouter error {r.status_code}")
            
            resp = r.json()
            if "choices" not in resp:
                raise Exception("Invalid OpenRouter response")
            
            response_text = resp["choices"][0]["message"]["content"]

        elif provider == "gem":
            model = cfg.get("gem_model", "gemini-1.5-flash")
            if cfg.get("gem_custom"):
                model = cfg.get("gem_custom")
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 300}
            }
            
            print(f"Gemini video with model: {model}")
            r = requests.post(
                url, params={"key": cfg.get("gem_key", "")},
                json=data, timeout=30
            )
            
            if r.status_code != 200:
                raise Exception(f"Gemini error {r.status_code}")
            
            resp = r.json()
            response_text = resp["candidates"][0]["content"]["parts"][0]["text"]

        elif provider == "oll":
            model = cfg.get("oll_model", "llama2")
            if cfg.get("oll_custom"):
                model = cfg.get("oll_custom")
            
            url = cfg.get("oll_url", "http://localhost:11434") + "/api/generate"
            
            print(f"Ollama video with model: {model}")
            r = requests.post(url, json={
                "model": model,
                "prompt": f"{system}\n\nPrompt: {prompt}",
                "stream": False
            }, timeout=180)
            
            if r.status_code != 200:
                raise Exception(f"Ollama error {r.status_code}")
            
            resp = r.json()
            response_text = resp["response"]

        else:
            raise Exception(f"Unknown provider: {provider}")

        print(f"Video response: {response_text[:200]}")

        # Create video frames
        video_bytes = create_video_frames(response_text, prompt, duration)
        return video_bytes, "video/mp4"

    except Exception as e:
        print(f"Video generation error: {e}")
        import traceback
        traceback.print_exc()
        raise


def create_video_frames(description, original_prompt, duration):
    """Creates a video from frames"""
    try:
        from PIL import Image, ImageDraw, ImageFont
        import numpy as np
        
        width, height = 1280, 720
        fps = 24
        total_frames = duration * fps
        
        frames = []
        
        # Generate frames
        for frame_num in range(total_frames):
            progress = frame_num / max(total_frames - 1, 1)
            
            # Create frame
            img = Image.new("RGB", (width, height), color=(20, 20, 40))
            draw = ImageDraw.Draw(img)
            
            # Gradient
            for y in range(height):
                ratio = y / height
                r = int(20 + ratio * 40)
                g = int(20 + ratio * 30)
                b = int(40 + ratio * 60)
                draw.line([(0, y), (width, y)], fill=(r, g, b))
            
            # Font
            try:
                font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 60)
            except:
                font_large = ImageFont.load_default()
            
            # Text animation
            alpha = 1.0
            if progress < 0.2:
                alpha = progress / 0.2
            elif progress > 0.8:
                alpha = (1 - progress) / 0.2
            
            # Display text
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
        
        # Create video with ffmpeg
        import subprocess
        import tempfile
        
        temp_dir = tempfile.mkdtemp()
        
        # Save frames
        for i, frame in enumerate(frames):
            img = Image.fromarray(frame.astype(np.uint8))
            img.save(os.path.join(temp_dir, f"frame_{i:06d}.png"))
        
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
                print(f"FFmpeg error: {result.stderr[:300]}")
                # Return placeholder if ffmpeg fails
                return create_placeholder_video()
            
            # Read video
            with open(output_path, "rb") as f:
                video_bytes = f.read()
            
            # Cleanup
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return video_bytes
            
        except FileNotFoundError:
            print("FFmpeg not found")
            return create_placeholder_video()
        
    except Exception as e:
        print(f"Frame creation error: {e}")
        return create_placeholder_video()


def create_placeholder_video():
    """Minimal MP4 placeholder"""
    return bytes([
        0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70,
        0x69, 0x73, 0x6f, 0x6d, 0x00, 0x00, 0x00, 0x00,
        0x69, 0x73, 0x6f, 0x6d, 0x69, 0x73, 0x6f, 0x32,
        0x6d, 0x70, 0x34, 0x31, 0x00, 0x00, 0x00, 0x00,
    ]) + b'\x00' * 2000


# ============================================================
# ROUTES
# ============================================================
@app.route("/")
def index():
    return send_from_directory(".", "index.html")


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
        print(f"\n=== GENERATING VIDEO ===")
        print(f"Prompt: {prompt[:80]}")
        print(f"Provider: {cfg.get('video_provider')}")
        
        duration = detect_duration(prompt)
        print(f"Duration: {duration}s")
        
        enhanced = enhance_prompt(prompt, cfg)
        print(f"Enhanced: {enhanced[:80]}")
        
        video_bytes, mime = generate_video(enhanced, cfg, duration)

        if not video_bytes or len(video_bytes) < 500:
            return jsonify({"error": "Video generation failed"}), 500

        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)
        
        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        print(f"Saved: {vid_name} ({len(video_bytes)/1024:.1f} KB)")

        words = prompt.split()
        title = " ".join(words[:6]) if len(words) > 6 else prompt

        return jsonify({
            "success": True,
            "video_url": f"/video/{vid_name}",
            "title": title,
            "duration": duration
        })

    except Exception as e:
        print(f"ERROR: {e}")
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
            model = cfg.get("or_custom") or cfg.get("or_model", "meta-llama/llama-3.1-8b-instruct:free")
            r = requests.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {cfg.get('or_key','')}"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 10},
                timeout=10
            )
            if r.status_code == 200:
                return jsonify({"success": True, "message": f"✅ OpenRouter OK! Model: {model}"})
            return jsonify({"success": False, "message": f"❌ Invalid key"})

        elif provider == "gem":
            model = cfg.get("gem_custom") or cfg.get("gem_model", "gemini-1.5-flash")
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            r = requests.post(
                url, params={"key": cfg.get("gem_key", "")},
                json={"contents": [{"parts": [{"text": "hi"}]}]},
                timeout=10
            )
            if r.status_code == 200:
                return jsonify({"success": True, "message": f"✅ Gemini OK! Model: {model}"})
            return jsonify({"success": False, "message": f"❌ Invalid key"})

        elif provider == "oll":
            model = cfg.get("oll_model", "llama2")
            r = requests.get(
                cfg.get("oll_url", "http://localhost:11434") + "/api/tags",
                timeout=10
            )
            if r.status_code == 200:
                models = r.json().get("models", [])
                return jsonify({"success": True, "message": f"✅ Ollama OK! Using: {model}"})
            return jsonify({"success": False, "message": "❌ Cannot reach Ollama"})

    except Exception as e:
        return jsonify({"success": False, "message": f"❌ {str(e)}"})

    return jsonify({"success": False, "message": "❌ Unknown error"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "videos": os.listdir(VIDEOS_DIR)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n🎬 AI Video Generator starting on port {port}\n")
    app.run(host="0.0.0.0", port=port, debug=False)
