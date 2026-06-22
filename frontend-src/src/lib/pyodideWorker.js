import { loadPyodide } from "pyodide";

let pyodideReadyPromise;

async function initPyodide() {
  // Load Pyodide from CDN to avoid huge local bundle sizes
  // Vite handles the rest
  const pyodide = await loadPyodide({
    indexURL: "https://cdn.jsdelivr.net/pyodide/v0.25.0/full/"
  });
  return pyodide;
}

pyodideReadyPromise = initPyodide();

self.onmessage = async (event) => {
  const { id, python } = event.data;
  
  if (!python) return;

  try {
    const pyodide = await pyodideReadyPromise;
    
    // Create a custom stdout buffer for this execution
    let outputBuffer = "";
    pyodide.setStdout({
      batched: (msg) => {
        outputBuffer += msg + "\n";
        self.postMessage({ id, output: outputBuffer });
      }
    });

    pyodide.setStderr({
      batched: (msg) => {
        outputBuffer += msg + "\n";
        self.postMessage({ id, output: outputBuffer });
      }
    });

    await pyodide.loadPackagesFromImports(python);
    let results = await pyodide.runPythonAsync(python);
    
    self.postMessage({ id, results, output: outputBuffer, completed: true });
  } catch (error) {
    self.postMessage({ id, error: error.message, completed: true });
  }
};
