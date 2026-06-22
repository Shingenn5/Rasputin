import React, { useState, useEffect, useRef } from 'react';
import { Play, Square, Terminal } from 'lucide-react';
import PyodideWorker from '../lib/pyodideWorker.js?worker';

// Singleton worker for Pyodide
let pyodideWorker = null;
let callbacks = {};
let messageId = 0;

function getWorker() {
  if (!pyodideWorker) {
    pyodideWorker = new PyodideWorker();
    pyodideWorker.onmessage = (event) => {
      const { id, ...data } = event.data;
      if (callbacks[id]) {
        callbacks[id](data);
        if (data.completed || data.error) {
          delete callbacks[id];
        }
      }
    };
  }
  return pyodideWorker;
}

export function CodeSandbox({ inline, className, children, ...props }) {
  const match = /language-(\w+)/.exec(className || '');
  const lang = match ? match[1].toLowerCase() : 'text';
  const isPython = lang === 'python';
  const isHtml = lang === 'html';
  const code = String(children).replace(/\n$/, '');
  
  const [output, setOutput] = useState('');
  const [isRunning, setIsRunning] = useState(false);
  const [error, setError] = useState(null);
  const [activeTab, setActiveTab] = useState(isHtml ? 'preview' : 'code');
  
  if (inline) {
    return <code className={className} {...props}>{children}</code>;
  }

  const handleRun = () => {
    setIsRunning(true);
    setOutput('');
    setError(null);
    
    const worker = getWorker();
    const id = ++messageId;
    
    callbacks[id] = (data) => {
      if (data.output) setOutput(data.output);
      if (data.error) setError(data.error);
      if (data.completed || data.error) setIsRunning(false);
    };
    
    worker.postMessage({ id, python: code });
  };

  return (
    <div className="code-sandbox" style={{ position: 'relative', margin: '1em 0', borderRadius: '8px', overflow: 'hidden', border: '1px solid var(--cc-border)', display: 'flex', flexDirection: 'column' }}>
      <div className="code-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0 12px', backgroundColor: 'var(--cc-surface)', borderBottom: '1px solid var(--cc-border)', height: '40px' }}>
        <div style={{ display: 'flex', gap: '16px', height: '100%' }}>
          {isHtml && (
            <button
              type="button"
              onClick={() => setActiveTab('preview')}
              style={{
                background: 'none', border: 'none', padding: '0', margin: 0,
                color: activeTab === 'preview' ? 'var(--ras-primary)' : 'var(--cc-muted)',
                borderBottom: activeTab === 'preview' ? '2px solid var(--ras-primary)' : '2px solid transparent',
                cursor: 'pointer', fontSize: '0.85rem', fontWeight: activeTab === 'preview' ? 'bold' : 'normal'
              }}
            >
              Preview
            </button>
          )}
          <button
            type="button"
            onClick={() => setActiveTab('code')}
            style={{
              background: 'none', border: 'none', padding: '0', margin: 0,
              color: activeTab === 'code' ? 'var(--ras-primary)' : 'var(--cc-muted)',
              borderBottom: activeTab === 'code' ? '2px solid var(--ras-primary)' : '2px solid transparent',
              cursor: 'pointer', fontSize: '0.85rem', fontWeight: activeTab === 'code' ? 'bold' : 'normal'
            }}
          >
            Code
          </button>
        </div>
        
        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', textTransform: 'uppercase' }}>{lang}</span>
          {isPython && activeTab === 'code' && (
            <button 
              type="button" 
              onClick={handleRun} 
              disabled={isRunning}
              style={{ 
                display: 'flex', alignItems: 'center', gap: '4px', padding: '4px 8px', 
                fontSize: '0.8rem', cursor: isRunning ? 'not-allowed' : 'pointer',
                backgroundColor: 'var(--ras-primary)', color: '#000', border: 'none', borderRadius: '4px'
              }}
            >
              {isRunning ? <Square size={12} /> : <Play size={12} />}
              {isRunning ? 'Running...' : 'Run'}
            </button>
          )}
        </div>
      </div>
      
      {activeTab === 'code' && (
        <div style={{ padding: '12px', backgroundColor: '#1e1e1e', color: '#d4d4d4', overflowX: 'auto' }}>
          <code className={className} {...props}>{code}</code>
        </div>
      )}

      {activeTab === 'preview' && isHtml && (
        <div style={{ width: '100%', minHeight: '400px', backgroundColor: '#fff' }}>
          <iframe 
            srcDoc={code} 
            sandbox="allow-scripts"
            title="HTML Artifact Preview" 
            style={{ width: '100%', height: '400px', border: 'none' }}
          />
        </div>
      )}
      
      {activeTab === 'code' && (output || error || isRunning) && (
        <div className="code-output" style={{ padding: '12px', backgroundColor: '#000', color: '#fff', borderTop: '1px solid #333', fontFamily: 'monospace', fontSize: '0.85rem', whiteSpace: 'pre-wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px', color: 'var(--cc-muted)', marginBottom: '8px', textTransform: 'uppercase', fontSize: '0.7rem' }}>
            <Terminal size={12} /> Console Output
          </div>
          {output && <div style={{ color: '#e5e5e5' }}>{output}</div>}
          {error && <div style={{ color: 'var(--ras-danger)' }}>{error}</div>}
          {isRunning && !output && <div style={{ color: 'var(--cc-muted)' }}>Executing...</div>}
        </div>
      )}
    </div>
  );
}
