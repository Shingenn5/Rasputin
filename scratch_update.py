import sys

with open('frontend-src/src/features/workspaces/WorkspacesView.jsx', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_content = """      <div className="w2-main-grid">
        
        {/* Left Column: Explorer Sidebar */}
        <div className="w2-column w2-column-nav">
          
          <div className="w2-section" style={{ gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="w2-section-title">Approved Folders</h2>
              <button className="icon-button" type="button" onClick={loadWorkspaceRoots} aria-label="Refresh roots">
                <RefreshCw size={14} />
              </button>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column' }}>
              {workspaceRoots.map((root) => {
                const rootPath = root.path || root.root;
                const rootId = root.id;
                const displayName = root.displayName || root.display_name || root.name || displayWorkspaceName(rootPath);
                const active = rootId === activeId || normalizePath(rootPath) === normalizePath(workspace.activePath);
                return (
                  <div key={rootId} className={`w2-tree-item ${active ? 'is-active' : ''}`} onClick={() => browseWorkspace(rootId)} style={{ fontWeight: active ? 600 : 400 }}>
                    <FolderOpen size={16} className="w2-tree-icon" />
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{displayName}</span>
                  </div>
                );
              })}
              {workspaceRoots.length === 0 && <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', padding: '4px 8px' }}>No approved folders.</div>}
              <div 
                className="w2-tree-item" 
                style={{ color: 'var(--cc-primary)', marginTop: '4px' }}
                onClick={() => setShowAddModal(true)}
              >
                <PlusCircle size={16} className="w2-tree-icon" style={{ color: 'var(--cc-primary)' }} />
                <span>Add Folder</span>
              </div>
            </div>
          </div>

          <hr style={{ borderColor: 'var(--cc-border)', margin: '4px 0' }} />

          <div className="w2-section" style={{ flex: 1, gap: '8px' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 className="w2-section-title" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>EXPLORER: {currentFolder}</h2>
            </div>
            
            <div className="w2-breadcrumbs" style={{ fontSize: '0.75rem', padding: '0 8px' }}>
              {breadcrumbs.map((crumb, index) => (
                <React.Fragment key={crumb.path || "root"}>
                  {index > 0 && <ChevronRight size={12} />}
                  <button type="button" onClick={() => browseWorkspace(currentRoot.id, crumb.path)} style={{ color: 'var(--cc-muted)' }}>
                    {crumb.label}
                  </button>
                </React.Fragment>
              ))}
            </div>
            
            <div style={{ padding: '0 8px' }}>
              <input 
                className="w2-input" 
                style={{ padding: '4px 8px', fontSize: '0.75rem' }}
                placeholder="Search..." 
                value={filter} 
                onChange={e => setFilter(e.target.value)} 
              />
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', flex: 1, overflowY: 'auto', marginTop: '4px' }}>
              {filteredEntries.map((entry) => (
                <div 
                  key={`${entry.kind}-${entry.path}`} 
                  className={`w2-tree-item ${selectedEntry?.path === entry.path ? 'is-active' : ''}`}
                  onClick={() => openEntry(entry)}
                  title={`${entry.kind === "folder" ? "Folder" : entry.extension || "File"}\\nSize: ${entry.kind === "folder" ? "--" : formatBytes(entry.sizeBytes)}\\nModified: ${formatTime(entry.modifiedAt)}`}
                >
                  <EntryIcon entry={entry} className="w2-tree-icon" />
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    {entry.displayName || entry.name}
                  </span>
                </div>
              ))}
              {filteredEntries.length === 0 && (
                <div style={{ fontSize: '0.75rem', color: 'var(--cc-muted)', padding: '8px', textAlign: 'center' }}>
                  {entries.length ? "No matching items." : "Folder is empty."}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Right Column: Editor / Dashboard */}
        <div className="w2-column w2-column-explorer" style={{ display: 'flex', flexDirection: 'column' }}>
          {previewMode ? (
            // Full-Pane Preview Mode
            <div className="w2-section" style={{ height: '100%', display: 'flex', flexDirection: 'column' }}>
              <div className="d-flex justify-content-between align-items-center mb-2">
                <h2 className="w2-section-title mb-0 d-flex align-items-center" style={{ textTransform: 'none', color: 'var(--cc-text)', fontSize: '1rem' }}>
                  <FileText className="me-2 text-primary" size={20} />
                  {selectedEntry?.name}
                </h2>
                <Button variant="outline-secondary" size="sm" onClick={closePreview} className="d-flex align-items-center">
                  <ArrowLeft size={16} className="me-2"/> Close Preview
                </Button>
              </div>
              
              <div className="w2-card mb-2" style={{ flexShrink: 0, padding: '8px 12px' }}>
                <div style={{ fontSize: '0.75rem', display: 'flex', gap: '24px' }}>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Path</strong><span>{selectedEntry?.path}</span></div>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Size</strong><span>{formatBytes(selectedEntry?.sizeBytes)}</span></div>
                  <div><strong style={{ color: 'var(--cc-muted)', marginRight: '8px' }}>Modified</strong><span>{formatTime(selectedEntry?.modifiedAt)}</span></div>
                </div>
              </div>
              
              <div className="w2-card" style={{ flex: 1, overflowY: 'auto', padding: 0, display: 'flex', flexDirection: 'column' }}>
                {previewLoading ? (
                  <div className="d-flex justify-content-center align-items-center h-100 p-5">
                    <Spinner animation="border" variant="primary" />
                  </div>
                ) : previewError ? (
                  <div className="p-4 text-danger">{previewError}</div>
                ) : (
                  <div className="w2-preview-block" style={{ flex: 1, border: 'none', margin: 0, borderRadius: 0 }}>
                    {preview?.content}
                  </div>
                )}
              </div>
            </div>
          ) : (
            // Empty State / Dashboard Mode
            <div className="w2-section" style={{ height: '100%', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center' }}>
              
              <div style={{ maxWidth: '600px', width: '100%', display: 'flex', flexDirection: 'column', gap: '24px' }}>
                
                <div className="text-center mb-4">
                  <FolderOpen size={48} style={{ color: 'var(--cc-muted)', marginBottom: '16px' }} />
                  <h2 style={{ fontSize: '1.5rem', fontWeight: 600, margin: 0 }}>{activeName || "No workspace selected"}</h2>
                  <p style={{ color: 'var(--cc-muted)', margin: '8px 0 0 0' }}>Select a file from the explorer to preview it.</p>
                </div>

                <div className="w2-section">
                  <h2 className="w2-section-title">Workspace Health</h2>
                  <div className="w2-card w2-health-grid">
                    <div className="w2-health-item is-good"><Check size={16}/> Folder Access</div>
                    <div className={`w2-health-item ${activeIndexed ? 'is-good' : 'is-warn'}`}>
                      {activeIndexed ? <Check size={16}/> : <AlertTriangle size={16}/>} RAG Index
                    </div>
                    <div className={`w2-health-item ${graphStats?.nodes > 0 ? 'is-good' : 'is-warn'}`}>
                      {graphStats?.nodes > 0 ? <Check size={16}/> : <AlertTriangle size={16}/>} Graph DB
                    </div>
                    <div className="w2-health-item is-good"><Check size={16}/> Security</div>
                  </div>
                </div>

                <div className="w2-section" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                  
                  <div className="w2-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h2 className="w2-section-title">Knowledge Operations</h2>
                    
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px', fontSize: '0.875rem' }}>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ color: 'var(--cc-muted)' }}>RAG Indexed</strong>
                        <span>{ragStats?.docs || 0} files</span>
                      </div>
                      <div style={{ display: 'flex', flexDirection: 'column' }}>
                        <strong style={{ color: 'var(--cc-muted)' }}>Graph Built</strong>
                        <span>{graphStats?.nodes || 0} nodes</span>
                      </div>
                    </div>
                    
                    <div className="w2-action-panel-grid">
                      <button className="w2-button primary" onClick={indexCurrentFolder}>Index Workspace</button>
                      <button className="w2-button" onClick={refreshKnowledgeStats}>Refresh Status</button>
                    </div>

                    {knowledgeStatus && <p style={{ fontSize: '0.75rem', margin: '4px 0 0 0', color: 'var(--cc-muted)' }}>{knowledgeStatus}</p>}

                    <form onSubmit={searchKnowledge} style={{ display: 'flex', gap: '8px', marginTop: '8px' }}>
                      <input className="w2-input" value={knowledgeQuery} onChange={e => setKnowledgeQuery(e.target.value)} placeholder="Search index & graph..." />
                      <button className="w2-button" type="submit">Search</button>
                    </form>

                    {knowledgeResults && (
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px', maxHeight: '150px', overflowY: 'auto' }}>
                        {ragHits.length > 0 && (
                          <div>
                            <strong style={{ fontSize: '0.875rem' }}>Local Knowledge Search</strong>
                            {ragHits.slice(0, 2).map((hit, i) => (
                              <div key={i} style={{ fontSize: '0.75rem', padding: '8px', backgroundColor: 'var(--cc-bg)', borderRadius: '4px', marginTop: '4px' }}>
                                <div style={{ fontWeight: 'bold' }}>{hit.path}</div>
                                <div>{hit.text.substring(0, 100)}...</div>
                              </div>
                            ))}
                          </div>
                        )}
                        {graphNodes.length > 0 && (
                          <div>
                            <strong style={{ fontSize: '0.875rem' }}>Graph Search</strong>
                            {graphNodes.slice(0, 2).map(node => (
                              <div key={node.id} style={{ fontSize: '0.75rem', padding: '8px', backgroundColor: 'var(--cc-bg)', borderRadius: '4px', marginTop: '4px' }}>
                                Node: {node.id} ({node.type})
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}
                  </div>

                  <div className="w2-card" style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    <h2 className="w2-section-title">Launch Workspace Task</h2>
                    <div className="w2-action-panel-grid" style={{ gridTemplateColumns: '1fr' }}>
                      <button className="w2-button" onClick={() => launchTask('summarize')}>Summarize Directory</button>
                      <button className="w2-button" onClick={() => launchTask('analyze')}>Analyze Workspace</button>
                      <button className="w2-button" onClick={() => launchTask('search')}>Search Vulnerabilities</button>
                      <button className="w2-button" onClick={() => launchTask('graph')}>Review Dependencies</button>
                      <button className="w2-button" onClick={() => launchTask('docs')}>Generate Documentation</button>
                      <button className="w2-button" onClick={() => launchTask('review')}>Code Review</button>
                    </div>
                  </div>

                </div>

              </div>
            </div>
          )}
        </div>
      </div>
"""

lines = lines[:311] + [new_content + "\n"] + lines[548:]

with open('frontend-src/src/features/workspaces/WorkspacesView.jsx', 'w', encoding='utf-8') as f:
    f.writelines(lines)
