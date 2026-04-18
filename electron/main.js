const { app, BrowserWindow, dialog, Menu, shell, ipcMain, protocol } = require('electron');
const path = require('path');
const { spawn } = require('child_process');
const net = require('net');
const log = require('electron-log');

// Configure logging
log.transports.file.level = 'info';
log.transports.console.level = 'debug';

let mainWindow = null;
let backendProcess = null;
let backendPort = 5001;

// Determine if we're running in development or production
const isDev = process.env.NODE_ENV === 'development';

/**
 * Find an available port starting from the preferred port.
 */
function findAvailablePort(startPort) {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.listen(startPort, () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
    server.on('error', () => {
      // Port in use, try next
      resolve(findAvailablePort(startPort + 1));
    });
  });
}

/**
 * Get the path to the backend executable.
 * In dev mode, we run server.py directly with Python.
 * In production, we use the PyInstaller-bundled executable.
 */
function getBackendPath() {
  if (isDev) {
    return null; // We'll use python directly in dev
  }
  // Production: bundled executable in resources
  const resourcePath = process.resourcesPath;
  const execName = process.platform === 'win32' ? 'pr-tracker-api.exe' : 'pr-tracker-api';
  return path.join(resourcePath, 'backend', execName);
}

/**
 * Get the user data directory for storing the database.
 */
function getDbPath() {
  const userDataPath = app.getPath('userData');
  return path.join(userDataPath, 'pr_tracker.duckdb');
}

/**
 * Get the schema.sql path.
 */
function getSchemaPath() {
  if (isDev) {
    return path.join(__dirname, '..', 'backend', 'db', 'schema.sql');
  }
  return path.join(process.resourcesPath, 'backend', 'schema.sql');
}

/**
 * Start the Flask backend server.
 */
async function startBackend() {
  backendPort = await findAvailablePort(5001);
  const dbPath = getDbPath();
  const schemaPath = getSchemaPath();

  log.info(`Starting backend on port ${backendPort}`);
  log.info(`Database path: ${dbPath}`);
  log.info(`Schema path: ${schemaPath}`);

  const env = {
    ...process.env,
    DB_PATH: dbPath,
    FLASK_PORT: String(backendPort),
    SCHEMA_PATH: schemaPath,
    // Disable Flask debug mode in production
    FLASK_DEBUG: isDev ? '1' : '0',
    // Signal to Flask that it's running inside Electron (disables reloader)
    RUNNING_IN_ELECTRON: '1',
    // Tell Flask to serve the frontend static files
    FRONTEND_DIR: path.join(__dirname, 'frontend-dist'),
  };

  if (isDev) {
    // Dev mode: run server.py using the project's backend venv Python
    const serverPath = path.join(__dirname, '..', 'backend', 'local', 'server.py');
    const venvPython = path.join(__dirname, '..', 'backend', '.venv', 'bin', 'python3');
    log.info(`Dev mode: running ${venvPython} ${serverPath}`);
    backendProcess = spawn(venvPython, [serverPath], {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  } else {
    // Production: run the bundled executable
    const backendPath = getBackendPath();
    log.info(`Production mode: running ${backendPath}`);
    backendProcess = spawn(backendPath, [], {
      env,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
  }

  backendProcess.stdout.on('data', (data) => {
    log.info(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.stderr.on('data', (data) => {
    log.warn(`[backend] ${data.toString().trim()}`);
  });

  backendProcess.on('error', (err) => {
    log.error(`Backend process error: ${err.message}`);
    dialog.showErrorBox('Backend Error', `Failed to start the backend server: ${err.message}`);
  });

  backendProcess.on('exit', (code, signal) => {
    log.info(`Backend process exited with code ${code}, signal ${signal}`);
    backendProcess = null;
  });

  // Wait for the backend to be ready
  await waitForBackend(backendPort);
  log.info('Backend is ready');
}

/**
 * Poll the backend until it responds.
 */
function waitForBackend(port, retries = 30, delay = 500) {
  return new Promise((resolve, reject) => {
    let attempts = 0;

    const check = () => {
      attempts++;
      const req = require('http').get(`http://127.0.0.1:${port}/api/stats`, (res) => {
        resolve();
      });

      req.on('error', () => {
        if (attempts >= retries) {
          reject(new Error(`Backend did not start after ${retries} attempts`));
        } else {
          setTimeout(check, delay);
        }
      });

      req.setTimeout(1000, () => {
        req.destroy();
        if (attempts >= retries) {
          reject(new Error(`Backend did not start after ${retries} attempts`));
        } else {
          setTimeout(check, delay);
        }
      });
    };

    check();
  });
}

/**
 * Stop the backend server.
 */
function stopBackend() {
  if (backendProcess) {
    log.info('Stopping backend process');
    backendProcess.kill('SIGTERM');

    // Force kill after 5 seconds if it hasn't stopped
    setTimeout(() => {
      if (backendProcess) {
        log.warn('Force killing backend process');
        backendProcess.kill('SIGKILL');
      }
    }, 5000);
  }
}

/**
 * Load the frontend from the Flask backend (same origin, no CORS issues).
 */
function loadFrontendWithPort(win) {
  const url = `http://127.0.0.1:${backendPort}/`;
  log.info(`Loading frontend from ${url}`);
  win.loadURL(url);
}

/**
 * Create the main application window.
 */
async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    title: 'PR Tracker',
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  if (isDev) {
    // In dev, try Vite dev server first, fall back to built frontend
    const viteUrl = 'http://localhost:5173';
    try {
      await new Promise((resolve, reject) => {
        const req = require('http').get(viteUrl, () => resolve());
        req.on('error', () => reject());
        req.setTimeout(1000, () => { req.destroy(); reject(); });
      });
      log.info('Vite dev server detected, loading from localhost:5173');
      mainWindow.loadURL(viteUrl);
      mainWindow.webContents.openDevTools();
    } catch {
      log.info('Vite dev server not running, loading built frontend with port injection');
      loadFrontendWithPort(mainWindow);
    }
  } else {
    loadFrontendWithPort(mainWindow);
  }

  // Open external links in the default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });

  // Enable right-click context menu
  mainWindow.webContents.on('context-menu', (event, params) => {
    const contextMenu = Menu.buildFromTemplate([
      { role: 'undo' },
      { role: 'redo' },
      { type: 'separator' },
      { role: 'cut' },
      { role: 'copy' },
      { role: 'paste' },
      { role: 'selectAll' },
      { type: 'separator' },
      { role: 'reload' },
      { role: 'toggleDevTools' },
    ]);
    contextMenu.popup();
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });
}

/**
 * Build the application menu.
 */
function buildMenu() {
  const template = [
    {
      label: 'File',
      submenu: [
        {
          label: 'Import Data',
          accelerator: 'CmdOrCtrl+I',
          click: () => {
            if (mainWindow) {
              mainWindow.webContents.executeJavaScript(
                'document.querySelector(".import-button")?.click()'
              );
            }
          },
        },
        { type: 'separator' },
        {
          label: 'Reset Database...',
          click: async () => {
            const { response } = await dialog.showMessageBox(mainWindow, {
              type: 'warning',
              buttons: ['Cancel', 'Reset Database'],
              defaultId: 0,
              cancelId: 0,
              title: 'Reset Database',
              message: 'Are you sure you want to reset the database?',
              detail: 'This will delete all snapshots, PR data, and comments. This action cannot be undone.',
            });

            if (response === 1) {
              log.info('Resetting database via API');

              try {
                const http = require('http');
                await new Promise((resolve, reject) => {
                  const req = http.request(
                    `http://127.0.0.1:${backendPort}/api/reset`,
                    { method: 'POST' },
                    (res) => {
                      let body = '';
                      res.on('data', (chunk) => body += chunk);
                      res.on('end', () => {
                        if (res.statusCode === 200) {
                          resolve();
                        } else {
                          reject(new Error(`Reset failed: ${body}`));
                        }
                      });
                    }
                  );
                  req.on('error', reject);
                  req.end();
                });

                // Reload the frontend with a clean state
                if (mainWindow) {
                  loadFrontendWithPort(mainWindow);
                }
                dialog.showMessageBox(mainWindow, {
                  type: 'info',
                  title: 'Database Reset',
                  message: 'Database has been reset successfully.',
                  detail: 'A fresh database has been created.',
                });
              } catch (err) {
                log.error(`Reset failed: ${err.message}`);
                dialog.showErrorBox('Error', `Failed to reset database: ${err.message}`);
              }
            }
          },
        },
        { type: 'separator' },
        { role: 'quit' },
      ],
    },
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
      ],
    },
    {
      label: 'Help',
      submenu: [
        {
          label: 'About Pull Request Tracker Dashboard',
          click: () => {
            dialog.showMessageBox(mainWindow, {
              type: 'info',
              title: 'About Pull Request Tracker Dashboard',
              message: 'Pull Request Tracker Dashboard v1.0.0',
              detail: 'Track and visualize GitHub pull request metrics over time.',
            });
          },
        },
      ],
    },
  ];

  // macOS-specific menu adjustments
  if (process.platform === 'darwin') {
    template.unshift({
      label: app.name,
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideOthers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' },
      ],
    });
  }

  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

// App lifecycle
app.whenReady().then(async () => {
  log.info('App starting...');

  // Register IPC handler for backend port
  ipcMain.handle('get-backend-port', () => backendPort);

  buildMenu();

  try {
    await startBackend();
  } catch (err) {
    log.error(`Failed to start backend: ${err.message}`);
    dialog.showErrorBox(
      'Startup Error',
      `Could not start the backend server.\n\n${err.message}\n\nThe application will now quit.`
    );
    app.quit();
    return;
  }

  await createWindow();
});

app.on('window-all-closed', () => {
  stopBackend();
  app.quit();
});

app.on('before-quit', () => {
  stopBackend();
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});
