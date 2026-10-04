import { contextBridge, ipcRenderer } from "electron";

contextBridge.exposeInMainWorld("electronAPI", {
  platform: process.platform,
  getEngineUrl: () => ipcRenderer.invoke("get-engine-url"),
});
