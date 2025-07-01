import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as path from 'path';

// 安裝Python依賴
function installPythonDeps(extensionPath: string) {
    const reqPath = path.join(extensionPath, 'requirements.txt');
    spawn('pip', ['install', '-r', reqPath]);
}

export function activate(context: vscode.ExtensionContext) {
    
    installPythonDeps(context.extensionPath);
	// 處理單個PDF
    let processFile = vscode.commands.registerCommand('pdfProcessor.processFile', async (uri: vscode.Uri) => {
		try {
			// 如果沒有傳入 uri，手動選擇文件
			if (!uri) {
				const fileUri = await vscode.window.showOpenDialog({
					canSelectMany: false,
					openLabel: 'Select PDF',
					filters: {
						'PDF files': ['pdf']
					}
				});
				
				if (!fileUri || fileUri.length === 0) {
					return;
				}
				uri = fileUri[0];
			}
			
			const config = vscode.workspace.getConfiguration('pdfProcessor');
			const configOutputPath = config.get<string>('outputPath');
			const outputPath = configOutputPath || path.dirname(uri.fsPath);
			
			await processPDF(uri.fsPath, outputPath, context);
		} catch (error) {
			vscode.window.showErrorMessage(`Error: ${error}`);
		}
	});

    // 處理文件夾
    let processFolder = vscode.commands.registerCommand('pdfProcessor.processFolder', async (uri: vscode.Uri) => {
		try {
			// 如果沒有傳入 uri，手動選擇文件夾
			if (!uri) {
				const folderUri = await vscode.window.showOpenDialog({
					canSelectMany: false,
					canSelectFolders: true,
					canSelectFiles: false,
					openLabel: 'Select Folder'
				});
				
				if (!folderUri || folderUri.length === 0) {
					return;
				}
				uri = folderUri[0];
			}
			
			const config = vscode.workspace.getConfiguration('pdfProcessor');
			const outputPath = config.get<string>('outputPath') || uri.fsPath;
			
			await processPDFFolder(uri.fsPath, outputPath, context);
		} catch (error) {
			vscode.window.showErrorMessage(`Error: ${error}`);
		}
		});
	
	// 選擇模板
	// 這個命令允許用戶選擇一個Markdown模板文件
	let selectTemplate = vscode.commands.registerCommand('pdfProcessor.selectTemplatePath', async () => {
        const fileUri = await vscode.window.showOpenDialog({
            canSelectMany: false,
            openLabel: 'Select Template',
            filters: {
                'Markdown files': ['md']
            }
        });

        if (fileUri && fileUri[0]) {
            const config = vscode.workspace.getConfiguration('pdfProcessor');
            await config.update('templatePath', fileUri[0].fsPath, vscode.ConfigurationTarget.Global);
            vscode.window.showInformationMessage(`Template set to: ${fileUri[0].fsPath}`);
        }
    });

	// 選擇輸出目錄
	let selectOutput = vscode.commands.registerCommand('pdfProcessor.selectOutputPath', async () => {
		const folderUri = await vscode.window.showOpenDialog({
			canSelectMany: false,
			canSelectFolders: true,
			canSelectFiles: false,
			openLabel: 'Select Output Directory'
		});

		if (folderUri && folderUri[0]) {
			const config = vscode.workspace.getConfiguration('pdfProcessor');
			await config.update('outputPath', folderUri[0].fsPath, vscode.ConfigurationTarget.Global);
			vscode.window.showInformationMessage(`Output path set to: ${folderUri[0].fsPath}`);
		}
	});

	// 選擇Bibtex文件
	let selectBibtex = vscode.commands.registerCommand('pdfProcessor.selectBibtexPath', async () => {
		const fileUri = await vscode.window.showOpenDialog({
			canSelectMany: false,
			openLabel: 'Select Bibtex File',
			filters: {
				'Bibtex files': ['bib']
			}
		});

		if (fileUri && fileUri[0]) {
			const config = vscode.workspace.getConfiguration('pdfProcessor');
			await config.update('bibtexPath', fileUri[0].fsPath, vscode.ConfigurationTarget.Global);
			vscode.window.showInformationMessage(`Bibtex path set to: ${fileUri[0].fsPath}`);
		}
	});

    context.subscriptions.push(processFile, processFolder, selectTemplate, selectOutput, selectBibtex);

}

async function processPDF(pdfPath: string, outputPath: string, context: vscode.ExtensionContext) {
    const config = vscode.workspace.getConfiguration('pdfProcessor');
    const apiKey = config.get<string>('openaiApiKey');
    const templatePath = config.get<string>('templatePath');
    
    const pythonScript = path.join(context.extensionPath, 'src', 'python', 'pdf_processor.py');
    
	if (outputPath.startsWith('~')) {
        outputPath = outputPath.replace('~', require('os').homedir());
    }
    
	outputPath = path.resolve(outputPath);

	const args = [
		pythonScript,
		pdfPath,
		'-o', outputPath
	];
    
    if (apiKey) args.push('-k', apiKey);
    if (templatePath) args.push('-t', templatePath);
	const pythonPath = config.get<string>('pythonPath') || 'python';
	console.log('Using Python:', pythonPath);
	console.log('Args:', args);
	console.log('Working directory:', process.cwd());
    
    return new Promise<void>((resolve, reject) => {

		console.log('Using Python:', pythonPath);
		console.log('Args:', args);
    	const process = spawn(pythonPath, args, {
    cwd: context.extensionPath
});
        
        process.stdout.on('data', (data) => {
		const message = data.toString().trim();
		console.log('STDOUT:', message);
		if (message.startsWith('INFO:')) {
			vscode.window.showInformationMessage(message.replace('INFO:', '').trim());
		} else if (message.startsWith('ERROR:')) {
			vscode.window.showErrorMessage(message.replace('ERROR:', '').trim());
		}
	});

	process.stderr.on('data', (data) => {
		const errorMsg = data.toString().trim();
		console.log('STDERR:', errorMsg);
		vscode.window.showErrorMessage(`Python Error: ${errorMsg}`);
	});
        
        process.on('close', (code) => {
            if (code === 0) {
                vscode.window.showInformationMessage('PDF processed successfully!');
                resolve();
            } else {
                reject(new Error(`Process failed with code ${code}`));
            }
        });
    });
}

async function processPDFFolder(folderPath: string, outputPath: string, context: vscode.ExtensionContext) {
    // 類似單文件處理，但傳入文件夾路徑
}

export function deactivate() {}
