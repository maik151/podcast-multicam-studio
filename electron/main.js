const { app, BrowserWindow, ipcMain, session } = require('electron');
const path = require('path');
const http = require('http');
const { spawn } = require('child_process');

let mainWindow = null;
let pythonProcess = null;

// Configurar flags de Chromium para WebRTC y certificados locales
app.commandLine.appendSwitch('ignore-certificate-errors');
app.commandLine.appendSwitch('allow-insecure-localhost');
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');
app.commandLine.appendSwitch('enable-features', 'WebRTCPipeWireCapturer');

// Comprobar si el backend Python ya está respondiendo
function checkBackend(port = 8080) {
  return new Promise((resolve) => {
    const req = http.get(`http://127.0.0.1:${port}/api/network`, { timeout: 1000 }, (res) => {
      resolve(res.statusCode === 200);
    });
    req.on('error', () => resolve(false));
    req.on('timeout', () => {
      req.destroy();
      resolve(false);
    });
  });
}

// Iniciar el backend Python (compatible tanto en desarrollo como en producción empaquetada)
async function ensureBackendRunning() {
  const isRunning = await checkBackend(8080);
  if (isRunning) {
    console.log('[Electron] Backend Python detectado activo en puerto 8080');
    return;
  }

  console.log('[Electron] Iniciando backend Python en segundo plano...');
  try {
    if (app.isPackaged) {
      // Producción: el engine está en process.resourcesPath/engine/start_studio.exe
      const engineDir = path.join(process.resourcesPath, 'engine');
      const startStudioExe = path.join(engineDir, 'start_studio.exe');
      pythonProcess = spawn(startStudioExe, ['--no-window'], {
        cwd: engineDir,
        detached: false,
        stdio: 'ignore',
        windowsHide: true
      });
    } else {
      // Desarrollo: usar entorno virtual local
      const repoRoot = path.resolve(__dirname, '..');
      const pythonExe = path.join(repoRoot, '.venv', 'Scripts', 'python.exe');
      const mainPy = path.join(repoRoot, 'main.py');
      pythonProcess = spawn(pythonExe, [mainPy, '--no-window'], {
        cwd: repoRoot,
        detached: false,
        stdio: 'ignore',
        windowsHide: true
      });
    }

    pythonProcess.on('error', (err) => {
      console.error('[Electron] Error iniciando subproceso Python:', err);
    });

    // Esperar hasta que el backend responda (hasta 12 segundos)
    for (let i = 0; i < 24; i++) {
      await new Promise(r => setTimeout(r, 500));
      if (await checkBackend(8080)) {
        console.log('[Electron] Backend Python conectado exitosamente');
        break;
      }
    }
  } catch (e) {
    console.error('[Electron] Fallo al spawnear backend:', e);
  }
}

function createWindow() {
  const iconPath = app.isPackaged
    ? path.join(process.resourcesPath, 'favicon.ico')
    : path.join(__dirname, '..', 'favicon.ico');

  mainWindow = new BrowserWindow({
    width: 1540,
    height: 940,
    minWidth: 1200,
    minHeight: 720,
    frame: false, // <-- VENTANA NATIVA FRAMELESS (Sin barra de Windows)
    backgroundColor: '#0e1015',
    icon: iconPath,
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      nodeIntegration: false,
      contextIsolation: true,
      webSecurity: false,
      allowRunningInsecureContent: true
    }
  });

  // Conceder automáticamente permisos de medios (cámara y micrófono)
  session.defaultSession.setPermissionRequestHandler((webContents, permission, callback) => {
    const allowed = ['media', 'mediaKeySystem', 'notifications', 'midi'];
    if (allowed.includes(permission)) {
      return callback(true);
    }
    callback(false);
  });

  // Conectar con el backend local (Puerto 8080 HTTP para carga ultra-rápida y cero advertencias)
  const targetUrl = 'http://127.0.0.1:8080';
  mainWindow.loadURL(targetUrl);

  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
  });

  // Notificar al renderer cuando la ventana cambia de maximizada a normal
  mainWindow.on('maximize', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('window-maximize-changed', true);
    }
  });

  mainWindow.on('unmaximize', () => {
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('window-maximize-changed', false);
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

// IPC Handlers para los controles nativos de ventana
ipcMain.on('window-minimize', () => {
  if (mainWindow) mainWindow.minimize();
});

ipcMain.on('window-maximize', () => {
  if (!mainWindow) return;
  if (mainWindow.isMaximized()) {
    mainWindow.unmaximize();
  } else {
    mainWindow.maximize();
  }
});

ipcMain.on('window-close', () => {
  if (mainWindow) mainWindow.close();
});

ipcMain.handle('window-is-maximized', () => {
  return mainWindow ? mainWindow.isMaximized() : false;
});

app.whenReady().then(async () => {
  await ensureBackendRunning();
  createWindow();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

app.on('window-all-closed', () => {
  // Enviar apagado seguro al backend si fue iniciado por Electron
  try {
    const req = http.request({
      hostname: '127.0.0.1',
      port: 8080,
      path: '/api/system/shutdown',
      method: 'POST'
    });
    req.on('error', () => {});
    req.end();
  } catch (e) {}

  if (pythonProcess) {
    try {
      pythonProcess.kill();
    } catch (e) {}
  }

  if (process.platform !== 'darwin') {
    app.quit();
  }
});
