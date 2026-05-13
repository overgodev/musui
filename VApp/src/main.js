const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const path = require('path');
const WebSocket = require('ws');
const axios = require('axios');
const { exec } = require('child_process');
const { execFile } = require('child_process');
const fs = require('fs');
const os = require('os');

let mainWindow;
let vtubeWs = null;
let vtubeAuthenticated = false;
let currentSettings = {};

const EDGE_RVC_DEFAULTS = Object.freeze({
  voice: 'th-TH-PremwadeeNeural',
  rate: '+3%',
  pitch: '+60Hz',
  volume: '+6%',
  f0method: 'harvest',
  indexRate: 0.9,
  protect: 0.28,
  rmsMixRate: 0.9,
  filterRadius: 3,
  resampleSr: 0,
});

function clamp01(value, fallback = 0) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  if (n < 0) return 0;
  if (n > 1) return 1;
  return n;
}

function toInt(value, fallback = 0) {
  const n = Number(value);
  return Number.isFinite(n) ? Math.trunc(n) : fallback;
}

function resolveRvcPython() {
  const localVenv = path.join(__dirname, '..', '.venv310_rvc', 'Scripts', 'python.exe');
  if (fs.existsSync(localVenv)) return localVenv;
  if (process.env.RVC_PYTHON && fs.existsSync(process.env.RVC_PYTHON)) return process.env.RVC_PYTHON;
  return 'python';
}

function resolveEdgeVoiceParams(text, opts = {}) {
  const hasThai = /[\u0E00-\u0E7F]/.test(text || '');
  return {
    voice: (opts.voice || '').trim() || (hasThai ? EDGE_RVC_DEFAULTS.voice : 'en-US-JennyNeural'),
    rate: (opts.rate || '').trim() || EDGE_RVC_DEFAULTS.rate,
    pitch: (opts.pitch || '').trim() || EDGE_RVC_DEFAULTS.pitch,
    volume: (opts.volume || '').trim() || EDGE_RVC_DEFAULTS.volume,
  };
}

// ─── Create Window ─────────────────────────────────────────────────────────
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 960,
    minHeight: 680,
    frame: false,
    transparent: false,
    backgroundColor: '#0d0d14',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js'),
    },
    icon: path.join(__dirname, '../assets/icon.png'),
  });

  mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));

  mainWindow.on('closed', () => {
    if (vtubeWs) vtubeWs.close();
    mainWindow = null;
  });
}

app.whenReady().then(createWindow);
app.on('window-all-closed', () => { if (process.platform !== 'darwin') app.quit(); });
app.on('activate', () => { if (BrowserWindow.getAllWindows().length === 0) createWindow(); });

// ─── Window Controls ────────────────────────────────────────────────────────
ipcMain.on('window-minimize', () => mainWindow.minimize());
ipcMain.on('window-maximize', () => mainWindow.isMaximized() ? mainWindow.unmaximize() : mainWindow.maximize());
ipcMain.on('window-close', () => mainWindow.close());

// ─── LM Studio Chat ────────────────────────────────────────────────────────
ipcMain.handle('lm-chat', async (event, { apiUrl, messages, systemPrompt, model, temperature, maxTokens }) => {
  try {
    const payload = {
      model: model || 'local-model',
      messages: [
        { role: 'system', content: systemPrompt || 'You are a friendly VTuber AI assistant.' },
        ...messages
      ],
      temperature: temperature ?? 0.8,
      max_tokens: maxTokens ?? 512,
      stream: false,
    };

    const response = await axios.post(`${apiUrl}/v1/chat/completions`, payload, {
      timeout: 60000,
      headers: { 'Content-Type': 'application/json' },
    });

    // Handle various LM Studio response formats
    const data = response.data;
    let text = '';
    if (data.choices && data.choices.length > 0) {
      const choice = data.choices[0];
      text = choice.message?.content || choice.text || '';
    } else if (data.content) {
      text = data.content;
    } else if (typeof data === 'string') {
      text = data;
    }
    
    if (!text) {
      console.error('LM Studio empty response:', JSON.stringify(data).substring(0, 300));
      return { success: false, error: 'AI ตอบกลับมาว่างเปล่า ลองตรวจสอบ model ที่เลือกอยู่' };
    }
    return { success: true, text: text.trim() };
  } catch (err) {
    console.error('lm-chat error:', err.response?.data || err.message);
    const errMsg = err.response?.data?.error?.message || err.response?.data?.message || err.message;
    return { success: false, error: errMsg };
  }
});

// ─── LM Studio Models List ──────────────────────────────────────────────────
ipcMain.handle('lm-get-models', async (event, { apiUrl }) => {
  try {
    const response = await axios.get(`${apiUrl}/v1/models`, { timeout: 5000 });
    return { success: true, models: response.data.data || [] };
  } catch (err) {
    return { success: false, error: err.message };
  }
});

// ─── VTube Studio WebSocket ─────────────────────────────────────────────────
ipcMain.handle('vtube-connect', async (event, { wsUrl }) => {
  return new Promise((resolve) => {
    try {
      if (vtubeWs) {
        vtubeWs.close();
        vtubeWs = null;
        vtubeAuthenticated = false;
      }

      vtubeWs = new WebSocket(wsUrl || 'ws://localhost:8001');

      vtubeWs.on('open', () => {
        // Request authentication token
        const authRequest = {
          apiName: 'VTubeStudioPublicAPI',
          apiVersion: '1.0',
          requestID: 'auth-request',
          messageType: 'AuthenticationTokenRequest',
          data: {
            pluginName: 'VTube AI Controller',
            pluginDeveloper: 'VTubeAI',
            pluginIcon: '',
          },
        };
        vtubeWs.send(JSON.stringify(authRequest));
      });

      vtubeWs.on('message', (data) => {
        try {
          const msg = JSON.parse(data.toString());
          if (msg.messageType === 'AuthenticationTokenResponse') {
            const token = msg.data?.authenticationToken;
            if (token) {
              // Authenticate with token
              const authMsg = {
                apiName: 'VTubeStudioPublicAPI',
                apiVersion: '1.0',
                requestID: 'auth-2',
                messageType: 'AuthenticationRequest',
                data: {
                  pluginName: 'VTube AI Controller',
                  pluginDeveloper: 'VTubeAI',
                  authenticationToken: token,
                },
              };
              vtubeWs.send(JSON.stringify(authMsg));
            }
          } else if (msg.messageType === 'AuthenticationResponse') {
            vtubeAuthenticated = msg.data?.authenticated || false;
            mainWindow?.webContents.send('vtube-status', {
              connected: true,
              authenticated: vtubeAuthenticated,
            });
          } else {
            mainWindow?.webContents.send('vtube-message', msg);
          }
        } catch (e) {}
      });

      vtubeWs.on('error', (err) => {
        resolve({ success: false, error: err.message });
      });

      vtubeWs.on('close', () => {
        vtubeAuthenticated = false;
        mainWindow?.webContents.send('vtube-status', { connected: false, authenticated: false });
      });

      setTimeout(() => {
        if (vtubeWs && vtubeWs.readyState === WebSocket.OPEN) {
          resolve({ success: true });
        } else {
          resolve({ success: false, error: 'Connection timeout' });
        }
      }, 3000);

    } catch (err) {
      resolve({ success: false, error: err.message });
    }
  });
});

// ─── VTube Trigger Hotkey ───────────────────────────────────────────────────
ipcMain.handle('vtube-trigger-hotkey', async (event, { hotkeyID }) => {
  if (!vtubeWs || vtubeWs.readyState !== WebSocket.OPEN) {
    return { success: false, error: 'Not connected to VTube Studio' };
  }
  const msg = {
    apiName: 'VTubeStudioPublicAPI',
    apiVersion: '1.0',
    requestID: 'hotkey-' + Date.now(),
    messageType: 'HotkeyTriggerRequest',
    data: { hotkeyID },
  };
  vtubeWs.send(JSON.stringify(msg));
  return { success: true };
});

// ─── VTube Get Hotkeys ──────────────────────────────────────────────────────
ipcMain.handle('vtube-get-hotkeys', async () => {
  if (!vtubeWs || vtubeWs.readyState !== WebSocket.OPEN) {
    return { success: false, error: 'Not connected' };
  }
  return new Promise((resolve) => {
    const reqID = 'hotkeys-' + Date.now();
    const msg = {
      apiName: 'VTubeStudioPublicAPI',
      apiVersion: '1.0',
      requestID: reqID,
      messageType: 'HotkeysInCurrentModelRequest',
      data: {},
    };

    const handler = (data) => {
      try {
        const parsed = JSON.parse(data.toString());
        if (parsed.requestID === reqID) {
          vtubeWs.off('message', handler);
          resolve({ success: true, hotkeys: parsed.data?.availableHotkeys || [] });
        }
      } catch (e) {}
    };

    vtubeWs.on('message', handler);
    vtubeWs.send(JSON.stringify(msg));
    setTimeout(() => { vtubeWs.off('message', handler); resolve({ success: false, error: 'Timeout' }); }, 5000);
  });
});

// ─── VTube Move Model ───────────────────────────────────────────────────────
ipcMain.handle('vtube-move-model', async (event, { posX, posY, rotation, size, valuesAreRelativeToModel }) => {
  if (!vtubeWs || vtubeWs.readyState !== WebSocket.OPEN) return { success: false };
  const isRelative = valuesAreRelativeToModel ?? false;
  const moveData = {
    timeInSeconds: 0.2,
    valuesAreRelativeToModel: isRelative,
    positionX: posX ?? 0,
    positionY: posY ?? 0,
    rotation: rotation ?? 0,
  };
  // Only send size when explicitly provided or doing absolute positioning
  if (!isRelative || (size !== null && size !== undefined)) {
    moveData.size = size ?? -50;
  }
  const msg = {
    apiName: 'VTubeStudioPublicAPI',
    apiVersion: '1.0',
    requestID: 'move-' + Date.now(),
    messageType: 'MoveModelRequest',
    data: moveData,
  };
  vtubeWs.send(JSON.stringify(msg));
  return { success: true };
});

// ─── TTS System ─────────────────────────────────────────────────────────────
ipcMain.handle('tts-speak', async (event, { text, voice, rate, pitch }) => {
  return new Promise((resolve) => {
    const say = require('say');
    say.speak(text, voice || null, rate || 1.0, (err) => {
      if (err) resolve({ success: false, error: err.message });
      else resolve({ success: true });
    });
  });
});

ipcMain.handle('tts-get-voices', async () => {
  return new Promise((resolve) => {
    const say = require('say');
    say.getInstalledVoices((err, voices) => {
      if (err) resolve({ success: false, voices: [] });
      else resolve({ success: true, voices: voices || [] });
    });
  });
});

ipcMain.handle('tts-stop', async () => {
  const say = require('say');
  say.stop();
  return { success: true };
});

ipcMain.handle('rvc-speak', async (event, opts = {}) => {
  const {
    text,
    runtime,
    rvcUrl,
    pitch,
    modelName,
    modelPath,
    indexPath,
    edgeVoice,
    edgeRate,
    edgePitch,
    edgeVolume,
    f0method,
    indexRate,
    protect,
    rmsMixRate,
    filterRadius,
    resampleSr,
  } = opts;

  const timestamp = Date.now();
  const srcWav = path.join(os.tmpdir(), `tts_src_${timestamp}.wav`);
  const outWav = path.join(os.tmpdir(), `rvc_out_${timestamp}.wav`);
  const cleanText = String(text || '').replace(/\s+/g, ' ').trim().substring(0, 500);
  const pythonCmd = resolveRvcPython();

  try {
    if (!cleanText) throw new Error('Text is empty');
    const edgeParams = resolveEdgeVoiceParams(cleanText, {
      voice: edgeVoice,
      rate: edgeRate,
      pitch: edgePitch,
      volume: edgeVolume,
    });

    const useLocalCpu = String(runtime || '').toLowerCase() === 'local-cpu';
    if (useLocalCpu) {
      if (!modelPath || !fs.existsSync(modelPath)) {
        throw new Error('Local CPU mode requires a valid .pth model path');
      }
      const helperScript = path.join(__dirname, 'rvc_local_cpu_tts_helper.py');
      const helperArgs = [
        helperScript,
        cleanText,
        outWav,
        `--model-path=${modelPath}`,
        `--voice=${edgeParams.voice}`,
        `--rate=${edgeParams.rate}`,
        `--edge-pitch=${edgeParams.pitch}`,
        `--volume=${edgeParams.volume}`,
        `--rvc-pitch=${toInt(pitch, 0)}`,
        `--f0method=${(typeof f0method === 'string' && f0method.trim()) || EDGE_RVC_DEFAULTS.f0method}`,
        `--index-rate=${clamp01(indexRate, EDGE_RVC_DEFAULTS.indexRate)}`,
        `--protect=${clamp01(protect, EDGE_RVC_DEFAULTS.protect)}`,
        `--rms-mix-rate=${clamp01(rmsMixRate, EDGE_RVC_DEFAULTS.rmsMixRate)}`,
      ];
      if (indexPath && fs.existsSync(indexPath)) helperArgs.push(`--index-path=${indexPath}`);

      await new Promise((resolve, reject) => {
        execFile(pythonCmd, helperArgs, { timeout: 180000 }, (err) => {
          if (err) reject(new Error('local cpu rvc failed: ' + err.message));
          else resolve();
        });
      });

      if (!fs.existsSync(outWav)) throw new Error('Local CPU RVC produced no output file');
      return { success: true, audioPath: outWav };
    }

    if (!rvcUrl) throw new Error('RVC server URL is required');

    const helperScript = path.join(__dirname, 'rvc_tts_helper.py');
    const helperArgs = [
      helperScript,
      cleanText,
      srcWav,
      `--voice=${edgeParams.voice}`,
      `--rate=${edgeParams.rate}`,
      `--pitch=${edgeParams.pitch}`,
      `--volume=${edgeParams.volume}`,
    ];

    await new Promise((resolve, reject) => {
      execFile(pythonCmd, helperArgs, { timeout: 30000 }, (err) => {
        if (err) reject(new Error('edge-tts failed: ' + err.message));
        else resolve();
      });
    });

    if (!fs.existsSync(srcWav)) throw new Error('edge-tts produced no output file');

    const form = new FormData();
    const wavBuf = fs.readFileSync(srcWav);
    form.append('files', new Blob([wavBuf], { type: 'audio/wav' }), 'input.wav');

    const uploadResp = await fetch(`${rvcUrl}/upload`, { method: 'POST', body: form });
    if (!uploadResp.ok) throw new Error(`RVC upload failed: ${uploadResp.status}`);
    const uploadData = await uploadResp.json();

    let uploadedPath = '';
    if (Array.isArray(uploadData) && uploadData.length > 0) {
      const first = uploadData[0];
      uploadedPath = typeof first === 'string' ? first : (first.path || first.name || first.tmp_path || '');
    }
    if (!uploadedPath) throw new Error('RVC upload returned no file path');

    if (modelName) {
      await fetch(`${rvcUrl}/run/infer_change_voice`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: [modelName, 0.33, 0.33] }),
      });
    }

    const inferResp = await fetch(`${rvcUrl}/run/infer_convert`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        data: [
          0,
          uploadedPath,
          toInt(pitch, 0),
          null,
          (typeof f0method === 'string' && f0method.trim()) || EDGE_RVC_DEFAULTS.f0method,
          '',
          '',
          clamp01(indexRate, EDGE_RVC_DEFAULTS.indexRate),
          toInt(filterRadius, EDGE_RVC_DEFAULTS.filterRadius),
          toInt(resampleSr, EDGE_RVC_DEFAULTS.resampleSr),
          clamp01(rmsMixRate, EDGE_RVC_DEFAULTS.rmsMixRate),
          clamp01(protect, EDGE_RVC_DEFAULTS.protect),
        ],
      }),
    });
    if (!inferResp.ok) throw new Error(`RVC infer failed: ${inferResp.status}`);

    const inferJson = await inferResp.json();
    const resultData = inferJson?.data;
    if (!Array.isArray(resultData) || resultData.length < 2) {
      throw new Error(`infer_convert response invalid: ${JSON.stringify(resultData).substring(0, 200)}`);
    }

    const audioOutput = resultData[1];
    const audioFilePath = typeof audioOutput === 'string'
      ? audioOutput
      : (audioOutput?.path || audioOutput?.name || '');
    if (!audioFilePath) throw new Error('Cannot read audio path from RVC response');

    const audioResp = await fetch(`${rvcUrl}/file=${audioFilePath}`);
    if (!audioResp.ok) throw new Error(`RVC file fetch failed: ${audioResp.status}`);
    const audioBuffer = Buffer.from(await audioResp.arrayBuffer());
    fs.writeFileSync(outWav, audioBuffer);

    try { fs.unlinkSync(srcWav); } catch {}
    return { success: true, audioPath: outWav };
  } catch (err) {
    try { fs.unlinkSync(srcWav); } catch {}
    try { fs.unlinkSync(outWav); } catch {}
    console.error('rvc-speak error:', err.message);
    return { success: false, error: err.message };
  }
});

// ─── File Dialog (for .pth model) ──────────────────────────────────────────
ipcMain.handle('open-file-dialog', async (event, { filters }) => {
  const result = await dialog.showOpenDialog(mainWindow, {
    properties: ['openFile'],
    filters: filters || [{ name: 'All Files', extensions: ['*'] }],
  });
  return { canceled: result.canceled, filePath: result.filePaths[0] || null };
});

// ─── Settings persistence ───────────────────────────────────────────────────
const settingsPath = path.join(app.getPath('userData'), 'settings.json');

ipcMain.handle('settings-load', async () => {
  try {
    if (fs.existsSync(settingsPath)) {
      const raw = fs.readFileSync(settingsPath, 'utf-8');
      return { success: true, data: JSON.parse(raw) };
    }
    return { success: true, data: {} };
  } catch (e) {
    return { success: false, data: {} };
  }
});

ipcMain.handle('settings-save', async (event, data) => {
  try {
    fs.writeFileSync(settingsPath, JSON.stringify(data, null, 2), 'utf-8');
    return { success: true };
  } catch (e) {
    return { success: false, error: e.message };
  }
});
