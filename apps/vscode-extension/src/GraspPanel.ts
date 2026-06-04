import * as vscode from 'vscode';

const APP_URL = 'https://app.proof-forge.ru';

export class GraspPanel implements vscode.WebviewViewProvider {
  private _view?: vscode.WebviewView;
  constructor(private readonly _extensionUri: vscode.Uri) {}

  resolveWebviewView(view: vscode.WebviewView) {
    this._view = view;
    view.webview.options = {
      enableScripts: true,
      localResourceRoots: [this._extensionUri],
    };
    view.webview.html = this._getHtml();
    view.webview.onDidReceiveMessage(msg => {
      if (msg.type === 'ready') {
        view.webview.postMessage({ type: 'init' });
      }
    });
  }

  navigateTo(path: string) {
    this._view?.webview.postMessage({ type: 'navigate', path });
  }

  postMessage(msg: object) {
    this._view?.webview.postMessage(msg);
  }

  private _getHtml(): string {
    return `<!DOCTYPE html>
<html style="height:100%;margin:0;padding:0">
<body style="height:100%;margin:0;padding:0;overflow:hidden;background:#13120f">
  <iframe
    id="grasp-frame"
    src="${APP_URL}"
    style="width:100%;height:100vh;border:none"
    allow="clipboard-read; clipboard-write; storage-access"
  ></iframe>
  <script>
    const frame = document.getElementById('grasp-frame');
    window.addEventListener('message', e => {
      if (e.data?.type === 'navigate') {
        frame.src = '${APP_URL}' + e.data.path;
      }
    });
    frame.onload = () => window.parent.postMessage({ type: 'ready' }, '*');
  </script>
</body>
</html>`;
  }
}
