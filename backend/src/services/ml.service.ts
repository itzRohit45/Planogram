import { spawn } from 'child_process';
import path from 'path';
import os from 'os';

const pythonScriptPath = path.resolve(__dirname, '../../../ml-service/audit_engine.py');
// Use the project's virtual environment python if available, handling Windows vs Mac/Linux
const isWindows = os.platform() === 'win32';
const pythonExecutable = path.resolve(
  __dirname, 
  isWindows ? '../../../planogram_env/Scripts/python.exe' : '../../../planogram_env/bin/python3'
);

export interface MLBaselineResult {
  shelf_capacity: number;
  error?: string;
}

export interface MLAuditResult {
  compliance_score: number;
  fill_rate: number;
  report_path: string;
  visual_report_path: string;
  comparison_report: any;
  error?: string;
}

export const runMLBaseline = (imagePath: string): Promise<MLBaselineResult> => {
  return new Promise((resolve, reject) => {
    const process = spawn(pythonExecutable, [pythonScriptPath, '--mode', 'baseline', '--image', imagePath]);

    let outputData = '';
    let errorData = '';

    process.stdout.on('data', (data) => {
      outputData += data.toString();
    });

    process.stderr.on('data', (data) => {
      errorData += data.toString();
    });

    process.on('close', (code) => {
      if (code !== 0 && !outputData.includes('{')) {
        console.error('Python Error:', errorData);
        return resolve({ shelf_capacity: 0, error: 'Failed to process baseline image' });
      }

      try {
        const jsonStr = outputData.substring(outputData.indexOf('{'), outputData.lastIndexOf('}') + 1);
        const result = JSON.parse(jsonStr);
        if (result.error) {
           return resolve({ shelf_capacity: 0, error: result.error });
        }
        resolve(result as MLBaselineResult);
      } catch (e) {
        resolve({ shelf_capacity: 0, error: 'Invalid output from ML service' });
      }
    });
  });
};

export const runMLAudit = (baselinePath: string, auditPath: string, shelfCapacity: number): Promise<MLAuditResult> => {
  return new Promise((resolve, reject) => {
    const process = spawn(pythonExecutable, [
      pythonScriptPath, 
      '--mode', 'audit', 
      '--baseline', baselinePath, 
      '--audit', auditPath,
      '--capacity', shelfCapacity.toString()
    ]);

    let outputData = '';
    let errorData = '';

    process.stdout.on('data', (data) => {
      outputData += data.toString();
    });

    process.stderr.on('data', (data) => {
      const msg = data.toString();
      errorData += msg;
      // Immediately print debug messages from Python to the backend console
      if (msg.includes('[DEBUG]')) {
        console.log(msg.trim());
      }
    });

    process.on('close', (code) => {
      if (code !== 0 && !outputData.includes('{')) {
        console.error('Python Error:', errorData);
        return resolve({ 
          compliance_score: 0, 
          fill_rate: 0, 
          report_path: '', 
          visual_report_path: '', 
          comparison_report: null, 
          error: 'Failed to process audit image' 
        });
      }

      try {
        const jsonStr = outputData.substring(outputData.indexOf('{'), outputData.lastIndexOf('}') + 1);
        const result = JSON.parse(jsonStr);
        if (result.error) {
           return resolve({ 
            compliance_score: 0, 
            fill_rate: 0, 
            report_path: '', 
            visual_report_path: '', 
            comparison_report: null, 
            error: result.error 
          });
        }
        resolve(result as MLAuditResult);
      } catch (e) {
        resolve({ 
          compliance_score: 0, 
          fill_rate: 0, 
          report_path: '', 
          visual_report_path: '', 
          comparison_report: null, 
          error: 'Invalid output from ML service' 
        });
      }
    });
  });
};
