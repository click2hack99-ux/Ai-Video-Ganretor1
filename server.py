from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import requests
import json
import os
import uuid
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import textwrap
import subprocess
import tempfile
import struct
import wave

app = Flask(__name__)
CORS(app)

VIDEOS_DIR = "generated_videos"
os.makedirs(VIDEOS_DIR, exist_ok=True)

# ============================================================
# FULL HTML FRONTEND
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
.welcome p{color:#666;font-size:15px;max-width:380px;line-height:1.6;}
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
.prog-box{margin-top:10px;}
.prog-bar{height:4px;background:#1e1e1e;border-radius:2px;overflow:hidden;margin-bottom:8px;}
.prog-fill{height:100%;background:linear-gradient(90deg,#7c3aed,#4f46e5);border-radius:2px;transition:width 0.6s ease;}
.steps{display:flex;flex-direction:column;gap:4px;}
.step{font-size:13px;color:#444;display:flex;align-items:center;gap:6px;transition:color 0.3s;}
.step.active{color:#8b5cf6;}
.step.done{color:#10b981;}
.err-box{background:#1a0808;border:1px solid #5a1a1a;color:#f87171;padding:12px 16px;border-radius:10px;font-size:14px;}
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
.modal{background:#111;border:1px solid #222;border-radius:18px;padding:26px;width:460px;max-width:95vw;animation:mIn 0.2s ease;}
@keyframes mIn{from{opacity:0;transform:scale(0.94);}to{opacity:1;transform:scale(1);}}
.m-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:22px;}
.m-title{font-size:17px;font-weight:600;}
.x-btn{background:none;border:none;color:#666;cursor:pointer;font-size:22px;line-height:1;transition:color 0.2s;}
.x-btn:hover{color:#fff;}
.tabs{display:flex;background:#0a0a0a;border-radius:10px;padding:4px;margin-bottom:20px;gap:3px;}
.tab{flex:1;padding:8px;border:none;background:none;color:#666;border-radius:7px;cursor:pointer;font-size:13px;transition:all 0.2s;font-family:inherit;}
.tab.on{background:#4f46e5;color:#fff;}
.tab:hover:not(.on){background:#1a1a1a;color:#ccc;}
.panel{display:none;}
.panel.show{display:block;}
.fg{margin-bottom:14px;}
label{display:block;font-size:12px;color:#666;margin-bottom:5px;font-weight:500;letter-spacing:0.3px;}
input[type=text],input[type=password],select{width:100%;background:#0a0a0a;border:1px solid #222;color:#eee;padding:10px 13px;border-radius:8px;font-size:14px;outline:none;transition:border-color 0.2s;font-family:inherit;}
input:focus,select:focus{border-color:#4f46e5;}
select option{background:#111;}
.note{font-size:12px;color:#444;margin-top:5px;line-height:1.4;}
.m-foot{display:flex;gap:10px;margin-top:22px;}
.btn-test{flex:1;padding:10px;background:#0d0d0d;border:1px solid #2e2e2e;color:#aaa;border-radius:8px;cursor:pointer;font-size:14px;transition:all 0.2s;font-family:inherit;}
.btn-test:hover{background:#1a1a1a;color:#fff;}
.btn-save{flex:1;padding:10px;background:#4f46e5;border:none;color:#fff;border-radius:8px;cursor:pointer;font-size:14px;font-weight:600;transition:background 0.2s;font-family:inherit;}
.btn-save:hover{background:#4338ca;}
.s-msg{text-align:center;font-size:13px;padding:9px;border-radius:7px;margin-top:12px;display:none;}
.s-msg.ok{background:#0a1f14;color:#34d399;border:1px solid #065f46;display:block;}
.s-msg.fail{background:#1f0a0a;color:#f87171;border:1px solid #7f1d1d;display:block;}
.s-msg.info{background:#0a0a1f;color:#818cf8;border:1px solid #312e81;display:block;}
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
      <span id="dotTxt">No API</span>
    </div>
    <button class="settings-btn" onclick="openM()">⚙️ Settings</button>
  </div>
</div>

<div class="chat-wrap" id="chat">
  <div class="msg-row">
    <div class="welcome" id="welcome">
      <div class="w-icon">🎬</div>
      <h1>AI Video Generator</h1>
      <p>Describe any video you want. AI will understand and generate it automatically.</p>
      <div class="chips">
        <div class="chip" onclick="useP(this)">A journey through space with nebulas</div>
        <div class="chip" onclick="useP(this)">Motivational video about success</div>
        <div class="chip" onclick="useP(this)">Peaceful nature documentary</div>
        <div class="chip" onclick="useP(this)">Tech product launch cinematic</div>
        <div class="chip" onclick="useP(this)">Cinematic story of a lone traveler</div>
        <div class="chip" onclick="useP(this)">Kids educational cartoon video</div>
      </div>
    </div>
  </div>
</div>

<div class="input-area">
  <div class="input-wrap">
    <div class="input-box">
      <textarea id="inp" placeholder="Describe the video you want to create..." rows="1"
        onkeydown="onKey(event)" oninput="resize(this)"></textarea>
      <button class="send-btn" id="sendBtn" onclick="send()">
        <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
    <div class="hint">Enter to send • Shift+Enter for new line</div>
  </div>
</div>

<div class="overlay" id="overlay" onclick="overlayClick(event)">
  <div class="modal">
    <div class="m-head">
      <div class="m-title">⚙️ API Settings</div>
      <button class="x-btn" onclick="closeM()">×</button>
    </div>
    <div class="tabs">
      <button class="tab on" onclick="switchTab('or',this)">OpenRouter</button>
      <button class="tab" onclick="switchTab('gem',this)">Gemini</button>
      <button class="tab" onclick="switchTab('oll',this)">Ollama</button>
    </div>
    <div class="panel show" id="p-or">
      <div class="fg">
        <label>API Key</label>
        <input type="password" id="or-key" placeholder="sk-or-v1-..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="or-model" onchange="orModelChange()">
          <option value="meta-llama/llama-3.1-8b-instruct:free">Llama 3.1 8B (Free)</option>
          <option value="meta-llama/llama-3.2-11b-vision-instruct:free">Llama 3.2 11B (Free)</option>
          <option value="google/gemma-2-9b-it:free">Gemma 2 9B (Free)</option>
          <option value="mistralai/mistral-7b-instruct:free">Mistral 7B (Free)</option>
          <option value="anthropic/claude-3-haiku">Claude 3 Haiku</option>
          <option value="openai/gpt-4o-mini">GPT-4o Mini</option>
          <option value="custom">Custom Model...</option>
        </select>
      </div>
      <div class="fg" id="or-cg" style="display:none;">
        <label>Custom Model ID</label>
        <input type="text" id="or-cm" placeholder="provider/model-name"/>
      </div>
    </div>
    <div class="panel" id="p-gem">
      <div class="fg">
        <label>API Key</label>
        <input type="password" id="gem-key" placeholder="AIza..."/>
      </div>
      <div class="fg">
        <label>Model</label>
        <select id="gem-model">
          <option value="gemini-1.5-flash">Gemini 1.5 Flash</option>
          <option value="gemini-1.5-pro">Gemini 1.5 Pro</option>
          <option value="gemini-pro">Gemini Pro</option>
        </select>
      </div>
    </div>
    <div class="panel" id="p-oll">
      <div class="fg">
        <label>Ollama Server URL</label>
        <input type="text" id="oll-url" value="http://localhost:11434"/>
      </div>
      <div class="fg">
        <label>Model Name</label>
        <input type="text" id="oll-model" placeholder="llama3, mistral, gemma2..."/>
      </div>
      <div class="note">Make sure Ollama is running locally with model pulled.</div>
    </div>
    <div class="s-msg" id="sMsg"></div>
    <div class="m-foot">
      <button class="btn-test" onclick="testAPI()">🔌 Test Connection</button>
      <button class="btn-save" onclick="saveS()">✓ Save Settings</button>
    </div>
  </div>
</div>

<script>
let cfg=JSON.parse(localStorage.getItem('aicfg')||'{}');
let busy=false,curTab='or';
window.onload=()=>{loadCfg();updateDot();};
function updateDot(){
  const d=document.getElementById('dot'),t=document.getElementById('dotTxt');
  if(cfg.provider){d.classList.add('on');t.textContent={openrouter:'OpenRouter',gemini:'Gemini',ollama:'Ollama'}[cfg.provider]||'Connected';}
  else{d.classList.remove('on');t.textContent='No API';}
}
function loadCfg(){
  if(!cfg.provider)return;
  const tab={openrouter:'or',gemini:'gem',ollama:'oll'}[cfg.provider];
  if(tab)switchTabById(tab);
  if(cfg.provider==='openrouter'){
    document.getElementById('or-key').value=cfg.api_key||'';
    const sel=document.getElementById('or-model');
    const opt=[...sel.options].find(o=>o.value===cfg.model);
    if(opt)sel.value=cfg.model;
    else{sel.value='custom';document.getElementById('or-cg').style.display='block';document.getElementById('or-cm').value=cfg.model||'';}
  }else if(cfg.provider==='gemini'){
    document.getElementById('gem-key').value=cfg.api_key||'';
    document.getElementById('gem-model').value=cfg.model||'gemini-1.5-flash';
  }else if(cfg.provider==='ollama'){
    document.getElementById('oll-url').value=cfg.ollama_url||'http://localhost:11434';
    document.getElementById('oll-model').value=cfg.model||'';
  }
}
function switchTab(id,btn){
  curTab=id;
  document.querySelectorAll('.tab').forEach(b=>b.classList.remove('on'));
  btn.classList.add('on');
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('show'));
  document.getElementById('p-'+id).classList.add('show');
  document.getElementById('sMsg').className='s-msg';
}
function switchTabById(id){
  curTab=id;
  const tabs=document.querySelectorAll('.tab');
  const map={or:0,gem:1,oll:2};
  tabs.forEach((b,i)=>b.classList.toggle('on',i===map[id]));
  document.querySelectorAll('.panel').forEach(p=>p.classList.remove('show'));
  document.getElementById('p-'+id).classList.add('show');
}
function orModelChange(){
  document.getElementById('or-cg').style.display=document.getElementById('or-model').value==='custom'?'block':'none';
}
function getCfg(){
  if(curTab==='or'){
    let m=document.getElementById('or-model').value;
    if(m==='custom')m=document.getElementById('or-cm').value;
    return{provider:'openrouter',api_key:document.getElementById('or-key').value,model:m};
  }else if(curTab==='gem'){
    return{provider:'gemini',api_key:document.getElementById('gem-key').value,model:document.getElementById('gem-model').value};
  }else{
    return{provider:'ollama',ollama_url:document.getElementById('oll-url').value,model:document.getElementById('oll-model').value};
  }
}
function openM(){document.getElementById('overlay').classList.add('show');loadCfg();}
function closeM(){document.getElementById('overlay').classList.remove('show');document.getElementById('sMsg').className='s-msg';}
function overlayClick(e){if(e.target.id==='overlay')closeM();}
async function testAPI(){
  const msg=document.getElementById('sMsg');
  msg.className='s-msg info';msg.textContent='⏳ Testing...';
  try{
    const r=await fetch('/test-api',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({api_config:getCfg()})});
    const d=await r.json();
    msg.className='s-msg '+(d.success?'ok':'fail');
    msg.textContent=(d.success?'✅ ':'❌ ')+d.message;
  }catch(e){msg.className='s-msg fail';msg.textContent='❌ Cannot reach server.';}
}
function saveS(){cfg=getCfg();localStorage.setItem('aicfg',JSON.stringify(cfg));updateDot();closeM();}
function useP(el){document.getElementById('inp').value=el.textContent;resize(document.getElementById('inp'));send();}
function onKey(e){if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send();}}
function resize(el){el.style.height='auto';el.style.height=Math.min(el.scrollHeight,180)+'px';}
async function send(){
  const inp=document.getElementById('inp');
  const prompt=inp.value.trim();
  if(!prompt||busy)return;
  document.getElementById('welcome').style.display='none';
  addUser(prompt);
  inp.value='';inp.style.height='auto';
  busy=true;document.getElementById('sendBtn').disabled=true;
  const tid=addTyping();
  try{
    const r=await fetch('/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({prompt,api_config:cfg})});
    const d=await r.json();
    removeTyping(tid);
    if(d.success)addVideo(d);else addErr(d.error||'Generation failed');
  }catch(e){removeTyping(tid);addErr('Server error. Is server.py running?');}
  busy=false;document.getElementById('sendBtn').disabled=false;
}
function addUser(txt){
  const w=document.createElement('div');w.className='msg-row';
  w.innerHTML=`<div class="message user-msg"><div class="user-bubble">${esc(txt)}</div></div>`;
  document.getElementById('chat').appendChild(w);scrollD();
}
function addTyping(){
  const id='t'+Date.now();
  const w=document.createElement('div');w.className='msg-row';w.id=id;
  w.innerHTML=`
  <div class="typing-wrap">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="dots"><span></span><span></span><span></span></div>
      <div class="prog-box">
        <div class="prog-bar"><div class="prog-fill" id="pf${id}" style="width:0%"></div></div>
        <div class="steps">
          <div class="step active" id="s1${id}">🤖 Analyzing prompt with AI...</div>
          <div class="step" id="s2${id}">🎨 Designing scenes & colors...</div>
          <div class="step" id="s3${id}">🎬 Rendering video frames...</div>
          <div class="step" id="s4${id}">🎵 Adding audio narration...</div>
        </div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w);scrollD();
  animProg(id);return id;
}
function animProg(id){
  [[20,1,800],[45,2,4000],[72,3,8000],[90,4,13000]].forEach(([pct,step,delay])=>{
    setTimeout(()=>{
      const pf=document.getElementById('pf'+id);if(pf)pf.style.width=pct+'%';
      for(let i=1;i<=4;i++){
        const el=document.getElementById('s'+i+id);
        if(el)el.className='step'+(i<step?' done':i===step?' active':'');
      }
    },delay);
  });
}
function removeTyping(id){const el=document.getElementById(id);if(el)el.remove();}
function addVideo(d){
  const w=document.createElement('div');w.className='msg-row';
  w.innerHTML=`
  <div class="message ai-msg">
    <div class="ai-av">🎬</div>
    <div class="ai-body">
      <div class="ai-text">✅ Your video is ready! <strong>${esc(d.title)}</strong> — ${d.scenes} scenes generated.</div>
      <div class="vid-card">
        <video controls autoplay muted loop><source src="${d.video_url}" type="video/mp4"></video>
        <div class="vid-footer">
          <span class="vid-title">🎬 ${esc(d.title)}</span>
          <a href="${d.video_url}" download class="dl-btn">⬇ Download</a>
        </div>
      </div>
    </div>
  </div>`;
  document.getElementById('chat').appendChild(w);scrollD();
}
function addErr(msg){
  const w=document.createElement('div');w.className='msg-row';
  w.innerHTML=`
  <div class="message ai-msg">
    <div class="ai-av">🎬</div>
    <div class="ai-body"><div class="err-box">⚠️ ${esc(msg)}</div></div>
  </div>`;
  document.getElementById('chat').appendChild(w);scrollD();
}
function scrollD(){const c=document.getElementById('chat');setTimeout(()=>c.scrollTop=c.scrollHeight,100);}
function esc(t){const d=document.createElement('div');d.textContent=t;return d.innerHTML;}
</script>
</body>
</html>'''


# ============================================================
# AI RESPONSE
# ============================================================
def get_ai_response(prompt, api_config):
    provider = api_config.get("provider", "")
    api_key = api_config.get("api_key", "")
    model = api_config.get("model", "")

    system_prompt = """You are an AI video script generator. Based on the user prompt, return ONLY valid JSON, no extra text.
JSON structure:
{
  "title": "Short video title max 5 words",
  "scenes": [
    {
      "duration": 4,
      "text": "Short text max 5 words",
      "subtitle": "Supporting line max 8 words",
      "bg_color": [R, G, B],
      "text_color": [R, G, B],
      "animation": "fade"
    }
  ]
}
Rules:
- 5 to 7 scenes total
- animation: fade, slide, zoom, or typewriter only
- Colors must match theme/mood
- text_color must contrast well with bg_color
- Keep all text SHORT"""

    try:
        if provider == "gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model or 'gemini-1.5-flash'}:generateContent"
            data = {
                "contents": [{"parts": [{"text": f"{system_prompt}\n\nPrompt: {prompt}"}]}],
                "generationConfig": {"temperature": 0.8, "maxOutputTokens": 2048}
            }
            r = requests.post(url, params={"key": api_key}, json=data, timeout=60)
            text = r.json()["candidates"][0]["content"]["parts"][0]["text"]

        elif provider == "ollama":
            url = api_config.get("ollama_url", "http://localhost:11434") + "/api/generate"
            r = requests.post(url, json={
                "model": model or "llama3",
                "prompt": f"{system_prompt}\n\nPrompt: {prompt}",
                "stream": False
            }, timeout=180)
            text = r.json()["response"]

        else:  # openrouter default
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://aivideogen.onrender.com",
                "X-Title": "AI Video Generator"
            }
            data = {
                "model": model or "meta-llama/llama-3.1-8b-instruct:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 2048
            }
            r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                              headers=headers, json=data, timeout=60)
            text = r.json()["choices"][0]["message"]["content"]

        s = text.find("{")
        e = text.rfind("}") + 1
        if s != -1 and e > 0:
            return json.loads(text[s:e])
        raise Exception("No JSON found")

    except Exception as ex:
        print(f"AI Error: {ex}")
        return fallback_scenes(prompt)


def fallback_scenes(prompt):
    words = prompt.split()
    title = " ".join(words[:5]) if len(words) > 5 else prompt
    return {
        "title": title,
        "scenes": [
            {"duration": 4, "text": title[:35], "subtitle": "AI Generated Video",
             "bg_color": [8, 8, 22], "text_color": [255, 255, 255], "animation": "fade"},
            {"duration": 4, "text": "Your Vision", "subtitle": prompt[:45],
             "bg_color": [12, 8, 32], "text_color": [180, 140, 255], "animation": "zoom"},
            {"duration": 4, "text": "Comes Alive", "subtitle": "Powered by AI",
             "bg_color": [5, 12, 28], "text_color": [100, 200, 255], "animation": "slide"},
            {"duration": 3, "text": "Thank You", "subtitle": title[:28],
             "bg_color": [8, 8, 18], "text_color": [255, 200, 100], "animation": "fade"},
        ]
    }


# ============================================================
# FRAME CREATOR - Pure PIL only
# ============================================================
def create_frame(scene, frame_num, total_frames, W=1280, H=720):
    bg = tuple(int(c) for c in scene.get("bg_color", [8, 8, 22]))
    tc = tuple(int(c) for c in scene.get("text_color", [255, 255, 255]))
    anim = scene.get("animation", "fade")
    prog = frame_num / max(total_frames - 1, 1)

    img = Image.new("RGB", (W, H), bg)
    draw = ImageDraw.Draw(img)

    # Gradient BG
    for y in range(H):
        ratio = y / H
        r = max(0, min(255, int(bg[0] + (tc[0] - bg[0]) * ratio * 0.08)))
        g = max(0, min(255, int(bg[1] + (tc[1] - bg[1]) * ratio * 0.08)))
        b = max(0, min(255, int(bg[2] + (tc[2] - bg[2]) * ratio * 0.12)))
        draw.line([(0, y), (W, y)], fill=(r, g, b))

    ac = tuple(min(255, int(c * 0.5 + 80)) for c in tc)

    # Borders
    draw.rectangle([0, 0, W, 4], fill=tc)
    draw.rectangle([0, H - 4, W, H], fill=tc)

    # Corner brackets
    for px, py in [(15, 15), (W - 55, 15), (15, H - 55), (W - 55, H - 55)]:
        draw.rectangle([px, py, px + 40, py + 3], fill=ac)
        draw.rectangle([px, py, px + 3, py + 40], fill=ac)

    # Fonts
    font_paths = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    ]
    fl = fm = ImageFont.load_default()
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                fl = ImageFont.truetype(fp, 72)
                fm = ImageFont.truetype(fp, 36)
                break
            except:
                continue

    main_txt = str(scene.get("text", ""))
    sub_txt = str(scene.get("subtitle", ""))

    # Animation
    alpha = 1.0
    ox, oy = 0, 0

    if anim == "fade":
        if prog < 0.2:
            alpha = prog / 0.2
        elif prog > 0.75:
            alpha = (1.0 - prog) / 0.25

    elif anim == "slide":
        if prog < 0.25:
            ox = int(-260 * (1 - prog / 0.25))
            alpha = prog / 0.25
        elif prog > 0.75:
            ox = int(260 * ((prog - 0.75) / 0.25))
            alpha = (1.0 - prog) / 0.25

    elif anim == "zoom":
        if prog < 0.25:
            alpha = prog / 0.25
        elif prog > 0.8:
            alpha = (1.0 - prog) / 0.2

    elif anim == "typewriter":
        chars = int(len(main_txt) * min(prog * 2.5, 1.0))
        main_txt = main_txt[:max(1, chars)]
        if prog > 0.8:
            alpha = (1.0 - prog) / 0.2

    alpha = max(0.01, min(1.0, alpha))

    # Draw main text
    lines = textwrap.wrap(main_txt, width=20)
    if not lines:
        lines = [main_txt[:20]]

    line_h = 90
    total_h = len(lines) * line_h
    sy = (H - total_h) // 2 - 30 + oy

    for i, line in enumerate(lines):
        try:
            bb = draw.textbbox((0, 0), line, font=fl)
            tw = bb[2] - bb[0]
        except:
            tw = len(line) * 40

        x = max(40, (W - tw) // 2 + ox)
        y = sy + i * line_h

        # Shadow
        sc = tuple(max(0, int(c * 0.2 * alpha)) for c in tc)
        draw.text((x + 4, y + 4), line, font=fl, fill=sc)

        # Main text
        draw.text((x, y), line, font=fl,
                  fill=tuple(max(0, min(255, int(c * alpha))) for c in tc))

    # Subtitle
    if sub_txt:
        disp = sub_txt[:60]
        try:
            bb = draw.textbbox((0, 0), disp, font=fm)
            sw = bb[2] - bb[0]
        except:
            sw = len(disp) * 20

        sx2 = max(20, (W - sw) // 2)
        sy2 = sy + len(lines) * line_h + 25
        sub_col = tuple(max(0, min(255, int(c * 0.75 * alpha))) for c in ac)
        draw.text((sx2, sy2), disp, font=fm, fill=sub_col)

    # Bottom progress bar
    bar_w = max(1, int(W * prog))
    bar_col = tuple(max(0, min(255, int(c * 0.55))) for c in tc)
    draw.rectangle([0, H - 18, bar_w, H - 14], fill=bar_col)

    return np.array(img)


# ============================================================
# VIDEO GENERATOR - imageio + ffmpeg
# ============================================================
def generate_video(scene_data, out_path):
    try:
        import imageio
        import imageio_ffmpeg

        fps = 24
        ffmpeg_path = imageio_ffmpeg.get_ffmpeg_exe()

        # Generate all frames as temp images
        frames_dir = out_path + "_frames"
        os.makedirs(frames_dir, exist_ok=True)

        frame_count = 0
        frame_list_path = os.path.join(frames_dir, "frames.txt")

        # Write frames
        for scene in scene_data["scenes"]:
            dur = int(scene.get("duration", 4))
            total_f = dur * fps

            for f in range(total_f):
                arr = create_frame(scene, f, total_f)
                img = Image.fromarray(arr.astype(np.uint8))
                frame_path = os.path.join(frames_dir, f"frame_{frame_count:06d}.jpg")
                img.save(frame_path, quality=85)
                frame_count += 1

        # Use ffmpeg to create video from frames
        cmd = [
            ffmpeg_path,
            "-y",
            "-framerate", str(fps),
            "-i", os.path.join(frames_dir, "frame_%06d.jpg"),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-crf", "23",
            "-preset", "fast",
            out_path
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if result.returncode != 0:
            print(f"FFmpeg error: {result.stderr}")
            raise Exception(f"FFmpeg failed: {result.stderr[-500:]}")

        # Try adding audio
        try:
            from gtts import gTTS
            all_text = ". ".join(
                sc.get("text", "") + " " + sc.get("subtitle", "")
                for sc in scene_data["scenes"]
            )[:500]

            audio_path = out_path + ".mp3"
            gTTS(text=all_text, lang='en', slow=False).save(audio_path)

            out_with_audio = out_path.replace(".mp4", "_final.mp4")
            audio_cmd = [
                ffmpeg_path,
                "-y",
                "-i", out_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                out_with_audio
            ]
            ar = subprocess.run(audio_cmd, capture_output=True, text=True, timeout=120)
            if ar.returncode == 0 and os.path.exists(out_with_audio):
                os.replace(out_with_audio, out_path)
            if os.path.exists(audio_path):
                os.remove(audio_path)
        except Exception as ae:
            print(f"Audio skipped: {ae}")

        # Cleanup frames
        try:
            import shutil
            shutil.rmtree(frames_dir, ignore_errors=True)
        except:
            pass

        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000

    except Exception as e:
        print(f"Video generation error: {e}")
        import traceback
        traceback.print_exc()
        return False


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
    api_cfg = data.get("api_config", {})

    if not prompt:
        return jsonify({"error": "Prompt required"}), 400

    try:
        print(f"Generating video for: {prompt[:60]}")
        scene_data = get_ai_response(prompt, api_cfg)
        print(f"Scenes: {len(scene_data.get('scenes', []))}")

        vid_id = str(uuid.uuid4())[:8]
        vid_name = f"vid_{vid_id}.mp4"
        vid_path = os.path.join(VIDEOS_DIR, vid_name)

        ok = generate_video(scene_data, vid_path)
        print(f"Video generated: {ok}, exists: {os.path.exists(vid_path)}")

        if ok:
            return jsonify({
                "success": True,
                "video_url": f"/video/{vid_name}",
                "title": scene_data.get("title", "Generated Video"),
                "scenes": len(scene_data.get("scenes", []))
            })

        return jsonify({"error": "Video render failed. Check server logs."}), 500

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/video/<fname>")
def serve_video(fname):
    return send_from_directory(VIDEOS_DIR, fname)


@app.route("/test-api", methods=["POST"])
def test_api():
    cfg = request.json.get("api_config", {})
    try:
        res = get_ai_response("simple 2 scene video about stars", cfg)
        if res and "scenes" in res:
            return jsonify({"success": True, "message": "Connected successfully!"})
        return jsonify({"success": False, "message": "Invalid API response"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})


@app.route("/health")
def health():
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        ffmpeg_ok = os.path.exists(ffmpeg)
    except:
        ffmpeg_ok = False
    return jsonify({
        "status": "ok",
        "ffmpeg": ffmpeg_ok,
        "videos_dir": os.path.exists(VIDEOS_DIR)
    })


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
