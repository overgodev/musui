const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  // Window controls
  minimize: () => ipcRenderer.send('window-minimize'),
  maximize: () => ipcRenderer.send('window-maximize'),
  close: () => ipcRenderer.send('window-close'),

  // LM Studio
  lmChat: (opts) => ipcRenderer.invoke('lm-chat', opts),
  lmGetModels: (opts) => ipcRenderer.invoke('lm-get-models', opts),

  // VTube Studio
  vtubeConnect: (opts) => ipcRenderer.invoke('vtube-connect', opts),
  vtubeTriggerHotkey: (opts) => ipcRenderer.invoke('vtube-trigger-hotkey', opts),
  vtubeGetHotkeys: () => ipcRenderer.invoke('vtube-get-hotkeys'),
  vtubeMoveModel: (opts) => ipcRenderer.invoke('vtube-move-model', opts),
  onVtubeStatus: (cb) => ipcRenderer.on('vtube-status', (_, d) => cb(d)),
  onVtubeMessage: (cb) => ipcRenderer.on('vtube-message', (_, d) => cb(d)),

  // TTS
  rvcSpeak: (opts) => ipcRenderer.invoke('rvc-speak', opts),
  ttsSpeak: (opts) => ipcRenderer.invoke('tts-speak', opts),
  ttsGetVoices: () => ipcRenderer.invoke('tts-get-voices'),
  ttsStop: () => ipcRenderer.invoke('tts-stop'),

  // File dialog
  openFileDialog: (opts) => ipcRenderer.invoke('open-file-dialog', opts),

  // Settings
  settingsLoad: () => ipcRenderer.invoke('settings-load'),
  settingsSave: (data) => ipcRenderer.invoke('settings-save', data),
});
