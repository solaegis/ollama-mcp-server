/**
 * extension.ts — Ollama Local LLM VS Code / Cursor extension
 *
 * Architecture:
 *   - Launches python/ollama_client.py as a child process on activation
 *   - Communicates via newline-delimited JSON over stdin/stdout
 *   - Status bar shows active model + Ollama health at a glance
 *   - Commands: pickModel, sendSelection, rewriteSelection, openPanel, pullModel
 *   - Webview panel provides a persistent chat UI
 */

import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';
import * as fs from 'fs';

// ─── Python bridge ─────────────────────────────────────────────────────────

interface RpcResponse {
  id: number;
  result: unknown;
  error: string | null;
}

class PythonBridge {
  private proc: cp.ChildProcess | null = null;
  private pending = new Map<number, { resolve: (v: unknown) => void; reject: (e: Error) => void }>();
  private nextId = 1;
  private buffer = '';
  private ready = false;
  private output: vscode.OutputChannel;

  constructor(output: vscode.OutputChannel) {
    this.output = output;
  }

  start(scriptPath: string, env: NodeJS.ProcessEnv): void {
    const python = this.findPython();
    this.output.appendLine(`Starting Python backend: ${python} ${scriptPath}`);

    this.proc = cp.spawn(python, [scriptPath], {
      env: { ...process.env, ...env },
      stdio: ['pipe', 'pipe', 'pipe'],
    });

    this.proc.stdout!.on('data', (chunk: Buffer) => {
      this.buffer += chunk.toString();
      const lines = this.buffer.split('\n');
      this.buffer = lines.pop() ?? '';
      for (const line of lines) {
        if (!line.trim()) { continue; }
        try {
          const msg = JSON.parse(line) as { ready?: boolean } & RpcResponse;
          if (msg.ready) {
            this.ready = true;
            this.output.appendLine('Python backend ready');
            return;
          }
          const p = this.pending.get(msg.id);
          if (p) {
            this.pending.delete(msg.id);
            if (msg.error) { p.reject(new Error(msg.error)); }
            else { p.resolve(msg.result); }
          }
        } catch {
          this.output.appendLine(`Unparseable line: ${line}`);
        }
      }
    });

    this.proc.stderr!.on('data', (chunk: Buffer) => {
      this.output.appendLine(`[py] ${chunk.toString().trim()}`);
    });

    this.proc.on('exit', (code) => {
      this.output.appendLine(`Python backend exited (${code})`);
      this.ready = false;
    });
  }

  async call<T>(method: string, params: Record<string, unknown> = {}): Promise<T> {
    if (!this.proc || !this.ready) {
      throw new Error('Ollama backend not running. Check the Ollama output channel.');
    }
    const id = this.nextId++;
    const line = JSON.stringify({ id, method, params }) + '\n';
    return new Promise<T>((resolve, reject) => {
      this.pending.set(id, {
        resolve: (v) => resolve(v as T),
        reject,
      });
      // Timeout safety: 5 min for slow models
      setTimeout(() => {
        if (this.pending.has(id)) {
          this.pending.delete(id);
          reject(new Error(`Request ${id} (${method}) timed out`));
        }
      }, 300_000);
      this.proc!.stdin!.write(line);
    });
  }

  stop(): void {
    this.proc?.kill();
    this.proc = null;
    this.ready = false;
  }

  isReady(): boolean { return this.ready; }

  private findPython(): string {
    // Prefer python3 on PATH; fall back to python
    for (const bin of ['python3', 'python']) {
      try {
        cp.execSync(`which ${bin}`, { stdio: 'ignore' });
        return bin;
      } catch { /* try next */ }
    }
    return 'python3';
  }
}

// ─── State ─────────────────────────────────────────────────────────────────

let bridge: PythonBridge;
let statusBar: vscode.StatusBarItem;
let chatPanel: vscode.WebviewPanel | undefined;
let activeModel: string;
let output: vscode.OutputChannel;

function cfg() { return vscode.workspace.getConfiguration('ollama'); }
function getModel() { return activeModel || cfg().get<string>('defaultModel', 'qwen2.5-coder:7b'); }

// ─── Status bar ────────────────────────────────────────────────────────────

function updateStatusBar(text: string, tooltip?: string, color?: vscode.ThemeColor) {
  statusBar.text = `$(circuit-board) ${text}`;
  statusBar.tooltip = tooltip ?? 'Ollama Local LLM — click to switch model';
  statusBar.color = color;
  statusBar.show();
}

async function refreshStatusBar() {
  if (!bridge.isReady()) {
    updateStatusBar('Ollama: offline', 'Backend not running', new vscode.ThemeColor('statusBarItem.warningForeground'));
    return;
  }
  try {
    const health = await bridge.call<Record<string, boolean>>('health');
    const loaded = await bridge.call<Array<{ name: string; vram_gb: number }>>('loaded_models');
    const ollamaOk = health['ollama'] ?? false;
    const litellmOk = health['litellm'] ?? false;
    const model = getModel();
    const inMem = loaded.some(m => m.name === model);
    const indicator = ollamaOk ? (inMem ? '●' : '○') : '✕';
    const stack = litellmOk ? '+stack' : '';
    updateStatusBar(`${indicator} ${model} ${stack}`.trim(),
      `Model: ${model}\nOllama: ${ollamaOk ? 'online' : 'offline'}\nLiteLLM: ${litellmOk ? 'online' : 'offline'}\nLoaded in memory: ${inMem}`);
  } catch {
    updateStatusBar(`${getModel()} — error`, undefined, new vscode.ThemeColor('statusBarItem.errorForeground'));
  }
}

// ─── Commands ──────────────────────────────────────────────────────────────

async function cmdPickModel() {
  if (!bridge.isReady()) {
    vscode.window.showWarningMessage('Ollama backend not running.');
    return;
  }
  const models = await bridge.call<Array<{ name: string; size_gb: number; params: string }>>('list_models');
  if (models.length === 0) {
    const pull = await vscode.window.showWarningMessage('No models found.', 'Pull a model');
    if (pull) { await cmdPullModel(); }
    return;
  }
  const loaded = await bridge.call<Array<{ name: string }>>('loaded_models');
  const loadedNames = new Set(loaded.map(m => m.name));

  const items: vscode.QuickPickItem[] = models.map(m => ({
    label: (loadedNames.has(m.name) ? '● ' : '○ ') + m.name,
    description: `${m.params}  ${m.size_gb} GB`,
    detail: loadedNames.has(m.name) ? 'loaded in memory' : '',
  }));

  const pick = await vscode.window.showQuickPick(items, {
    title: 'Select Ollama model',
    placeHolder: `Current: ${getModel()}`,
  });
  if (!pick) { return; }
  activeModel = pick.label.replace(/^[●○] /, '');
  await cfg().update('defaultModel', activeModel, vscode.ConfigurationTarget.Global);
  await refreshStatusBar();
  vscode.window.showInformationMessage(`Switched to ${activeModel}`);
}

async function cmdSendSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showWarningMessage('Select some text first.');
    return;
  }
  const selected = editor.document.getText(editor.selection);
  const lang = editor.document.languageId;

  const prompt = await vscode.window.showInputBox({
    prompt: 'Instruction for the LLM (leave blank to just analyse selection)',
    placeHolder: 'e.g. explain this, find bugs, write a test',
  });

  const messages = [
    { role: 'system', content: `You are a helpful coding assistant. The code is ${lang}.` },
    { role: 'user', content: prompt ? `${prompt}\n\n\`\`\`${lang}\n${selected}\n\`\`\`` : selected },
  ];

  await runChatAndShowPanel(messages, `Ollama: ${prompt || 'analyse selection'}`);
}

async function cmdRewriteSelection() {
  const editor = vscode.window.activeTextEditor;
  if (!editor || editor.selection.isEmpty) {
    vscode.window.showWarningMessage('Select some text first.');
    return;
  }
  const selected = editor.document.getText(editor.selection);
  const lang = editor.document.languageId;

  const messages = [
    {
      role: 'system',
      content: `You are an expert ${lang} developer. Rewrite the provided code to be cleaner, more idiomatic, and well-commented. Return ONLY the rewritten code with no extra explanation.`,
    },
    { role: 'user', content: `\`\`\`${lang}\n${selected}\n\`\`\`` },
  ];

  const result = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `Rewriting with ${getModel()}…`, cancellable: false },
    () => bridge.call<string>('chat', { model: getModel(), messages, temperature: cfg().get('temperature', 0.7) })
  );

  // Strip markdown code fences if model wrapped the output
  const clean = result.replace(/^```[\w]*\n?/, '').replace(/\n?```$/, '');

  // Offer to replace selection or open in diff
  const action = await vscode.window.showInformationMessage(
    'Rewrite complete', { modal: false }, 'Replace selection', 'Open diff', 'Copy'
  );
  if (action === 'Replace selection') {
    const edit = new vscode.WorkspaceEdit();
    edit.replace(editor.document.uri, editor.selection, clean);
    await vscode.workspace.applyEdit(edit);
  } else if (action === 'Open diff') {
    const original = await vscode.workspace.openTextDocument({ content: selected, language: lang });
    const rewritten = await vscode.workspace.openTextDocument({ content: clean, language: lang });
    await vscode.commands.executeCommand('vscode.diff', original.uri, rewritten.uri, 'Original ↔ Rewritten');
  } else if (action === 'Copy') {
    await vscode.env.clipboard.writeText(clean);
  }
}

async function cmdOpenPanel() {
  if (chatPanel) {
    chatPanel.reveal();
    return;
  }
  createChatPanel();
}

async function cmdPullModel() {
  const name = await vscode.window.showInputBox({
    prompt: 'Model to pull from Ollama registry',
    placeHolder: 'e.g. llama3.3:70b, qwen2.5-coder:14b, phi4:latest',
    value: '',
  });
  if (!name) { return; }

  await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `Pulling ${name}…`, cancellable: false },
    async () => {
      const status = await bridge.call<string>('pull_model', { model: name });
      vscode.window.showInformationMessage(`Pull ${name}: ${status}`);
      await refreshStatusBar();
    }
  );
}

// ─── Chat webview panel ────────────────────────────────────────────────────

function createChatPanel() {
  chatPanel = vscode.window.createWebviewPanel(
    'ollamaChat',
    `Ollama: ${getModel()}`,
    vscode.ViewColumn.Beside,
    { enableScripts: true, retainContextWhenHidden: true }
  );

  chatPanel.webview.html = getChatHtml(getModel());

  chatPanel.webview.onDidReceiveMessage(async (msg: { type: string; text?: string; model?: string }) => {
    if (msg.type === 'send' && msg.text) {
      const messages = [
        { role: 'system', content: 'You are a helpful assistant.' },
        { role: 'user', content: msg.text },
      ];
      chatPanel!.webview.postMessage({ type: 'thinking' });
      try {
        const reply = await bridge.call<string>('chat', {
          model: getModel(),
          messages,
          temperature: cfg().get('temperature', 0.7),
        });
        chatPanel!.webview.postMessage({ type: 'reply', text: reply, model: getModel() });
      } catch (e: unknown) {
        const err = e instanceof Error ? e.message : String(e);
        chatPanel!.webview.postMessage({ type: 'error', text: err });
      }
    } else if (msg.type === 'switchModel') {
      await cmdPickModel();
      chatPanel!.title = `Ollama: ${getModel()}`;
      chatPanel!.webview.postMessage({ type: 'modelChanged', model: getModel() });
    }
  });

  chatPanel.onDidDispose(() => { chatPanel = undefined; });
}

async function runChatAndShowPanel(messages: Array<{ role: string; content: string }>, title: string) {
  if (!bridge.isReady()) {
    vscode.window.showErrorMessage('Ollama backend not running.');
    return;
  }

  const reply = await vscode.window.withProgress(
    { location: vscode.ProgressLocation.Notification, title: `${title} with ${getModel()}…`, cancellable: false },
    () => bridge.call<string>('chat', { model: getModel(), messages, temperature: cfg().get('temperature', 0.7) })
  );

  // Show result in a read-only document (quick, no webview needed for one-shot responses)
  const doc = await vscode.workspace.openTextDocument({ content: reply, language: 'markdown' });
  await vscode.window.showTextDocument(doc, { viewColumn: vscode.ViewColumn.Beside, preview: true });
}

// ─── Chat panel HTML ───────────────────────────────────────────────────────

function getChatHtml(model: string): string {
  return `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Ollama Chat</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: var(--vscode-font-family);
    font-size: var(--vscode-font-size);
    color: var(--vscode-editor-foreground);
    background: var(--vscode-editor-background);
    display: flex; flex-direction: column; height: 100vh;
  }
  #header {
    padding: 8px 12px; border-bottom: 1px solid var(--vscode-panel-border);
    display: flex; align-items: center; gap: 8px; flex-shrink: 0;
  }
  #model-label {
    font-size: 11px; opacity: 0.7; flex: 1;
  }
  #switch-btn {
    font-size: 11px; padding: 2px 8px; cursor: pointer;
    background: var(--vscode-button-secondaryBackground);
    color: var(--vscode-button-secondaryForeground);
    border: none; border-radius: 3px;
  }
  #switch-btn:hover { background: var(--vscode-button-secondaryHoverBackground); }
  #messages {
    flex: 1; overflow-y: auto; padding: 12px;
    display: flex; flex-direction: column; gap: 12px;
  }
  .msg { display: flex; flex-direction: column; gap: 4px; max-width: 100%; }
  .msg-role {
    font-size: 10px; font-weight: 600; opacity: 0.5; text-transform: uppercase; letter-spacing: 0.05em;
  }
  .msg-body {
    padding: 8px 10px; border-radius: 6px; white-space: pre-wrap; word-break: break-word; line-height: 1.5;
  }
  .user .msg-body { background: var(--vscode-inputOption-activeBackground); }
  .assistant .msg-body { background: var(--vscode-editor-inactiveSelectionBackground); }
  .thinking .msg-body { opacity: 0.5; font-style: italic; }
  .error .msg-body { background: var(--vscode-inputValidation-errorBackground); color: var(--vscode-inputValidation-errorForeground); }
  #input-row {
    padding: 8px 12px; border-top: 1px solid var(--vscode-panel-border);
    display: flex; gap: 6px; flex-shrink: 0;
  }
  #input {
    flex: 1; resize: none; min-height: 36px; max-height: 120px;
    padding: 6px 8px; border-radius: 4px;
    background: var(--vscode-input-background); color: var(--vscode-input-foreground);
    border: 1px solid var(--vscode-input-border, transparent); font-family: inherit; font-size: inherit;
  }
  #input:focus { outline: 1px solid var(--vscode-focusBorder); }
  #send-btn {
    padding: 6px 14px; cursor: pointer;
    background: var(--vscode-button-background); color: var(--vscode-button-foreground);
    border: none; border-radius: 4px; font-size: inherit; align-self: flex-end;
  }
  #send-btn:hover { background: var(--vscode-button-hoverBackground); }
  #send-btn:disabled { opacity: 0.5; cursor: default; }
  code { font-family: var(--vscode-editor-font-family); font-size: 0.9em; }
  pre { background: var(--vscode-textCodeBlock-background); padding: 8px; border-radius: 4px; overflow-x: auto; margin: 4px 0; }
</style>
</head>
<body>
<div id="header">
  <span id="model-label">Model: <strong id="model-name">${model}</strong></span>
  <button id="switch-btn">Switch model</button>
</div>
<div id="messages"></div>
<div id="input-row">
  <textarea id="input" placeholder="Ask something… (Shift+Enter for newline, Enter to send)" rows="2"></textarea>
  <button id="send-btn">Send</button>
</div>
<script>
  const vscode = acquireVsCodeApi();
  const messagesEl = document.getElementById('messages');
  const inputEl = document.getElementById('input');
  const sendBtn = document.getElementById('send-btn');
  const modelName = document.getElementById('model-name');

  function addMessage(role, text) {
    const div = document.createElement('div');
    div.className = 'msg ' + role;
    const roleEl = document.createElement('div');
    roleEl.className = 'msg-role';
    roleEl.textContent = role === 'assistant' ? 'ollama' : role;
    const body = document.createElement('div');
    body.className = 'msg-body';
    // Simple code fence rendering
    body.innerHTML = text
      .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;')
      .replace(/\`\`\`([\\s\\S]*?)\`\`\`/g, '<pre><code>$1</code></pre>')
      .replace(/\`([^\`]+)\`/g, '<code>$1</code>');
    div.appendChild(roleEl);
    div.appendChild(body);
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  let thinkingEl = null;

  function send() {
    const text = inputEl.value.trim();
    if (!text) return;
    inputEl.value = '';
    inputEl.style.height = '';
    sendBtn.disabled = true;
    addMessage('user', text);
    thinkingEl = addMessage('thinking', '…generating');
    vscode.postMessage({ type: 'send', text });
  }

  sendBtn.addEventListener('click', send);
  inputEl.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); send(); }
  });
  inputEl.addEventListener('input', () => {
    inputEl.style.height = 'auto';
    inputEl.style.height = Math.min(inputEl.scrollHeight, 120) + 'px';
  });
  document.getElementById('switch-btn').addEventListener('click', () => {
    vscode.postMessage({ type: 'switchModel' });
  });

  window.addEventListener('message', e => {
    const msg = e.data;
    if (msg.type === 'thinking') {
      // already shown
    } else if (msg.type === 'reply') {
      if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
      addMessage('assistant', msg.text);
      sendBtn.disabled = false;
    } else if (msg.type === 'error') {
      if (thinkingEl) { thinkingEl.remove(); thinkingEl = null; }
      addMessage('error', 'Error: ' + msg.text);
      sendBtn.disabled = false;
    } else if (msg.type === 'modelChanged') {
      modelName.textContent = msg.model;
    }
  });
</script>
</body>
</html>`;
}

// ─── Extension lifecycle ────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext) {
  output = vscode.window.createOutputChannel('Ollama Local LLM');
  bridge = new PythonBridge(output);

  // Locate the Python script relative to the extension directory
  const scriptPath = path.join(context.extensionPath, 'python', 'ollama_client.py');
  if (!fs.existsSync(scriptPath)) {
    vscode.window.showErrorMessage(`Ollama extension: Python backend not found at ${scriptPath}`);
    return;
  }

  // Build env from settings
  const c = cfg();
  const env: NodeJS.ProcessEnv = {
    OLLAMA_BASE_URL: c.get('baseUrl', 'http://localhost:11434'),
    LITELLM_BASE_URL: c.get('litellmUrl', 'http://localhost:4000'),
    LITELLM_MASTER_KEY: c.get('litellmKey', 'sk-local-dev-key'),
  };

  bridge.start(scriptPath, env);
  activeModel = c.get('defaultModel', 'qwen2.5-coder:7b');

  // Status bar — click opens model picker
  statusBar = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
  statusBar.command = 'ollama.pickModel';
  context.subscriptions.push(statusBar);

  updateStatusBar('Ollama: starting…');

  // Refresh status bar after backend warms up, then every 60s
  setTimeout(() => refreshStatusBar(), 3000);
  const timer = setInterval(() => refreshStatusBar(), 60_000);
  context.subscriptions.push({ dispose: () => clearInterval(timer) });

  // Re-read settings if user changes them
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration(e => {
      if (e.affectsConfiguration('ollama')) {
        activeModel = cfg().get('defaultModel', 'qwen2.5-coder:7b');
        refreshStatusBar();
      }
    })
  );

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('ollama.pickModel', cmdPickModel),
    vscode.commands.registerCommand('ollama.sendSelection', cmdSendSelection),
    vscode.commands.registerCommand('ollama.rewriteSelection', cmdRewriteSelection),
    vscode.commands.registerCommand('ollama.openPanel', cmdOpenPanel),
    vscode.commands.registerCommand('ollama.pullModel', cmdPullModel),
  );

  output.appendLine('Ollama Local LLM extension activated');
}

export function deactivate() {
  bridge?.stop();
  chatPanel?.dispose();
}
