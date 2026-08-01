<template>
  <div class="workspaces-container">
    <header>
      <h1>Workspaces</h1>
      <div class="workspace-switcher">
        <button 
          v-for="workspace in workspaces" 
          :key="workspace.id"
          :class="{ active: currentWorkspace === workspace.id }"
          @click="switchWorkspace(workspace.id)"
        >
          {{ workspace.name }}
        </button>
      </div>
    </header>
    
    <main class="workspace-grid">
      <div class="workspace-card" v-for="workspace in workspaces" :key="workspace.id">
        <div class="workspace-header">
          <h2>{{ workspace.name }}</h2>
          <div class="workspace-tools">
            <button v-for="tool in workspace.tools" :key="tool.id">
              {{ tool.name }}
            </button>
          </div>
        </div>
        
        <div class="workspace-features">
          <div class="feature-item" v-for="feature in workspace.features" :key="feature.id">
            <span class="feature-icon">{{ feature.icon }}</span>
            <span class="feature-name">{{ feature.name }}</span>
          </div>
        </div>
      </div>
    </main>

    <div class="status-indicators">
      <div class="status-bar">
        <div class="status-item">
          <span class="status-icon">✓</span>
          <span class="status-text">Ready</span>
        </div>
        <div class="progress-bar">
          <div class="progress-fill" style="width: 100%"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { ref } from 'vue';

export default {
  setup() {
    const currentWorkspace = ref('general');
    const workspaces = ref([
      {
        id: 'research',
        name: 'Research',
        tools: ['Web Search', 'Deep Research', 'Document Upload', 'Synthesis'],
        features: ['Recursive Search', 'Citation Management', 'Research Tracking']
      },
      {
        id: 'documents',
        name: 'Documents',
        tools: ['Document Upload', 'RAG Processing', 'Graph Visualization', 'Entity Extraction'],
        features: ['Knowledge Graph Integration', 'Document Analysis', 'Export Options']
      },
      {
        id: 'coding',
        name: 'Coding',
        tools: ['Code Editor', 'Script Debugging', 'Terminal Access', 'Auto-Refactoring'],
        features: ['Syntax Highlighting', 'Code Versioning', 'External Integration']
      },
      {
        id: 'general',
        name: 'General',
        tools: ['Basic Chat', 'Quick Tasks', 'System Settings'],
        features: ['Task Prioritization', 'Quick Actions', 'User Preferences']
      }
    ]);

    const switchWorkspace = (workspaceId) => {
      currentWorkspace.value = workspaceId;
      // Implement workspace switching logic here
    };

    return {
      currentWorkspace,
      workspaces
    };
  }
};
</script>

<style scoped>
.workspaces-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
}

.workspace-switcher {
  margin-bottom: 20px;
}

.workspace-switcher button {
  padding: 8px 16px;
  margin-right: 8px;
  border: none;
  border-radius: 4px;
  background-color: #f0f0f0;
  cursor: pointer;
  transition: background-color 0.2s;
}

.workspace-switcher button.active {
  background-color: #007bff;
  color: white;
}

.workspace-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 20px;
}

.workspace-card {
  background: white;
  border-radius: 8px;
  padding: 16px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.workspace-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.workspace-tools button {
  padding: 4px 8px;
  margin-right: 4px;
  border: none;
  border-radius: 4px;
  background-color: #f8f9fa;
  cursor: pointer;
}

.workspace-features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 12px;
}

.feature-item {
  display: flex;
  align-items: center;
  padding: 8px;
  border-radius: 4px;
  background-color: #f8f9fa;
}

.feature-icon {
  margin-right: 8px;
}

.status-indicators {
  margin-top: 20px;
  padding: 16px;
  background: #f8f9fa;
  border-radius: 8px;
}

.status-bar {
  display: flex;
  gap: 16px;
}

.progress-bar {
  height: 8px;
  background-color: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background-color: #007bff;
  transition: width 0.3s ease;
}
</style>