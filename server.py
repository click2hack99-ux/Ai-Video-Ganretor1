from flask import Flask, request, jsonify, send_from_directory, Response
from flask_cors import CORS
import requests
import json
import os
import uuid
import time
import base64

app = Flask(__name__)
CORS(app)

VIDEOS_DIR = "generated_videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)

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
.welcome p{color:#666;font-size:15px;max-width:420px;line-height:1.6;}
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
.vid-footer{padding:12px 16px;display:flex;align-items:center;justify-content:space-between;}
.vid-title{font-size:13px;color:#999;font-weight:500;}
.dl-btn{background:#4f46e5;color:#fff;border:none;padding:7px 14px;border-radius:7px;font-size:13px;cursor:pointer;text-decoration:none;display:inline-flex;align-items:center;gap:5px;transition:background 0.2s;}
.dl-btn:hover{background:#4338ca;}
.typing-wrap{display:flex;gap:12px;align-items:flex-start;margin-bottom:20px;}
.dots{display:flex;align-items:center;gap:5px;padding:14px;background:#141414;border-radius:10px;}
.dots span{width:8px;height:8px;background:#444;border-radius:50%;animation:bop 1.4s infinite ease-in-out;}
.dots span:nth-child(1){animation-delay:-0.32s;}
.dots span:nth-child(2){animation-delay:-0.16s;}
@keyframes bop{0%,80%,100%{transform:scale(0.7);background:#333;}40%{transform:scale(1);background:#7c3aed;}}
.prog-box{margin-top:10px;min-width:300px;}
.prog-bar{height:4px;background:#1e1e1e;border-radius:2px;overflow:hidden;margin-bottom:8px;}
.prog-fill{height:100%;background:linear-gradient(90deg,#7c3aed,#4f46e5);border-radius:2px;transition:width 0.6s ease;}
.steps{display:flex;flex-direction:column;gap:6px;}
.step{font-size:13px;color:#444;display:flex;align-items:center;gap:6px;transition:color 0.3s;}
.step.active{color:#8b5cf6;}
.step.done{color:#10b981;}
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
.section-label{font-size:11px;font-weight:700;color:#555;letter-spacing:1px;text-transform:uppercase;margin-bottom:12px;margin-top:20px;}
.divider{height:1px;background:#1e1e1e;margin:20px 0;}
.tabs{display:flex;background:#0a0a0a;border-radius:10px;padding:4px;margin-bottom:16px;gap:3px;}
.tab{flex:1;padding:7px;border:none;background:none;color:#666;border-radius:7px;cursor:pointer;font-size:12px;transition:all 0.2s;font-family:inherit;}
.tab.on{background:#4f46e5;color:#fff;}
.tab:hover:not(.on){background:#1a1a1a;color:#ccc;}
.panel{display:none;}
.panel.show{display:block;}
.fg{margin-bottom:14px;}
label{display:block;font-size:12px;color:#666;margin-bottom:5px;font-weight:500;}
input[type=text],input[type=password],select,textarea.form-ta{width:100%;background:#0a0a0a;border:1px solid #222;color:#eee;padding:10px 13px;border-radius:8px;font-size:14px;outline:none;transition:border-color 0.2s;font-family:inherit;}
input:focus,select:focus,textarea.form-ta:focus{border-color:#4f46e5;}
select option{background:#111;}
.note{font-size:12px;color:#555;margin-top:6px;line-height:1.5;padding:8px 10px;background:#0a0a0a;border-radius:6px;border-left:2px solid #333;}
.hf-badge{display:inline-flex;align-items:center;gap:4px;background:#1a1a2e;border:1px solid #2e2e5a;color:#818cf8;padding:4px 10px;border-radius:6px;font-size:12px;margin-bottom:12px;}
.m-foot{display:flex;gap:10px;margin-top:22px;}
.btn-test{flex:1;padding:10px;background:#0d0d0d;border:1px solid #2e2e2e;color:#aaa;border-radius:8px;cursor:pointer;font-size:14px;transition:all 0.2s;font-family:inherit;}
.btn-test:hover{background:#1a1a1a;color:#fff;}
.btn-save{flex:1;padding:10px;background:#4f46e5;border:none;color:#fff;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:background 0.2s;font-family:inherit;}
.btn-save:hover{background:#4338ca;}
.s-msg{text-align:center;font-size:13px;padding:9px;border-radius:7px;margin-top:12px;display:none;}
.s-msg.ok{background:#0a1f14;color:#34d399;border:1px solid #065f46;display:block;}
.s-msg.fail{background:#1f0a0a;color:#f87171;border:1px solid #7f1d1d;display:block;}
.s-msg.info{background:#0a0a1f;color:#818cf8;border:1px solid #312e81;display:block;}
.warn-box{background:#1a1500;border:1px solid #5a4a00;color:#fbbf24;padding:10px 14px;border-radius:8px;font-size:13px;margin-bottom:16px;line-height:1.5;}
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
      <p>Real AI-generated videos from your text prompts. Setup your API keys in Settings to get started.</p>
      <div class="chips">
        <div class="chip" onclick="useP(this)">A boy and girl hugging in a park</div>
        <div class="chip" onclick="useP(this)">Ocean waves crashing on beach at sunset</div>
        <div class="chip" onclick="useP(this)">City traffic at night with neon lights</div>
        <div class="chip" onclick="useP(this)">Snow falling in a quiet forest</div>
        <div class="chip" onclick="useP(this)">Rocket launching into space</div>
        <div class="chip" onclick="useP(this)">Flowers blooming in timelapse</div>
      </div>
    </div>
  </div>
</div>

<div class="input-area">
  <div class="input-wrap">
    <div class="input-box">
      <textarea id="inp" placeholder="Describe the video you want to generate..." rows="1"
        onkeydown="onKey(event)" oninput="resize(this)"></textarea>
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

    <!-- VIDEO GENERATION -->
    <div class="section-label">🎬 Video Generation API</div>
    <div class="warn-box">
      ⚡ Real AI video generation. Use any one provider below.
    </div>

    <div class="tabs">
      <button class="tab on" id="vtab-hf"   onclick="switchVTab('hf',this)">HuggingFace</button>
      <button class="tab"    id="vtab-rep"  onclick="switchVTab('rep',this)">Replicate</button>
      <button class="tab"    id="vtab-fal"  onclick="switchVTab('fal',this)">Fal.ai</button>
    </div>

    <!-- HuggingFace Panel -->
    <div class="panel show" id="vp-hf">
      <div class="hf-badge">🤗 Free Tier Available</div>
      <div class="fg">
        <label>HuggingFace API Token</label>
        <input type="password" id="hf-key" placeholder="hf_..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="hf-model">
          <option value="damo-vilab/text-to-video-ms-1.7b">DAMO Text-to-Video 1.7B (Free)</option>
          <option value="ali-vilab/i2vgen-xl">I2VGen-XL (Free)</option>
          <option value="cerspense/zeroscope_v2_576w">ZeroScope v2 576w (Free)</option>
          <option value="cerspense/zeroscope_v2_XL">ZeroScope v2 XL (Free)</option>
        </select>
      </div>
      <div class="note">
        Get free token: huggingface.co/settings/tokens<br>
        ⚠️ Free tier is slow (2-5 min). First request may take longer (cold start).
      </div>
    </div>

    <!-- Replicate Panel -->
    <div class="panel" id="vp-rep">
      <div class="fg">
        <label>Replicate API Token</label>
        <input type="password" id="rep-key" placeholder="r8_..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="rep-model">
          <option value="minimax/video-01">MiniMax Video-01 (Best Quality)</option>
          <option value="wan-ai/wan2.1-t2v-480p">Wan 2.1 480p</option>
          <option value="wan-ai/wan2.1-t2v-720p">Wan 2.1 720p</option>
          <option value="luma/ray">Luma Ray (Cinematic)</option>
          <option value="tencent/hunyuan-video">HunyuanVideo</option>
        </select>
      </div>
      <div class="note">
        Get token: replicate.com/account/api-tokens<br>
        ~$0.01-0.05 per video. New accounts get free credits.
      </div>
    </div>

    <!-- Fal.ai Panel -->
    <div class="panel" id="vp-fal">
      <div class="fg">
        <label>Fal.ai API Key</label>
        <input type="password" id="fal-key" placeholder="your-fal-key..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="fal-model">
          <option value="fal-ai/kling-video/v1.5/standard/text-to-video">Kling 1.5 Standard</option>
          <option value="fal-ai/kling-video/v1/standard/text-to-video">Kling 1.0</option>
          <option value="fal-ai/wan/v2.1/1.3b/text-to-video">Wan 2.1 1.3B (Fast)</option>
          <option value="fal-ai/hunyuan-video">HunyuanVideo</option>
          <option value="fal-ai/ltx-video">LTX Video (Fast)</option>
        </select>
      </div>
      <div class="note">
        Get key: fal.ai/dashboard/keys<br>
        Fast generation, good quality, pay per use.
      </div>
    </div>

    <div class="divider"></div>

    <!-- OPTIONAL AI TEXT -->
    <div class="section-label">🤖 AI Prompt Enhancer (Optional)</div>
    <div class="tabs">
      <button class="tab on" id="atab-none" onclick="switchATab('none',this)">None</button>
      <button class="tab" id="atab-or"   onclick="switchATab('or',this)">OpenRouter</button>
      <button class="tab" id="atab-gem"  onclick="switchATab('gem',this)">Gemini</button>
    </div>

    <div class="panel show" id="ap-none">
      <div class="note">No AI enhancer. Your prompt will be sent directly to video API.</div>
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
          <option value="mistralai/mistral-7b-instruct:free">Mistral 7B (Free)</option>
          <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
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
let cfg = JSON.parse(localStorage.getItem('aivid_cfg') || '{}');
let busy = false;
let curVTab = 'hf';
let curATab = 'none';

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
      document.getElementById('hf-model').value = cfg.hf_model || 'damo-vilab/text-to-video-ms-1.7b';
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
  const c = {};
  c.video_provider = curVTab;
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
  msg.className = 's-msg info'; msg.textContent = '⏳ Testing connection...';
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
  localStorage.setItem('aivid_cfg', JSON.stringify(cfg));
  updateDot(); closeM();
}

function useP(el) { document.getElementById('inp').value = el.textContent; resize(document.getElementById('inp')); send(); }
function onKey(e) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); } }
function resize(el) { el.style.height = 'auto'; el.style.height = Math.min(el.scrollHeight, 180) + 'px'; }

async function send() {
  const inp = document.getElementById('inp');
  const prompt = inp.value.trim();
  if (!prompt || busy) return;
  if (!cfg.video_provider) {
    alert('Please setup API keys in Settings first!');
    openM(); return;
  }
  document.getElementById('welcome').style.display = 'none';
  addUser(prompt);
  inp.value = ''; inp.style.height = 'auto';
  busy = true; document.getElementById('sendBtn').disabled = true;
  const tid = addTyping();
  try {
    const r = await fetch('/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt, cfg }),
      signal: AbortSignal.timeout(600000)
    });
    const d = await r.json();
    removeTyping(tid);
    if (d.success) addVideo(d);
    else addErr(d.error || 'Generation failed');
  } catch (e) {
    removeTyping(tid);
    addErr('Request failed or timed out: ' + e.message);
  }
  busy = false; document.getElementById('sendBtn').disabled = false;
}

function addUser(txt) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `<div class="message user-msg"><div class="user-bubble">${esc(txt)}</div></div>`;
  document.getElementById('chat').appendChild(w); scrollD();
}

function addTyping() {
  const id = 't' + Date.now();
  const w = document.createElement('div'); w.className = 'msg-row'; w.id = id;
  w.innerHTML = `
  <div class="typing-wrap">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="dots"><span></span><span></span><span></span></div>
      <div class="prog-box">
        <div class="prog-bar"><div class="prog-fill" id="pf${id}" style="width:0%"></div></div>
        <div class="steps">
          <div class="step active" id="s1${id}">🤖 Enhancing your prompt...</div>
          <div class="step" id="s2${id}">🎬 Sending to video AI...</div>
          <div class="step" id="s3${id}">⚙️ AI is generating video...</div>
          <div class="step" id="s4${id}">📥 Downloading & saving...</div>
        </div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w); scrollD();
  animProg(id); return id;
}

function animProg(id) {
  [[15,1,1000],[35,2,5000],[65,3,15000],[88,4,45000]].forEach(([pct,step,delay]) => {
    setTimeout(() => {
      const pf = document.getElementById('pf' + id); if (pf) pf.style.width = pct + '%';
      for (let i = 1; i <= 4; i++) {
        const el = document.getElementById('s' + i + id);
        if (el) el.className = 'step' + (i < step ? ' done' : i === step ? ' active' : '');
      }
    }, delay);
  });
}

function removeTyping(id) { const el = document.getElementById(id); if (el) el.remove(); }

function addVideo(d) {
  const w = document.createElement('div'); w.className = 'msg-row';
  w.innerHTML = `
  <div class="message ai-msg">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="ai-text">✅ Video ready! <strong>${esc(d.title || 'Generated Video')}</strong></div>
      <div class="vid-card">
        <video controls autoplay muted loop><source src="${d.video_url}" type="video/mp4"></video>
        <div class="vid-footer">
          <span class="vid-title">🎬 ${esc(d.title || 'AI Video')}</span>
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
# PROMPT ENHANCER (Optional AI)
# ============================================================
def enhance_prompt(prompt, cfg):
    ai_provider = cfg.get("ai_provider", "none")
    if ai_provider == "none" or not ai_provider:
        return prompt

    system = """You are a video generation prompt expert. 
Enhance the user's prompt to be more descriptive for AI video generation.
Return ONLY the enhanced prompt, nothing else. Max 200 words.
Make it cinematic, detailed, with camera angles, lighting, atmosphere."""

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
                "max_tokens": 300
            }
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers, json=data, timeout=30)
            return r.json()["choices"][0]["message"]["content"].strip()

        elif ai_provider == "gem":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{cfg.get('gem_model','gemini-1.5-flash')}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"maxOutputTokens": 300}
            }
            r = requests.post(url, params={"key": cfg.get("gem_key", "")}, json=data, timeout=30)
            return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()

    except Exception as e:
        print(f"Prompt enhance failed: {e}")

    return prompt


# ============================================================
# VIDEO GENERATION - HuggingFace
# ============================================================
def generate_hf(prompt, cfg):
    model = cfg.get("hf_model", "damo-vilab/text-to-video-ms-1.7b")
    token = cfg.get("hf_key", "")
    api_url = f"https://api-inference.huggingface.co/models/{model}"
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "inputs": prompt,
        "parameters": {
            "num_frames": 16,
            "num_inference_steps": 25,
            "guidance_scale": 7.5,
        }
    }

    print(f"HF request: {model}")
    max_retries = 3
    for attempt in range(max_retries):
        r = requests.post(api_url, headers=headers, json=payload, timeout=300)
        print(f"HF status: {r.status_code}")

        if r.status_code == 200:
            content_type = r.headers.get("content-type", "")
            if "video" in content_type or "octet-stream" in content_type or len(r.content) > 10000:
                return r.content, "video/mp4"
            # Try as JSON (some models return JSON with base64)
            try:
                data = r.json()
                if isinstance(data, list) and len(data) > 0:
                    if "blob" in data[0]:
                        return base64.b64decode(data[0]["blob"]), "video/mp4"
            except:
                pass
            return r.content, "video/mp4"

        elif r.status_code == 503:
            # Model loading
            try:
                wait = r.json().get("estimated_time", 30)
                wait = min(float(wait), 60)
            except:
                wait = 30
            print(f"Model loading, waiting {wait}s...")
            time.sleep(wait)

        elif r.status_code == 401:
            raise Exception("Invalid HuggingFace token")
        elif r.status_code == 429:
            time.sleep(20)
        else:
            raise Exception(f"HF API error {r.status_code}: {r.text[:200]}")

    raise Exception("HuggingFace: max retries exceeded, model may still be loading")


# ============================================================
# VIDEO GENERATION - Replicate
# ============================================================
def generate_replicate(prompt, cfg):
    token = cfg.get("rep_key", "")
    model = cfg.get("rep_model", "minimax/video-01")
    headers = {
        "Authorization": f"Token {token}",
        "Content-Type": "application/json"
    }

    # Create prediction
    payload = {"input": {"prompt": prompt}}

    # Model-specific params
    if "wan" in model:
        payload["input"].update({"num_frames": 81, "fps": 16})
    elif "minimax" in model:
        payload["input"].update({"duration": 5})
    elif "luma" in model:
        payload["input"].update({"duration": "5s", "aspect_ratio": "16:9"})
    elif "hunyuan" in model:
        payload["input"].update({"num_frames": 65, "fps": 24})

    print(f"Replicate model: {model}")
    r = requests.post(
        f"https://api.replicate.com/v1/models/{model}/predictions",
        headers=headers, json=payload, timeout=30
    )

    if r.status_code not in [200, 201]:
        # Try alternate endpoint
        r = requests.post(
            "https://api.replicate.com/v1/predictions",
            headers=headers,
            json={"version": model, "input": payload["input"]},
            timeout=30
        )

    if r.status_code not in [200, 201]:
        raise Exception(f"Replicate error {r.status_code}: {r.text[:300]}")

    prediction = r.json()
    pred_id = prediction.get("id")
    if not pred_id:
        raise Exception("No prediction ID from Replicate")

    # Poll for result
    print(f"Polling prediction: {pred_id}")
    for i in range(120):  # 10 min max
        time.sleep(5)
        poll = requests.get(
            f"https://api.replicate.com/v1/predictions/{pred_id}",
            headers=headers, timeout=30
        )
        data = poll.json()
        status = data.get("status")
        print(f"Status: {status}")

        if status == "succeeded":
            output = data.get("output")
            video_url = None
            if isinstance(output, str):
                video_url = output
            elif isinstance(output, list) and len(output) > 0:
                video_url = output[0]
            if video_url:
                vid_r = requests.get(video_url, timeout=120)
                return vid_r.content, "video/mp4"
            raise Exception("No video URL in output")

        elif status == "failed":
            raise Exception(f"Replicate failed: {data.get('error', 'Unknown error')}")

    raise Exception("Replicate timeout: prediction took too long")


# ============================================================
# VIDEO GENERATION - Fal.ai
# ============================================================
def generate_fal(prompt, cfg):
    api_key = cfg.get("fal_key", "")
    model = cfg.get("fal_model", "fal-ai/kling-video/v1.5/standard/text-to-video")

    headers = {
        "Authorization": f"Key {api_key}",
        "Content-Type": "application/json"
    }

    payload = {"prompt": prompt}

    # Model specific params
    if "kling" in model:
        payload.update({"duration": "5", "aspect_ratio": "16:9"})
    elif "wan" in model:
        payload.update({"num_frames": 81})
    elif "ltx" in model:
        payload.update({"num_frames": 97, "fps": 24})

    print(f"Fal.ai model: {model}")

    # Submit
    r = requests.post(
        f"https://queue.fal.run/{model}",
        headers=headers, json=payload, timeout=60
    )

    if r.status_code not in [200, 201]:
        raise Exception(f"Fal.ai error {r.status_code}: {r.text[:300]}")

    data = r.json()
    request_id = data.get("request_id")
    if not request_id:
        # Direct response
        output = data.get("video", {})
        if isinstance(output, dict):
            url = output.get("url")
        else:
            url = str(output)
        if url:
            vid_r = requests.get(url, timeout=120)
            return vid_r.content, "video/mp4"
        raise Exception("No request_id or video in response")

    # Poll
    print(f"Fal request_id: {request_id}")
    for i in range(120):
        time.sleep(5)
        poll = requests.get(
            f"https://queue.fal.run/{model}/requests/{request_id}/status",
            headers=headers, timeout=30
        )
        status_data = poll.json()
        status = status_data.get("status")
        print(f"Fal status: {status}")

        if status == "COMPLETED":
            result = requests.get(
                f"https://queue.fal.run/{model}/requests/{request_id}",
                headers=headers, timeout=30
            )
            out = result.json()
            video = out.get("video", {})
            url = video.get("url") if isinstance(video, dict) else str(video)
            if url:
                vid_r = requests.get(url, timeout=120)
                return vid_r.content, "video/mp4"
            raise Exception("No video URL in fal response")

        elif status in ["FAILED", "ERROR"]:
            raise Exception(f"Fal.ai failed: {status_data}")

    raise Exception("Fal.ai timeout")


# ============================================================
# MAIN GENERATE ROUTE
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
        return jsonify({"error": "No video API configured. Please setup in Settings."}), 400

    try:
        # Step 1: Enhance prompt
        enhanced = enhance_prompt(prompt, cfg)
        print(f"Original: {prompt}")
        print(f"Enhanced: {enhanced}")

        # Step 2: Generate video
        provider = cfg.get("video_provider")
        video_bytes = None

        if provider == "hf":
            video_bytes, mime = generate_hf(enhanced, cfg)
        elif provider == "rep":
            video_bytes, mime = generate_replicate(enhanced, cfg)
        elif provider == "fal":
            video_bytes, mime = generate_fal(enhanced, cfg)
        else:
            return jsonify({"error": f"Unknown provider: {provider}"}), 400

        if not video_bytes or len(video_bytes) < 1000:
            return jsonify({"error": "Video generation returned empty/invalid data"}), 500

        # Save video
        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)

        with open(vid_path, "wb") as f:
            f.write(video_bytes)

        print(f"Video saved: {vid_name} ({len(video_bytes)} bytes)")

        words = prompt.split()
        title = " ".join(words[:6]) if len(words) > 6 else prompt

        return jsonify({
            "success": True,
            "video_url": f"/video/{vid_name}",
            "title": title,
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
                return jsonify({"success": False, "message": "HuggingFace token missing"})
            r = requests.get("https://huggingface.co/api/whoami",
                             headers={"Authorization": f"Bearer {token}"}, timeout=10)
            if r.status_code == 200:
                name = r.json().get("name", "User")
                return jsonify({"success": True, "message": f"Connected as {name}!"})
            return jsonify({"success": False, "message": f"Invalid token (status {r.status_code})"})

        elif provider == "rep":
            token = cfg.get("rep_key", "")
            if not token:
                return jsonify({"success": False, "message": "Replicate token missing"})
            r = requests.get("https://api.replicate.com/v1/account",
                             headers={"Authorization": f"Token {token}"}, timeout=10)
            if r.status_code == 200:
                name = r.json().get("username", "User")
                return jsonify({"success": True, "message": f"Connected as {name}!"})
            return jsonify({"success": False, "message": f"Invalid token (status {r.status_code})"})

        elif provider == "fal":
            key = cfg.get("fal_key", "")
            if not key:
                return jsonify({"success": False, "message": "Fal.ai key missing"})
            return jsonify({"success": True, "message": "Fal.ai key saved (will verify on first generation)"})

    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

    return jsonify({"success": False, "message": "Unknown error"})


@app.route("/health")
def health():
    return jsonify({"status": "ok", "videos_dir": os.path.exists(VIDEOS_DIR)})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🎬 AI Video Generator starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
