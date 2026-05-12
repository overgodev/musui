// ══════════════════════════════════════════════════════════════
//  VTube AI — Renderer Process (app.js)
// ══════════════════════════════════════════════════════════════

// ── State ─────────────────────────────────────────────────────
const state = {
  currentPanel: 'chat',
  personas: [],
  currentPersona: null,
  chatHistory: [],
  ttsEnabled: false,
  vtubeConnected: false,
  vtubeAuthenticated: false,
  lmConnected: false,
  isSpeaking: false,
  availableHotkeys: [], // hotkeys from VTube Studio
  settings: {
    lmUrl: 'http://localhost:1234',
    lmApiKey: '',
    lmTemp: 0.8,
    lmMaxTokens: 512,
    vtubeUrl: 'ws://localhost:8001',
    vtubeAutoEmo: true,
    vtubeAutoMove: true,
    ttsEngine: 'system',
    ttsVoice: '',
    ttsRate: 1.0,
    vitsUrl: '',
    vitsSpeaker: 0,
    pthPath: '',
    cfgPath: '',
    aiLang: 'th',
    aiMemory: 10,
    aiEmoDetect: true,
    selectedModel: '',
  },
};

// ── Emotion → keyword mapping ─────────────────────────────────
const emotionKeywords = {
  happy:   ['ดีใจ','ยินดี','สนุก','เฮ','ฮ่า','555','haha','happy','joy','glad','やった','嬉しい'],
  excited: ['ตื่นเต้น','ว้าว','เยี่ยม','สุดยอด','wow','amazing','excited','すごい','わあ'],
  love:    ['รัก','น่ารัก','ชอบมาก','หัวใจ','❤','💕','love','かわいい','好き'],
  sad:     ['เศร้า','เสียใจ','น้ำตา','เสียดาย','sad','cry','sorry','悲しい','ごめん'],
  angry:   ['โกรธ','หัวร้อน','น่าหงุดหน่าย','angry','mad','怒','むかつく'],
  surprise:['ทำไม','แปลก','ตกใจ','เอ๊ะ','oh','what','surprised','えっ','まじ'],
  shy:     ['อาย','หน้าแดง','ขอโทษ','shy','embarrassed','はずかしい'],
  cool:    ['เท่','แน่','cool','awesome','เจ๋ง','かっこいい'],
};

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', async () => {
  initChatElements();
  document.getElementById('welcome-time').textContent = formatTime(new Date());
  await loadSettings();
  renderPersonaList();
  applySettingsToUI();
  loadVoices();

  // VTube Studio events
  api.onVtubeStatus((data) => {
    state.vtubeConnected = data.connected;
    state.vtubeAuthenticated = data.authenticated;
    updateVtubeStatusUI();
    if (data.connected && data.authenticated) {
      log('VTube Studio: เชื่อมต่อและ authenticated สำเร็จ ✅');
      setTimeout(loadHotkeys, 500);
    }
  });

  // Auto-load models if URL is set
  if (state.settings.lmUrl) setTimeout(refreshModels, 800);
});

// ── Panel switching ───────────────────────────────────────────
function switchPanel(panel, btn) {
  document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(`panel-${panel}`).classList.add('active');
  btn.classList.add('active');
  state.currentPanel = panel;
  if (panel === 'persona') renderPersonaList();
}

// ── Toast notifications ───────────────────────────────────────
function toast(msg, type = 'info', duration = 3000) {
  const c = document.getElementById('toast-container');
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  t.innerHTML = `<span>${type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️'}</span> ${msg}`;
  c.appendChild(t);
  setTimeout(() => { t.style.animation = 'none'; t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, duration);
}

function log(msg) {
  const el = document.getElementById('debug-log');
  const time = formatTime(new Date());
  el.textContent = `[${time}] ${msg}\n` + el.textContent;
  document.getElementById('status-log').textContent = msg;
}

function formatTime(d) {
  return d.toLocaleTimeString('th-TH', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

// ── Settings ──────────────────────────────────────────────────
async function loadSettings() {
  const res = await api.settingsLoad();
  if (res.success && res.data) {
    Object.assign(state.settings, res.data);
    if (res.data.personas) state.personas = res.data.personas;
    if (res.data.currentPersonaIdx !== undefined) {
      state.currentPersona = state.personas[res.data.currentPersonaIdx] || null;
      updatePersonaDisplay();
    }
  }
}

async function saveSettings() {
  collectSettingsFromUI();
  const data = {
    ...state.settings,
    personas: state.personas,
    currentPersonaIdx: state.currentPersona ? state.personas.indexOf(state.currentPersona) : -1,
  };
  const res = await api.settingsSave(data);
  if (res.success) toast('บันทึกการตั้งค่าแล้ว ✨', 'success');
  else toast('บันทึกไม่สำเร็จ: ' + res.error, 'error');
}

async function saveQuickSettings() {
  state.settings.selectedModel = document.getElementById('model-select').value;
  await api.settingsSave({ ...state.settings, personas: state.personas });
}

function collectSettingsFromUI() {
  state.settings.lmUrl = document.getElementById('lm-url').value.trim().replace(/\/$/, '');
  state.settings.lmApiKey = document.getElementById('lm-apikey').value.trim();
  state.settings.lmTemp = parseFloat(document.getElementById('lm-temp').value);
  state.settings.lmMaxTokens = parseInt(document.getElementById('lm-maxtok').value);
  state.settings.vtubeUrl = document.getElementById('vtube-url').value.trim();
  state.settings.vtubeAutoEmo = document.getElementById('vtube-auto-emo').value === '1';
  state.settings.vtubeAutoMove = document.getElementById('vtube-auto-move').value === '1';
  state.settings.ttsEngine = document.getElementById('tts-engine').value;
  state.settings.ttsVoice = document.getElementById('tts-voice').value;
  state.settings.ttsRate = parseFloat(document.getElementById('tts-rate').value);
  state.settings.vitsUrl = document.getElementById('vits-url').value.trim();
  state.settings.vitsSpeaker = parseInt(document.getElementById('vits-speaker').value);
  state.settings.aiLang = document.getElementById('ai-lang').value;
  state.settings.aiMemory = parseInt(document.getElementById('ai-memory').value);
  state.settings.aiEmoDetect = document.getElementById('ai-emo-detect').value === '1';
  state.settings.selectedModel = document.getElementById('model-select').value;
}

function applySettingsToUI() {
  const s = state.settings;
  setVal('lm-url', s.lmUrl || 'http://localhost:1234');
  setVal('lm-apikey', s.lmApiKey || '');
  setVal('lm-temp', s.lmTemp || 0.8);
  document.getElementById('lm-temp-val').textContent = s.lmTemp || 0.8;
  setVal('lm-maxtok', s.lmMaxTokens || 512);
  document.getElementById('lm-maxtok-val').textContent = s.lmMaxTokens || 512;
  setVal('vtube-url', s.vtubeUrl || 'ws://localhost:8001');
  setVal('vtube-auto-emo', s.vtubeAutoEmo ? '1' : '0');
  setVal('vtube-auto-move', s.vtubeAutoMove ? '1' : '0');
  setVal('tts-engine', s.ttsEngine || 'system');
  setVal('tts-rate', s.ttsRate || 1.0);
  document.getElementById('tts-rate-val').textContent = (s.ttsRate || 1.0) + 'x';
  setVal('vits-url', s.vitsUrl || '');
  setVal('vits-speaker', s.vitsSpeaker || 0);
  setVal('pth-path', s.pthPath || '');
  setVal('cfg-path', s.cfgPath || '');
  setVal('ai-lang', s.aiLang || 'th');
  setVal('ai-memory', s.aiMemory || 10);
  document.getElementById('ai-memory-val').textContent = s.aiMemory || 10;
  setVal('ai-emo-detect', s.aiEmoDetect ? '1' : '0');
  if (s.pthPath) document.getElementById('pth-display').textContent = s.pthPath.split(/[\\/]/).pop();
  updateTTSStatus();
}

function setVal(id, val) {
  const el = document.getElementById(id);
  if (el) el.value = val;
}

// ── LM Studio ─────────────────────────────────────────────────
async function testLMStudio() {
  const url = document.getElementById('lm-url').value.trim().replace(/\/$/, '');
  if (!url) return toast('กรุณาใส่ URL ก่อน', 'error');
  log(`กำลังทดสอบ LM Studio: ${url}`);
  setLMStatus('loading');
  const res = await api.lmGetModels({ apiUrl: url });
  if (res.success) {
    state.settings.lmUrl = url;
    state.lmConnected = true;
    setLMStatus('ok');
    toast(`เชื่อมต่อ LM Studio สำเร็จ พบ ${res.models.length} model`, 'success');
    log(`LM Studio: พบ ${res.models.length} models`);
    populateModels(res.models);
  } else {
    state.lmConnected = false;
    setLMStatus('err');
    toast('เชื่อมต่อ LM Studio ไม่สำเร็จ: ' + res.error, 'error');
    log('LM Studio error: ' + res.error);
  }
}

async function refreshModels() {
  const url = (document.getElementById('lm-url')?.value || state.settings.lmUrl || '').trim().replace(/\/$/, '');
  if (!url) return;
  const res = await api.lmGetModels({ apiUrl: url });
  if (res.success) {
    state.lmConnected = true;
    setLMStatus('ok');
    populateModels(res.models);
  } else {
    state.lmConnected = false;
    setLMStatus('err');
  }
}

function populateModels(models) {
  const sel = document.getElementById('model-select');
  const prev = sel.value;
  sel.innerHTML = '<option value="">-- เลือก model --</option>';
  models.forEach(m => {
    const opt = document.createElement('option');
    opt.value = m.id;
    opt.textContent = m.id;
    sel.appendChild(opt);
  });
  if (prev) sel.value = prev;
  else if (state.settings.selectedModel) sel.value = state.settings.selectedModel;
  else if (models.length) sel.value = models[0].id;
}

function setLMStatus(status) {
  const dot = document.getElementById('dot-lm');
  const val = document.getElementById('val-lm');
  const badge = document.getElementById('badge-lm');
  if (status === 'ok') {
    dot.className = 'status-dot on';
    val.textContent = 'เชื่อมต่อแล้ว'; val.className = 'val ok';
    badge.textContent = 'เชื่อมต่อแล้ว'; badge.className = 'card-badge badge-connected';
  } else if (status === 'loading') {
    dot.className = 'status-dot loading';
    val.textContent = 'กำลังเชื่อมต่อ...'; val.className = 'val';
  } else {
    dot.className = 'status-dot off';
    val.textContent = 'ไม่ได้เชื่อมต่อ'; val.className = 'val err';
    badge.textContent = 'ไม่ได้เชื่อมต่อ'; badge.className = 'card-badge badge-disconnected';
  }
}

// ── Chat ──────────────────────────────────────────────────────
let chatMessages = null;
let chatInput = null;
let btnSend = null;
let isGenerating = false;

function initChatElements() {
  chatMessages = document.getElementById('chat-messages');
  chatInput    = document.getElementById('chat-input');
  btnSend      = document.getElementById('btn-send');
  chatInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  });
  chatInput.addEventListener('input', () => {
    chatInput.style.height = 'auto';
    chatInput.style.height = Math.min(chatInput.scrollHeight, 140) + 'px';
  });
}

async function sendMessage() {
  if (isGenerating) return;
  const text = chatInput.value.trim();
  if (!text) return;

  // Always read current input value first, fallback to saved setting
  const lmInput = document.getElementById('lm-url');
  const url = (lmInput ? lmInput.value.trim() : '') || state.settings.lmUrl || '';
  if (!url) return toast('กรุณาตั้งค่า LM Studio URL ก่อน', 'error');
  // Keep state in sync
  if (url) state.settings.lmUrl = url.replace(/\/$/, '');

  chatInput.value = '';
  chatInput.style.height = 'auto';

  // Add user message
  appendMessage('user', text);
  state.chatHistory.push({ role: 'user', content: text });

  // Trim history
  const maxMem = state.settings.aiMemory || 10;
  if (state.chatHistory.length > maxMem * 2) {
    state.chatHistory = state.chatHistory.slice(-maxMem * 2);
  }

  setGenerating(true);

  // Build system prompt
  const systemPrompt = buildSystemPrompt();

  // Add typing indicator
  const typingId = 'typing-' + Date.now();
  appendTyping(typingId);

  // Call LM Studio
  const model = document.getElementById('model-select').value;
  const messages = [...state.chatHistory];
  const res = await api.lmChat({
    apiUrl: url,
    messages,
    systemPrompt,
    model: model || undefined,
    temperature: state.settings.lmTemp || 0.8,
    maxTokens: state.settings.lmMaxTokens || 512,
  });

  removeTyping(typingId);
  setGenerating(false);

  if (res.success) {
    let aiText = res.text.trim();
    let chosenHotkeyId = null;

    // Parse JSON response when hotkeys are active
    if (state.vtubeConnected && state.availableHotkeys.length > 0) {
      try {
        // Strip markdown code fences if model wraps in them
        const clean = aiText.replace(/^```json\s*/i, '').replace(/^```\s*/i, '').replace(/\s*```$/i, '').trim();
        const parsed = JSON.parse(clean);
        if (parsed.text) {
          aiText = parsed.text.trim();
          chosenHotkeyId = parsed.hotkey || null;
        }
      } catch (e) {
        // Model didn't return JSON — use raw text, fall back to keyword detection
        log('VTube: AI ไม่ได้ตอบเป็น JSON ใช้ keyword detection แทน');
      }
    }

    state.chatHistory.push({ role: 'assistant', content: aiText });
    appendMessage('ai', aiText);

    // Trigger AI-chosen hotkey first
    if (chosenHotkeyId && state.vtubeConnected) {
      const hk = state.availableHotkeys.find(h => h.hotkeyID === chosenHotkeyId);
      await api.vtubeTriggerHotkey({ hotkeyID: chosenHotkeyId });
      log(`VTube: AI เลือก hotkey "${hk?.name || chosenHotkeyId}"`);
    } else if (state.settings.aiEmoDetect && state.vtubeConnected) {
      // Fallback: keyword-based emotion detection
      const emo = detectEmotion(aiText);
      if (emo) await triggerEmotion(emo);
    }

    // TTS
    if (state.ttsEnabled && state.settings.ttsEngine !== 'off') {
      await speakText(aiText);
    }

    // VTube subtle body sway while speaking
    if (state.settings.vtubeAutoMove && state.vtubeConnected) {
      await animateSpeaking();
    }

    // Reset to default/idle expression after a delay
    if (chosenHotkeyId && state.vtubeConnected) {
      const resetDelay = estimateReadingTime(aiText);
      setTimeout(async () => {
        const idleHk = findIdleHotkey();
        if (idleHk && idleHk.hotkeyID !== chosenHotkeyId) {
          await api.vtubeTriggerHotkey({ hotkeyID: idleHk.hotkeyID });
          log(`VTube: reset กลับหน้า idle "${idleHk.name}"`);
        }
      }, resetDelay);
    }
  } else {
    appendMessage('ai', `❌ เกิดข้อผิดพลาด: ${res.error}\n\nตรวจสอบว่า LM Studio กำลังทำงานอยู่นะคะ`);
    log('LM error: ' + res.error);
  }
}

function buildSystemPrompt() {
  const lang = state.settings.aiLang || 'th';
  const langInst = {
    th: 'ตอบเป็นภาษาไทยเท่านั้น ใช้ภาษาสุภาพและเป็นมิตร',
    jp: '日本語のみで答えてください。丁寧で親しみやすい言葉を使ってください。',
    en: 'Answer only in English. Be friendly and polite.',
    mix: 'ตอบเป็นภาษาไทย สามารถผสมภาษาอื่นได้บ้างตามความเหมาะสม',
  }[lang] || '';

  // Build hotkey instruction if VTube is connected and hotkeys are loaded
  let hotkeyInst = '';
  if (state.vtubeConnected && state.availableHotkeys.length > 0) {
    const hkList = state.availableHotkeys
      .map(hk => `  - "${hk.name}" (ID: ${hk.hotkeyID})`)
      .join('\n');
    hotkeyInst = `\n\n=== VTube Studio Hotkeys ===
คุณสามารถควบคุมสีหน้าและ animation ของ VTuber ได้ โดยเลือก hotkey ที่เหมาะสมกับอารมณ์ของคำตอบ
รายการ hotkeys ที่มีอยู่:
${hkList}

กฎสำคัญ: ในทุกคำตอบ คุณต้องตอบในรูปแบบ JSON นี้เท่านั้น:
{"text": "ข้อความตอบกลับของคุณที่นี่", "hotkey": "HOTKEY_ID_ที่เลือก"}

- "text" คือข้อความที่จะแสดงและพูด
- "hotkey" คือ ID ของ hotkey ที่ตรงกับอารมณ์ของคำตอบมากที่สุด (ใส่ "" ถ้าไม่มีที่เหมาะสม)
- ห้ามใส่ข้อความอื่นนอกจาก JSON นี้`;
  }

  const basePrompt = state.currentPersona
    ? `${state.currentPersona.prompt}\n\n${langInst}\n\nกรุณาตอบกระชับ ไม่เกิน 3-4 ประโยค`
    : `คุณคือ AI VTuber ที่เป็นมิตรและน่ารัก ${langInst} ตอบสั้นกระชับ ไม่เกิน 3-4 ประโยค`;

  return basePrompt + hotkeyInst;
}

function appendMessage(role, text) {
  if (!chatMessages) chatMessages = document.getElementById('chat-messages');
  const isUser = role === 'user';
  const persona = state.currentPersona;
  const avatar = isUser ? '🧑' : (persona?.emoji || '🤖');

  const div = document.createElement('div');
  div.className = 'msg ' + role;

  const avatarEl = document.createElement('div');
  avatarEl.className = 'msg-avatar';
  avatarEl.textContent = avatar;

  const wrapper = document.createElement('div');

  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.innerHTML = escapeHtml(text).replace(/\n/g, '<br>');

  const timeEl = document.createElement('div');
  timeEl.className = 'msg-time';
  timeEl.textContent = formatTime(new Date());

  wrapper.appendChild(bubble);
  wrapper.appendChild(timeEl);
  div.appendChild(avatarEl);
  div.appendChild(wrapper);

  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function appendTyping(id) {
  if (!chatMessages) chatMessages = document.getElementById('chat-messages');
  const div = document.createElement('div');
  div.className = 'msg ai';
  div.id = id;

  const avatarEl = document.createElement('div');
  avatarEl.className = 'msg-avatar';
  avatarEl.textContent = state.currentPersona?.emoji || '🤖';

  const wrapper = document.createElement('div');
  const bubble = document.createElement('div');
  bubble.className = 'msg-bubble';
  bubble.style.color = 'var(--text3)';
  bubble.innerHTML = '<span class="spinner"></span> กำลังคิด...';
  wrapper.appendChild(bubble);

  div.appendChild(avatarEl);
  div.appendChild(wrapper);
  chatMessages.appendChild(div);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function removeTyping(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function setGenerating(val) {
  isGenerating = val;
  btnSend.disabled = val;
  btnSend.textContent = val ? '⏸' : '▶';
}

function clearChat() {
  state.chatHistory = [];
  chatMessages.innerHTML = '';
  appendMessage('ai', '🗑 ล้างประวัติการสนทนาแล้วค่ะ เริ่มต้นใหม่ได้เลย!');
}

function escapeHtml(t) {
  return t.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// ── Emotion Detection ─────────────────────────────────────────
function detectEmotion(text) {
  const lower = text.toLowerCase();
  for (const [emo, keywords] of Object.entries(emotionKeywords)) {
    if (keywords.some(k => lower.includes(k.toLowerCase()))) return emo;
  }
  return null;
}

// ── VTube Studio ──────────────────────────────────────────────
async function connectVTube() {
  const url = document.getElementById('vtube-url').value.trim();
  if (!url) return toast('กรุณาใส่ WebSocket URL', 'error');
  state.settings.vtubeUrl = url;

  log(`กำลังเชื่อมต่อ VTube Studio: ${url}`);
  document.getElementById('btn-vtube-connect').textContent = '⏳ กำลังเชื่อมต่อ...';
  document.getElementById('btn-vtube-connect').disabled = true;

  const res = await api.vtubeConnect({ wsUrl: url });

  document.getElementById('btn-vtube-connect').disabled = false;
  document.getElementById('btn-vtube-connect').textContent = '🔌 เชื่อมต่อ';

  if (res.success) {
    log('VTube Studio: กำลังรอ authentication จาก VTube Studio app...');
    toast('กำลังรอ authentication จาก VTube Studio กรุณากด Allow ใน app', 'info', 5000);
  } else {
    toast('เชื่อมต่อไม่สำเร็จ: ' + res.error, 'error');
    log('VTube error: ' + res.error);
  }
}

function updateVtubeStatusUI() {
  const dot = document.getElementById('dot-vtube');
  const val = document.getElementById('val-vtube');
  const badge = document.getElementById('badge-vtube');
  const text = document.getElementById('vtube-status-text');

  if (state.vtubeConnected && state.vtubeAuthenticated) {
    dot.className = 'status-dot on';
    val.textContent = 'เชื่อมต่อแล้ว'; val.className = 'val ok';
    badge.textContent = 'เชื่อมต่อแล้ว'; badge.className = 'card-badge badge-connected';
    text.innerHTML = '<span style="color:var(--green)">✅ เชื่อมต่อและ authenticated สำเร็จ</span>';
  } else if (state.vtubeConnected) {
    dot.className = 'status-dot loading';
    val.textContent = 'รอ Auth'; val.className = 'val';
    badge.textContent = 'รอ Auth'; badge.className = 'card-badge';
    text.innerHTML = '<span style="color:var(--yellow)">⏳ กรุณากด Allow ใน VTube Studio</span>';
  } else {
    dot.className = 'status-dot off';
    val.textContent = 'ไม่ได้เชื่อมต่อ'; val.className = 'val err';
    badge.textContent = 'ไม่ได้เชื่อมต่อ'; badge.className = 'card-badge badge-disconnected';
    if (text) text.innerHTML = '';
  }
}

async function triggerEmotion(emo) {
  document.querySelectorAll('.emo-btn').forEach(b => b.classList.remove('active'));
  const all = document.querySelectorAll('.emo-btn');
  all.forEach(b => { if (b.getAttribute('onclick')?.includes(emo)) b.classList.add('active'); });
  setTimeout(() => document.querySelectorAll('.emo-btn').forEach(b => b.classList.remove('active')), 2000);

  if (!state.vtubeConnected) return;

  // Check if current persona has hotkey mapping
  const persona = state.currentPersona;
  const hotkeyId = persona?.hotkeys?.[emo];
  if (hotkeyId) {
    await api.vtubeTriggerHotkey({ hotkeyID: hotkeyId });
    log(`VTube: trigger emotion "${emo}" → hotkey "${hotkeyId}"`);
  }
}

async function loadHotkeys() {
  if (!state.vtubeConnected) return toast('กรุณาเชื่อมต่อ VTube Studio ก่อน', 'error');
  const res = await api.vtubeGetHotkeys();
  const list = document.getElementById('hotkey-list');
  if (res.success && res.hotkeys.length > 0) {
    // Save to state so AI can use them
    state.availableHotkeys = res.hotkeys.map(hk => ({
      hotkeyID: hk.hotkeyID,
      name: hk.name || hk.hotkeyID,
      type: hk.type || '',
    }));
    list.innerHTML = '';
    res.hotkeys.forEach(hk => {
      const div = document.createElement('div');
      div.className = 'hotkey-item';
      div.innerHTML = `<span>${hk.name || hk.hotkeyID}</span><span style="color:var(--text3);font-family:var(--mono);font-size:10px;">${hk.type || ''}</span>`;
      div.onclick = () => {
        api.vtubeTriggerHotkey({ hotkeyID: hk.hotkeyID });
        toast(`Trigger: ${hk.name}`, 'success', 1500);
        log(`Hotkey triggered: ${hk.name} (${hk.hotkeyID})`);
      };
      list.appendChild(div);
    });
    log(`VTube: โหลด hotkeys สำเร็จ ${res.hotkeys.length} รายการ — AI จะใช้ได้เลย`);
    toast(`โหลด ${res.hotkeys.length} hotkeys สำเร็จ AI จะเลือกใช้เองได้แล้ว ✨`, 'success', 3000);
  } else {
    state.availableHotkeys = [];
    list.innerHTML = '<div style="color:var(--text3);font-size:12px;text-align:center;padding:20px;">ไม่พบ Hotkeys หรือยังไม่ได้ตั้งค่าใน VTube Studio</div>';
    if (!res.success) toast('โหลด Hotkeys ไม่สำเร็จ: ' + res.error, 'error');
  }
}

// หาหน้า idle/default จาก hotkeys ที่โหลดมา
// ลำดับความสำคัญ: ชื่อที่ตรงกับ keyword idle/default/normal → hotkey แรกใน list
function findIdleHotkey() {
  if (!state.availableHotkeys.length) return null;
  const idleKeywords = ['idle', 'default', 'normal', 'neutral', 'ปกติ', 'ธรรมดา', 'rest', 'base'];
  const found = state.availableHotkeys.find(hk =>
    idleKeywords.some(k => hk.name.toLowerCase().includes(k))
  );
  return found || state.availableHotkeys[0];
}

// คำนวณเวลา (ms) ที่รอก่อน reset ≈ เวลาอ่านข้อความ + buffer 1 วินาที
function estimateReadingTime(text) {
  const charsPerSecond = 8; // อ่านภาษาไทย/ญี่ปุ่น ~8 ตัวอักษรต่อวินาที
  const seconds = Math.max(2, text.length / charsPerSecond);
  return Math.min(seconds * 1000 + 1000, 12000); // สูงสุด 12 วินาที
}

async function animateSpeaking() {
  if (!state.settings.vtubeAutoMove) return;
  // Subtle relative sway — does NOT move model away from current position
  const wobble = [0.03, -0.03, 0.015, -0.015, 0];
  for (const r of wobble) {
    await api.vtubeMoveModel({ posX: r, posY: 0, rotation: r * 1.5, size: null, valuesAreRelativeToModel: true });
    await sleep(200);
  }
}

// ── TTS ───────────────────────────────────────────────────────
function toggleTTS() {
  state.ttsEnabled = !state.ttsEnabled;
  const btn = document.getElementById('btn-tts-toggle');
  btn.classList.toggle('active', state.ttsEnabled);
  btn.title = state.ttsEnabled ? 'TTS เปิดอยู่ (คลิกเพื่อปิด)' : 'เปิด TTS';
  updateTTSStatus();
  toast(state.ttsEnabled ? '🔊 TTS เปิดแล้ว' : '🔇 TTS ปิดแล้ว', 'info', 1500);
}

function updateTTSStatus() {
  const dot = document.getElementById('dot-tts');
  const val = document.getElementById('val-tts');
  const engine = state.settings.ttsEngine;
  if (state.ttsEnabled && engine !== 'off') {
    dot.className = 'status-dot on';
    val.textContent = engine === 'system' ? 'System TTS' : engine;
    val.className = 'val ok';
  } else {
    dot.className = 'status-dot off';
    val.textContent = 'ปิด'; val.className = 'val';
  }
}

async function loadVoices() {
  const res = await api.ttsGetVoices();
  const sel = document.getElementById('tts-voice');
  const prev = sel.value;
  sel.innerHTML = '<option value="">Default</option>';
  if (res.success && res.voices) {
    res.voices.forEach(v => {
      const opt = document.createElement('option');
      opt.value = v; opt.textContent = v;
      sel.appendChild(opt);
    });
    if (prev) sel.value = prev;
    else if (state.settings.ttsVoice) sel.value = state.settings.ttsVoice;
    log(`TTS: โหลดเสียงสำเร็จ ${res.voices.length} เสียง`);
  }
}

async function testTTS() {
  const text = 'สวัสดีครับ นี่คือการทดสอบระบบเสียงของ VTube AI';
  await speakText(text);
}

async function speakText(text) {
  const engine = state.settings.ttsEngine || 'system';
  if (engine === 'off') return;

  // Try VITS server first if configured
  if (engine === 'system' && state.settings.vitsUrl) {
    try {
      const r = await fetch(`${state.settings.vitsUrl}/voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, speaker_id: state.settings.vitsSpeaker || 0 }),
      });
      if (r.ok) {
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const audio = new Audio(url);
        setSpeaking(true);
        audio.onended = () => { setSpeaking(false); URL.revokeObjectURL(url); };
        audio.play();
        return;
      }
    } catch (e) { log('VITS error: ' + e.message + ' → fallback to system TTS'); }
  }

  // System TTS fallback
  const cleanText = text.replace(/[*_#`]/g, '').replace(/\n/g, ' ').substring(0, 300);
  setSpeaking(true);
  const res = await api.ttsSpeak({
    text: cleanText,
    voice: state.settings.ttsVoice || null,
    rate: state.settings.ttsRate || 1.0,
  });
  setSpeaking(false);
  if (!res.success) log('TTS error: ' + res.error);
}

function setSpeaking(val) {
  state.isSpeaking = val;
  document.getElementById('speaking-indicator').classList.toggle('visible', val);
}

function onTTSEngineChange() {
  state.settings.ttsEngine = document.getElementById('tts-engine').value;
  updateTTSStatus();
}

async function testVITS() {
  const url = document.getElementById('vits-url').value.trim();
  if (!url) return toast('กรุณาใส่ VITS Server URL', 'error');
  try {
    const r = await fetch(`${url}/voice`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: 'ทดสอบระบบเสียง', speaker_id: parseInt(document.getElementById('vits-speaker').value) }),
    });
    if (r.ok) {
      const blob = await r.blob();
      const audioUrl = URL.createObjectURL(blob);
      new Audio(audioUrl).play();
      toast('VITS ทดสอบสำเร็จ 🎵', 'success');
    } else {
      toast('VITS server ตอบกลับผิดพลาด: ' + r.status, 'error');
    }
  } catch (e) {
    toast('เชื่อมต่อ VITS ไม่ได้: ' + e.message, 'error');
  }
}

// ── File pickers ──────────────────────────────────────────────
async function selectPthFile() {
  const res = await api.openFileDialog({ filters: [
    { name: 'PyTorch Model', extensions: ['pth', 'pt'] },
    { name: 'All Files', extensions: ['*'] }
  ]});
  if (!res.canceled && res.filePath) {
    document.getElementById('pth-path').value = res.filePath;
    document.getElementById('pth-display').textContent = res.filePath.split(/[\\/]/).pop();
    state.settings.pthPath = res.filePath;
    log('เลือกไฟล์ .pth: ' + res.filePath);
  }
}

async function selectCfgFile() {
  const res = await api.openFileDialog({ filters: [
    { name: 'Config JSON', extensions: ['json'] },
    { name: 'All Files', extensions: ['*'] }
  ]});
  if (!res.canceled && res.filePath) {
    document.getElementById('cfg-path').value = res.filePath;
    state.settings.cfgPath = res.filePath;
    log('เลือกไฟล์ config: ' + res.filePath);
  }
}

// ── Persona Management ────────────────────────────────────────
function renderPersonaList() {
  const list = document.getElementById('persona-list');
  if (!list) return;
  list.innerHTML = '';

  if (state.personas.length === 0) {
    // Add default personas
    state.personas = [
      {
        name: 'Sakura AI',
        emoji: '🌸',
        desc: 'สาว AI น่ารัก สไตล์ญี่ปุ่น',
        prompt: 'คุณคือ Sakura สาว AI น่ารักสไตล์ญี่ปุ่น พูดสุภาพและน่ารัก ชอบใช้คำว่า "ค่ะ" และ "นะคะ" บางทีผสมคำญี่ปุ่นได้บ้าง เช่น "kawaii", "sugoi" ตอบสั้นกระชับ ไม่เกิน 3 ประโยค',
        hotkeys: {},
      },
      {
        name: 'Neko Chan',
        emoji: '🐱',
        desc: 'แมวสาว AI ซน ๆ ร่าเริง',
        prompt: 'คุณคือ Neko แมวสาว AI ร่าเริงและซน ชอบพูดว่า "nya~" ท้ายประโยคบ้าง มีพลังงานสูง ชอบเล่น ตอบสั้นกระชับ แต่มีชีวิตชีวา',
        hotkeys: {},
      },
    ];
  }

  state.personas.forEach((p, i) => {
    const card = document.createElement('div');
    card.className = 'persona-card' + (state.currentPersona === p ? ' active' : '');
    card.innerHTML = `
      <div class="persona-emoji">${p.emoji}</div>
      <div class="persona-card-name">${escapeHtml(p.name)}</div>
      <div class="persona-card-desc">${escapeHtml(p.desc)}</div>
      <div style="margin-top:8px;display:flex;gap:6px;justify-content:center;">
        <button class="btn btn-primary btn-sm" onclick="selectPersona(${i})">✓ ใช้งาน</button>
        <button class="btn btn-secondary btn-sm" onclick="editPersona(${i})">✏️</button>
      </div>
    `;
    list.appendChild(card);
  });
}

function selectPersona(idx) {
  state.currentPersona = state.personas[idx];
  renderPersonaList();
  updatePersonaDisplay();
  saveSettings();
  toast(`เลือกตัวละคร "${state.currentPersona.name}" แล้ว ✨`, 'success');
  switchPanel('chat', document.querySelector('[data-panel="chat"]'));
}

function updatePersonaDisplay() {
  const p = state.currentPersona;
  document.getElementById('persona-avatar-display').textContent = p?.emoji || '🎭';
  document.getElementById('persona-name-display').textContent = p?.name || 'ยังไม่ได้เลือก';
  document.getElementById('persona-desc-display').textContent = p?.desc || 'กรุณาเลือกตัวละครใน Tab ตัวละคร';
}

let editingPersonaIdx = -1;

function startNewPersona() {
  editingPersonaIdx = -1;
  document.getElementById('pe-emoji').value = '🎭';
  document.getElementById('pe-name').value = '';
  document.getElementById('pe-desc').value = '';
  document.getElementById('pe-prompt').value = '';
  document.getElementById('pe-hk-happy').value = '';
  document.getElementById('pe-hk-sad').value = '';
  document.getElementById('pe-hk-excited').value = '';
  document.getElementById('pe-hk-angry').value = '';
  document.getElementById('persona-editor-title').textContent = '➕ เพิ่มตัวละครใหม่';
  document.getElementById('btn-delete-persona').style.display = 'none';
  document.getElementById('persona-editor').style.display = 'block';
  document.getElementById('persona-editor').scrollIntoView({ behavior: 'smooth' });
}

function editPersona(idx) {
  editingPersonaIdx = idx;
  const p = state.personas[idx];
  document.getElementById('pe-emoji').value = p.emoji || '🎭';
  document.getElementById('pe-name').value = p.name || '';
  document.getElementById('pe-desc').value = p.desc || '';
  document.getElementById('pe-prompt').value = p.prompt || '';
  document.getElementById('pe-hk-happy').value = p.hotkeys?.happy || '';
  document.getElementById('pe-hk-sad').value = p.hotkeys?.sad || '';
  document.getElementById('pe-hk-excited').value = p.hotkeys?.excited || '';
  document.getElementById('pe-hk-angry').value = p.hotkeys?.angry || '';
  document.getElementById('persona-editor-title').textContent = '✏️ แก้ไขตัวละคร';
  document.getElementById('btn-delete-persona').style.display = 'inline-flex';
  document.getElementById('persona-editor').style.display = 'block';
  document.getElementById('persona-editor').scrollIntoView({ behavior: 'smooth' });
}

function savePersona() {
  const name = document.getElementById('pe-name').value.trim();
  if (!name) return toast('กรุณาใส่ชื่อตัวละคร', 'error');
  const persona = {
    name,
    emoji: document.getElementById('pe-emoji').value || '🎭',
    desc: document.getElementById('pe-desc').value.trim(),
    prompt: document.getElementById('pe-prompt').value.trim(),
    hotkeys: {
      happy: document.getElementById('pe-hk-happy').value.trim(),
      sad: document.getElementById('pe-hk-sad').value.trim(),
      excited: document.getElementById('pe-hk-excited').value.trim(),
      angry: document.getElementById('pe-hk-angry').value.trim(),
    },
  };
  if (editingPersonaIdx >= 0) {
    state.personas[editingPersonaIdx] = persona;
    if (state.currentPersona === state.personas[editingPersonaIdx]) state.currentPersona = persona;
  } else {
    state.personas.push(persona);
  }
  document.getElementById('persona-editor').style.display = 'none';
  renderPersonaList();
  saveSettings();
  toast(`บันทึกตัวละคร "${name}" แล้ว ✨`, 'success');
}

function deletePersona() {
  if (editingPersonaIdx < 0) return;
  const name = state.personas[editingPersonaIdx].name;
  if (state.currentPersona === state.personas[editingPersonaIdx]) {
    state.currentPersona = null;
    updatePersonaDisplay();
  }
  state.personas.splice(editingPersonaIdx, 1);
  document.getElementById('persona-editor').style.display = 'none';
  renderPersonaList();
  saveSettings();
  toast(`ลบตัวละคร "${name}" แล้ว`, 'info');
}

function cancelPersonaEdit() {
  document.getElementById('persona-editor').style.display = 'none';
}

// ── Utils ─────────────────────────────────────────────────────
function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }