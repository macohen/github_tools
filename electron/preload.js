const { contextBridge, ipcRenderer } = require('electron');

// Expose a minimal API to the renderer process
contextBridge.exposeInMainWorld('electronAPI', {
  isElectron: true,
  platform: process.platform,
  version: require('./package.json').version,
  // Backend port will be set via IPC from main process
  backendPort: null,
  getBackendPort: () => ipcRenderer.invoke('get-backend-port'),
});
