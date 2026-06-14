/**
 * Action Registry 
 * Phase 0 of Activities V2 
 * 
 * Provides a reliable wrapper for all UI interactions.
 * Every button must route through an action handler that guarantees:
 * - Loading state UI
 * - Error catching and presentation
 * - Success feedback
 * - Audit logging
 */

export const actionRegistry = {
  logs: [],
  
  logAction(action) {
    const entry = {
      id: crypto.randomUUID(),
      timestamp: new Date().toISOString(),
      ...action
    };
    this.logs.unshift(entry);
    if (this.logs.length > 500) this.logs.pop();
    
    // In dev mode, print the log chain
    console.groupCollapsed(`[Action] ${action.name}`);
    console.log("Component:", action.component);
    console.log("Target:", action.target);
    console.log("Status:", action.status);
    console.log("Details:", action.details);
    console.groupEnd();
    
    // Fire event for UI to update
    window.dispatchEvent(new CustomEvent("rasputin:audit", { detail: entry }));
    return entry;
  }
};

/**
 * Hook to wrap actions with reliable state
 */
export function useReliableAction(componentName) {
  return async function executeAction(actionName, target, asyncFn, setUiState) {
    setUiState({ status: 'loading', message: 'Running...' });
    
    actionRegistry.logAction({
      name: actionName,
      component: componentName,
      target,
      status: 'started'
    });
    
    try {
      const result = await asyncFn();
      setUiState({ status: 'success', message: 'Completed' });
      
      actionRegistry.logAction({
        name: actionName,
        component: componentName,
        target,
        status: 'success',
        details: result
      });
      
      // Auto-clear success state after 2 seconds
      setTimeout(() => setUiState({ status: 'idle', message: '' }), 2000);
      return result;
      
    } catch (error) {
      setUiState({ status: 'failed', message: error.message });
      
      actionRegistry.logAction({
        name: actionName,
        component: componentName,
        target,
        status: 'failed',
        details: error.message,
        stack: error.stack
      });
      
      throw error;
    }
  };
}
