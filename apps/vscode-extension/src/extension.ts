import * as vscode from 'vscode';
import { GraspPanel } from './GraspPanel';

export function activate(ctx: vscode.ExtensionContext) {
  const provider = new GraspPanel(ctx.extensionUri);
  ctx.subscriptions.push(
    vscode.window.registerWebviewViewProvider('grasp.panel', provider)
  );
  ctx.subscriptions.push(
    vscode.commands.registerCommand('grasp.openPanel', () => {
      vscode.commands.executeCommand('workbench.view.extension.grasp-container');
    })
  );
  ctx.subscriptions.push(
    vscode.commands.registerCommand('grasp.addCurrentFile', async (uri: vscode.Uri) => {
      const filePath = uri?.fsPath ?? vscode.window.activeTextEditor?.document.fileName;
      if (filePath) {
        provider.navigateTo('/topics/new');
        provider.postMessage({ type: 'prefillFile', path: filePath });
      }
    })
  );
  ctx.subscriptions.push(
    vscode.window.registerUriHandler({
      handleUri(uri: vscode.Uri) {
        if (uri.path === '/auth') {
          const token = new URLSearchParams(uri.query).get('token');
          if (token) {
            vscode.commands.executeCommand('workbench.view.extension.grasp-container');
            provider.postMessage({ type: 'auth_token', token });
          }
        }
      }
    })
  );
}

export function deactivate() {}
