import React, { useEffect, useState, useRef, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'

// Status colors
const STATUS_COLORS = {
  NEW: '#6366f1',
  ENRICHED: '#8b5cf6',
  MESSAGED: '#06b6d4',
  SENT: '#10b981',
  FAILED: '#ef4444'
}

const STATUSES = ['ALL', 'NEW', 'ENRICHED', 'MESSAGED', 'SENT', 'FAILED']

// Styles
const styles = {
  container: {
    minHeight: '100vh',
    background: 'linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%)',
    color: '#e2e8f0',
    fontFamily: "'Inter', -apple-system, BlinkMacSystemFont, sans-serif",
    padding: '2rem',
  },
  header: {
    textAlign: 'center',
    marginBottom: '2rem',
  },
  title: {
    fontSize: '2.5rem',
    fontWeight: '800',
    background: 'linear-gradient(135deg, #818cf8 0%, #c084fc 50%, #f472b6 100%)',
    WebkitBackgroundClip: 'text',
    WebkitTextFillColor: 'transparent',
    marginBottom: '0.5rem',
  },
  subtitle: {
    color: '#94a3b8',
    fontSize: '1rem',
  },
  sseIndicator: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '0.5rem',
    marginTop: '0.5rem',
    padding: '0.25rem 0.75rem',
    borderRadius: '9999px',
    fontSize: '0.75rem',
    fontWeight: '500',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))',
    gap: '1.5rem',
    maxWidth: '1400px',
    margin: '0 auto',
  },
  card: {
    background: 'rgba(30, 41, 59, 0.7)',
    backdropFilter: 'blur(20px)',
    borderRadius: '16px',
    border: '1px solid rgba(148, 163, 184, 0.1)',
    padding: '1.5rem',
  },
  cardTitle: {
    fontSize: '0.875rem',
    fontWeight: '600',
    color: '#94a3b8',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    marginBottom: '1rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  btn: {
    padding: '0.75rem 1.5rem',
    borderRadius: '12px',
    border: 'none',
    fontWeight: '600',
    cursor: 'pointer',
    transition: 'all 0.2s',
    fontSize: '0.875rem',
  },
  btnPrimary: {
    background: 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)',
    color: 'white',
  },
  btnDanger: {
    background: 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)',
    color: 'white',
  },
  btnSecondary: {
    background: 'rgba(148, 163, 184, 0.1)',
    color: '#94a3b8',
    border: '1px solid rgba(148, 163, 184, 0.2)',
  },
  // Modal styles
  modalOverlay: {
    position: 'fixed',
    top: 0,
    left: 0,
    right: 0,
    bottom: 0,
    background: 'rgba(0, 0, 0, 0.8)',
    backdropFilter: 'blur(8px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 1000,
    padding: '2rem',
  },
  modal: {
    background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
    borderRadius: '20px',
    border: '1px solid rgba(148, 163, 184, 0.2)',
    maxWidth: '800px',
    width: '100%',
    maxHeight: '90vh',
    overflow: 'auto',
    boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.5)',
  },
  modalHeader: {
    padding: '1.5rem',
    borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
  },
  modalBody: {
    padding: '1.5rem',
  },
  messageBox: {
    background: 'rgba(15, 23, 42, 0.5)',
    borderRadius: '12px',
    padding: '1rem',
    marginBottom: '1rem',
    border: '1px solid rgba(148, 163, 184, 0.1)',
  },
  messageLabel: {
    fontSize: '0.75rem',
    fontWeight: '600',
    color: '#818cf8',
    textTransform: 'uppercase',
    marginBottom: '0.5rem',
    display: 'flex',
    alignItems: 'center',
    gap: '0.5rem',
  },
  messageText: {
    color: '#e2e8f0',
    fontSize: '0.875rem',
    lineHeight: '1.6',
    whiteSpace: 'pre-wrap',
  },
  select: {
    padding: '0.5rem 0.75rem',
    borderRadius: '8px',
    border: '1px solid rgba(148, 163, 184, 0.2)',
    background: 'rgba(15, 23, 42, 0.5)',
    color: '#e2e8f0',
    fontSize: '0.875rem',
    cursor: 'pointer',
    outline: 'none',
  },
  progressBar: {
    width: '100%',
    height: '8px',
    background: 'rgba(148, 163, 184, 0.2)',
    borderRadius: '4px',
    overflow: 'hidden',
    marginTop: '0.5rem',
  },
}

// Message Modal Component
function MessageModal({ lead, messages, onClose }) {
  if (!lead) return null

  return (
    <div style={styles.modalOverlay} onClick={onClose}>
      <div style={styles.modal} onClick={(e) => e.stopPropagation()}>
        <div style={styles.modalHeader}>
          <div>
            <h2 style={{ margin: 0, fontSize: '1.25rem', color: '#e2e8f0' }}>
              Messages for {lead.name}
            </h2>
            <p style={{ margin: '0.25rem 0 0', color: '#64748b', fontSize: '0.875rem' }}>
              {lead.title} at {lead.company} • {lead.email}
            </p>
          </div>
          <button
            onClick={onClose}
            style={{
              background: 'rgba(239, 68, 68, 0.1)',
              border: '1px solid rgba(239, 68, 68, 0.3)',
              color: '#f87171',
              width: '36px',
              height: '36px',
              borderRadius: '8px',
              cursor: 'pointer',
              fontSize: '1.25rem',
            }}
          >
            ×
          </button>
        </div>

        <div style={styles.modalBody}>
          {messages.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
              No messages generated for this lead yet.
            </div>
          ) : (
            messages.map((msg, idx) => (
              <div key={msg.id || idx}>
                {/* Email A */}
                {msg.email_a && (
                  <div style={styles.messageBox}>
                    <div style={styles.messageLabel}>
                      <span></span> Email Variant A (Pain-Focused)
                    </div>
                    <div style={styles.messageText}>{msg.email_a}</div>
                  </div>
                )}

                {/* Email B */}
                {msg.email_b && (
                  <div style={styles.messageBox}>
                    <div style={{ ...styles.messageLabel, color: '#c084fc' }}>
                      <span></span> Email Variant B (Trigger-Focused)
                    </div>
                    <div style={styles.messageText}>{msg.email_b}</div>
                  </div>
                )}

                {/* DM A */}
                {msg.dm_a && (
                  <div style={styles.messageBox}>
                    <div style={{ ...styles.messageLabel, color: '#06b6d4' }}>
                      <span></span> LinkedIn DM Variant A
                    </div>
                    <div style={styles.messageText}>{msg.dm_a}</div>
                  </div>
                )}

                {/* DM B */}
                {msg.dm_b && (
                  <div style={styles.messageBox}>
                    <div style={{ ...styles.messageLabel, color: '#10b981' }}>
                      <span></span> LinkedIn DM Variant B
                    </div>
                    <div style={styles.messageText}>{msg.dm_b}</div>
                  </div>
                )}

                {/* CTA */}
                {msg.cta && (
                  <div style={{
                    ...styles.messageBox,
                    background: 'rgba(99, 102, 241, 0.1)',
                    border: '1px solid rgba(99, 102, 241, 0.3)',
                  }}>
                    <div style={{ ...styles.messageLabel, color: '#a5b4fc' }}>
                      <span>🎯</span> Call to Action
                    </div>
                    <div style={{ ...styles.messageText, color: '#a5b4fc', fontWeight: '500' }}>
                      {msg.cta}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

// Pipeline Progress Component
function PipelineProgress({ progress, currentStage, metrics }) {
  const stages = ['generate', 'enrich', 'message', 'send']
  const stageLabels = {
    generate: ' Generate Leads',
    enrich: ' Enrich Data',
    message: ' Create Messages',
    send: ' Send Outreach'
  }

  // Calculate overall progress percentage (check both 'complete' and 'completed')
  const completedStages = stages.filter(s =>
    progress[s]?.status === 'complete' || progress[s]?.status === 'completed'
  ).length
  const overallProgress = (completedStages / stages.length) * 100

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        <span></span> Pipeline Progress
        <span style={{
          marginLeft: 'auto',
          fontSize: '0.8rem',
          color: '#818cf8',
          fontWeight: '600',
        }}>
          {Math.round(overallProgress)}%
        </span>
      </div>

      {/* Overall progress bar */}
      <div style={{
        ...styles.progressBar,
        height: '12px',
        marginBottom: '1.5rem',
        background: 'rgba(99, 102, 241, 0.1)',
        borderRadius: '6px',
      }}>
        <div style={{
          height: '100%',
          width: `${overallProgress}%`,
          background: 'linear-gradient(90deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%)',
          borderRadius: '6px',
          transition: 'width 0.5s ease',
          boxShadow: overallProgress > 0 ? '0 0 10px rgba(139, 92, 246, 0.5)' : 'none',
        }} />
      </div>

      {/* Stage steps */}
      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        {stages.map((stage, idx) => {
          const stageProgress = progress[stage] || { status: 'pending', count: 0 }
          const isActive = currentStage === stage
          const isComplete = stageProgress.status === 'complete' || stageProgress.status === 'completed'
          const isRunning = stageProgress.status === 'running' || isActive
          const isFailed = stageProgress.status === 'failed'

          // Determine step number color
          const stepColor = isComplete ? '#10b981' : isRunning ? '#818cf8' : isFailed ? '#ef4444' : '#475569'

          return (
            <div key={stage} style={{
              display: 'flex',
              alignItems: 'center',
              gap: '1rem',
              opacity: isComplete || isRunning ? 1 : 0.5,
            }}>
              {/* Step number circle */}
              <div style={{
                width: '32px',
                height: '32px',
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '0.875rem',
                fontWeight: '700',
                background: isComplete
                  ? 'linear-gradient(135deg, #10b981 0%, #059669 100%)'
                  : isRunning
                    ? 'linear-gradient(135deg, #6366f1 0%, #8b5cf6 100%)'
                    : 'rgba(71, 85, 105, 0.3)',
                color: 'white',
                transition: 'all 0.3s ease',
                animation: isRunning ? 'pulse 2s infinite' : 'none',
                boxShadow: isRunning ? '0 0 15px rgba(99, 102, 241, 0.5)' : 'none',
              }}>
                {isComplete ? '✓' : idx + 1}
              </div>

              {/* Stage info */}
              <div style={{ flex: 1 }}>
                <div style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  marginBottom: '0.25rem',
                }}>
                  <span style={{
                    fontSize: '0.875rem',
                    color: isComplete ? '#10b981' : isRunning ? '#818cf8' : isFailed ? '#ef4444' : '#94a3b8',
                    fontWeight: isRunning ? '600' : '500',
                  }}>
                    {stageLabels[stage]}
                    {isRunning && <span style={{
                      marginLeft: '0.5rem',
                      animation: 'pulse 1s infinite',
                    }}>⏳</span>}
                  </span>
                  <span style={{
                    fontSize: '0.75rem',
                    color: '#94a3b8',
                    fontWeight: '500',
                  }}>
                    {stageProgress.count > 0 && `${stageProgress.count} items`}
                    {stage === 'send' && (metrics?.status_counts?.SENT > 0 || stageProgress.sent > 0) && (
                      <span style={{ color: '#10b981' }}> • {metrics?.status_counts?.SENT || stageProgress.sent || 0} sent</span>
                    )}
                    {stage === 'send' && (metrics?.status_counts?.FAILED > 0 || stageProgress.failed > 0) && (
                      <span style={{ color: '#ef4444' }}> • {metrics?.status_counts?.FAILED || stageProgress.failed || 0} failed</span>
                    )}
                  </span>
                </div>

                {/* Individual progress bar */}
                <div style={{
                  ...styles.progressBar,
                  height: '6px',
                  background: 'rgba(148, 163, 184, 0.1)',
                }}>
                  <div style={{
                    height: '100%',
                    width: isComplete ? '100%' : isRunning ? '60%' : '0%',
                    background: isFailed
                      ? '#ef4444'
                      : isComplete
                        ? '#10b981'
                        : 'linear-gradient(90deg, #6366f1, #8b5cf6)',
                    transition: 'width 0.3s ease',
                    borderRadius: '3px',
                  }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Metrics Cards
function MetricsGrid({ metrics }) {
  const { status_counts = {}, total = 0 } = metrics

  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        <span>📈</span> Live Metrics
      </div>
      <div style={{
        fontSize: '3rem',
        fontWeight: '800',
        background: 'linear-gradient(135deg, #818cf8 0%, #c084fc 100%)',
        WebkitBackgroundClip: 'text',
        WebkitTextFillColor: 'transparent',
        marginBottom: '1rem',
      }}>
        {total}
        <span style={{ fontSize: '1rem', color: '#64748b', marginLeft: '0.5rem' }}>total leads</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
        {Object.entries(status_counts).map(([status, count]) => (
          <div key={status} style={{
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            background: `${STATUS_COLORS[status]}20`,
            border: `1px solid ${STATUS_COLORS[status]}40`,
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
          }}>
            <div style={{
              width: '8px',
              height: '8px',
              borderRadius: '50%',
              background: STATUS_COLORS[status],
            }} />
            <span style={{ fontSize: '0.875rem', color: '#e2e8f0' }}>{status}</span>
            <span style={{ fontWeight: '700', color: STATUS_COLORS[status] }}>{count}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// Control Panel
function ControlPanel({ running, onStart, onStop, onReset, config, setConfig, lastMessage, sseConnected }) {
  return (
    <div style={styles.card}>
      <div style={styles.cardTitle}>
        <span></span> Controls
        {sseConnected !== undefined && (
          <span style={{
            marginLeft: 'auto',
            fontSize: '0.7rem',
            padding: '0.2rem 0.5rem',
            borderRadius: '9999px',
            background: sseConnected ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)',
            color: sseConnected ? '#34d399' : '#f87171',
          }}>
            {sseConnected ? '🟢 Live' : '🔴 Polling'}
          </span>
        )}
      </div>

      {lastMessage && (
        <div style={{
          padding: '0.75rem',
          marginBottom: '1rem',
          borderRadius: '8px',
          background: lastMessage.includes('error') || lastMessage.includes('❌')
            ? 'rgba(239, 68, 68, 0.1)'
            : 'rgba(16, 185, 129, 0.1)',
          color: lastMessage.includes('error') || lastMessage.includes('❌')
            ? '#f87171'
            : '#34d399',
          fontSize: '0.875rem',
        }}>
          {lastMessage}
        </div>
      )}

      <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            background: config.dryRun ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
            border: `1px solid ${config.dryRun ? '#10b98140' : '#ef444440'}`,
            cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={config.dryRun}
              onChange={(e) => setConfig({ ...config, dryRun: e.target.checked })}
              disabled={running}
              style={{ accentColor: '#10b981' }}
            />
            <span style={{ color: config.dryRun ? '#10b981' : '#ef4444' }}>
              {config.dryRun ? 'Dry Run' : ' Live Mode'}
            </span>
          </label>

          <label style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            background: config.aiMode ? 'rgba(139, 92, 246, 0.1)' : 'rgba(148, 163, 184, 0.1)',
            border: config.aiMode ? '1px solid rgba(139, 92, 246, 0.3)' : 'none',
            cursor: 'pointer',
          }}>
            <input
              type="checkbox"
              checked={config.aiMode}
              onChange={(e) => setConfig({ ...config, aiMode: e.target.checked })}
              disabled={running}
              style={{ accentColor: '#8b5cf6' }}
            />
            <span style={{ color: config.aiMode ? '#a78bfa' : '#94a3b8' }}> AI Mode</span>
          </label>

          <div style={{
            display: 'flex',
            alignItems: 'center',
            gap: '0.5rem',
            padding: '0.5rem 1rem',
            borderRadius: '8px',
            background: 'rgba(148, 163, 184, 0.1)',
          }}>
            <span></span>
            <input
              type="number"
              value={config.count}
              onChange={(e) => {
                const val = e.target.value
                // Allow empty or valid numbers while typing
                if (val === '' || val === '0') {
                  setConfig({ ...config, count: '' })
                } else {
                  const num = parseInt(val)
                  if (!isNaN(num)) {
                    setConfig({ ...config, count: num })
                  }
                }
              }}
              onBlur={(e) => {
                // Apply default on blur if empty
                const num = parseInt(e.target.value)
                if (isNaN(num) || num < 1) {
                  setConfig({ ...config, count: 10 })
                } else if (num > 500) {
                  setConfig({ ...config, count: 500 })
                }
              }}
              disabled={running}
              min={1}
              max={500}
              style={{
                width: '70px',
                padding: '0.25rem 0.5rem',
                borderRadius: '4px',
                border: '1px solid rgba(148, 163, 184, 0.2)',
                background: 'rgba(15, 23, 42, 0.5)',
                color: '#e2e8f0',
                fontSize: '0.875rem',
              }}
            />
            <span style={{ color: '#64748b', fontSize: '0.75rem' }}>leads</span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: '0.75rem' }}>
          {!running ? (
            <button
              onClick={onStart}
              style={{ ...styles.btn, ...styles.btnPrimary, flex: 1 }}
            >
              Start Pipeline
            </button>
          ) : (
            <button
              onClick={onStop}
              style={{ ...styles.btn, ...styles.btnDanger, flex: 1 }}
            >
              ⏹️ Stop Pipeline
            </button>
          )}
          <button
            onClick={onReset}
            disabled={running}
            style={{ ...styles.btn, ...styles.btnSecondary, opacity: running ? 0.5 : 1 }}
          >
            Reset
          </button>
        </div>
      </div>
    </div>
  )
}

// Event Log
function EventLog({ logs }) {
  return (
    <div style={{ ...styles.card, gridColumn: '1 / -1' }}>
      <div style={styles.cardTitle}>
        <span>📋</span> Recent Logs
      </div>
      <div style={{
        maxHeight: '200px',
        overflowY: 'auto',
        background: 'rgba(15, 23, 42, 0.5)',
        borderRadius: '8px',
        padding: '0.75rem',
      }}>
        {logs.length === 0 ? (
          <div style={{ color: '#64748b', textAlign: 'center', padding: '1rem' }}>
            No logs yet. Run the pipeline to see activity.
          </div>
        ) : (
          logs.map((log, idx) => (
            <div key={idx} style={{
              padding: '0.5rem',
              borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
              display: 'flex',
              gap: '0.75rem',
              alignItems: 'flex-start',
              fontSize: '0.813rem',
            }}>
              <span style={{ color: '#64748b', flexShrink: 0 }}>
                {log.ts ? new Date(log.ts).toLocaleTimeString() : ''}
              </span>
              <span style={{
                padding: '0.125rem 0.5rem',
                borderRadius: '4px',
                background: log.level === 'ERROR' ? '#ef444420' : '#6366f120',
                color: log.level === 'ERROR' ? '#f87171' : '#818cf8',
                fontSize: '0.75rem',
                fontWeight: '600',
                flexShrink: 0,
              }}>
                {log.stage}
              </span>
              <span style={{ color: '#cbd5e1' }}>
                {log.message}
              </span>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

// Lead Table with clickable rows and status filter
function LeadTable({ leads, onLeadClick, statusFilter, setStatusFilter }) {
  const filteredLeads = statusFilter === 'ALL'
    ? leads
    : leads.filter(lead => lead.status === statusFilter)

  return (
    <div style={{ ...styles.card, gridColumn: '1 / -1' }}>
      <div style={styles.cardTitle}>
        <span></span> Leads ({filteredLeads.length})

        {/* Status Filter */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span style={{ fontSize: '0.7rem', color: '#64748b', fontWeight: 'normal' }}>
            Filter:
          </span>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            style={styles.select}
          >
            {STATUSES.map(status => (
              <option key={status} value={status}>
                {status === 'ALL' ? 'All Statuses' : status}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div style={{ overflowX: 'auto' }}>
        <table style={{
          width: '100%',
          borderCollapse: 'collapse',
          fontSize: '0.875rem',
        }}>
          <thead>
            <tr style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.2)' }}>
              {['ID', 'Name', 'Company', 'Title', 'Industry', 'Status', 'Confidence', ''].map(h => (
                <th key={h} style={{
                  padding: '0.75rem',
                  textAlign: 'left',
                  color: '#94a3b8',
                  fontWeight: '600',
                  fontSize: '0.75rem',
                  textTransform: 'uppercase',
                  letterSpacing: '0.05em',
                }}>{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filteredLeads.slice(0, 20).map((lead) => (
              <tr
                key={lead.id}
                onClick={() => onLeadClick(lead)}
                style={{
                  borderBottom: '1px solid rgba(148, 163, 184, 0.1)',
                  cursor: 'pointer',
                  transition: 'background 0.2s',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'rgba(99, 102, 241, 0.1)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <td style={{ padding: '0.75rem', color: '#64748b' }}>#{lead.id}</td>
                <td style={{ padding: '0.75rem', fontWeight: '500' }}>{lead.name}</td>
                <td style={{ padding: '0.75rem', color: '#94a3b8' }}>{lead.company}</td>
                <td style={{ padding: '0.75rem', color: '#94a3b8' }}>{lead.title}</td>
                <td style={{ padding: '0.75rem' }}>
                  <span style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: 'rgba(99, 102, 241, 0.1)',
                    color: '#818cf8',
                    fontSize: '0.75rem',
                  }}>{lead.industry}</span>
                </td>
                <td style={{ padding: '0.75rem' }}>
                  <span style={{
                    padding: '0.25rem 0.5rem',
                    borderRadius: '4px',
                    background: `${STATUS_COLORS[lead.status]}20`,
                    color: STATUS_COLORS[lead.status],
                    fontSize: '0.75rem',
                    fontWeight: '600',
                  }}>{lead.status}</span>
                </td>
                <td style={{ padding: '0.75rem' }}>
                  {lead.confidence && (
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{
                        width: '50px',
                        height: '6px',
                        background: 'rgba(148, 163, 184, 0.2)',
                        borderRadius: '3px',
                        overflow: 'hidden',
                      }}>
                        <div style={{
                          width: `${lead.confidence}%`,
                          height: '100%',
                          background: lead.confidence >= 80 ? '#10b981' : lead.confidence >= 60 ? '#f59e0b' : '#ef4444',
                          borderRadius: '3px',
                        }} />
                      </div>
                      <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                        {lead.confidence?.toFixed(0)}%
                      </span>
                    </div>
                  )}
                </td>
                <td style={{ padding: '0.75rem' }}>
                  <span style={{ color: '#818cf8', fontSize: '1rem' }}></span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {filteredLeads.length === 0 && (
          <div style={{ textAlign: 'center', padding: '2rem', color: '#64748b' }}>
            {leads.length === 0
              ? 'No leads yet. Run the pipeline to generate leads.'
              : `No leads with status "${statusFilter}".`
            }
          </div>
        )}
        {filteredLeads.length > 20 && (
          <div style={{ textAlign: 'center', padding: '1rem', color: '#64748b', fontSize: '0.875rem' }}>
            Showing 20 of {filteredLeads.length} leads
          </div>
        )}
      </div>
    </div>
  )
}

// Export Buttons
function ExportButtons() {
  const exportCSV = async (type) => {
    window.open(`${API_BASE}/export/${type}`, '_blank')
  }

  return (
    <div style={{ ...styles.card }}>
      <div style={styles.cardTitle}>
        <span>📤</span> Export Data
      </div>
      <div style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
        <button
          onClick={() => exportCSV('leads')}
          style={{ ...styles.btn, ...styles.btnSecondary }}
        >
          📑 Export Leads CSV
        </button>
        <button
          onClick={() => exportCSV('messages')}
          style={{ ...styles.btn, ...styles.btnSecondary }}
        >
          Export Messages CSV
        </button>
      </div>
    </div>
  )
}

// Main App
function App() {
  const [metrics, setMetrics] = useState({ total: 0, status_counts: {} })
  const [leads, setLeads] = useState([])
  const [logs, setLogs] = useState([])
  const [running, setRunning] = useState(false)
  const [lastMessage, setLastMessage] = useState('')
  const [config, setConfig] = useState({
    dryRun: true,
    aiMode: false,
    count: 50,
  })
  const [statusFilter, setStatusFilter] = useState('ALL')

  // SSE state
  const [sseConnected, setSseConnected] = useState(false)
  const [currentStage, setCurrentStage] = useState(null)
  const [progress, setProgress] = useState({
    generate: { status: 'pending', count: 0 },
    enrich: { status: 'pending', count: 0 },
    message: { status: 'pending', count: 0 },
    send: { status: 'pending', count: 0, sent: 0, failed: 0 },
  })
  const eventSourceRef = useRef(null)

  // Modal state
  const [selectedLead, setSelectedLead] = useState(null)
  const [leadMessages, setLeadMessages] = useState([])
  const [modalOpen, setModalOpen] = useState(false)

  const fetchData = useCallback(async () => {
    try {
      const [metricsRes, leadsRes, logsRes] = await Promise.all([
        fetch(`${API_BASE}/metrics`),
        fetch(`${API_BASE}/leads?limit=50`),
        fetch(`${API_BASE}/logs?limit=50`)
      ])

      if (metricsRes.ok) {
        const metricsData = await metricsRes.json()
        setMetrics(metricsData)
      }
      if (leadsRes.ok) {
        const leadsData = await leadsRes.json()
        setLeads(leadsData.items || [])
      }
      if (logsRes.ok) {
        const logsData = await logsRes.json()
        setLogs(logsData.items || [])
      }
    } catch (err) {
      console.error('Fetch failed:', err)
    }
  }, [])

  // Fetch pipeline status on mount to restore state after refresh
  const fetchPipelineStatus = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/pipeline/status`)
      if (response.ok) {
        const data = await response.json()
        if (data.pipeline_state) {
          setRunning(data.pipeline_state.running)
          setCurrentStage(data.pipeline_state.current_stage)
          if (data.pipeline_state.progress) {
            setProgress(data.pipeline_state.progress)
          }
        }
        if (data.metrics) {
          setMetrics(data.metrics)
        }
      }
    } catch (err) {
      console.error('Failed to fetch pipeline status:', err)
    }
  }, [])

  // SSE Connection
  useEffect(() => {
    const connectSSE = () => {
      try {
        const eventSource = new EventSource(`${API_BASE}/events`)
        eventSourceRef.current = eventSource

        eventSource.onopen = () => {
          console.log('SSE connected')
          setSseConnected(true)
        }

        // Handle named events from SSE
        eventSource.addEventListener('init', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE init:', data)
            if (data.pipeline_state) {
              setRunning(data.pipeline_state.running)
              setCurrentStage(data.pipeline_state.current_stage)
              if (data.pipeline_state.progress) {
                setProgress(data.pipeline_state.progress)
              }
            }
          } catch (e) {
            console.error('SSE init parse error:', e)
          }
        })

        eventSource.addEventListener('stage_started', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE stage_started:', data)
            setCurrentStage(data.stage)
            setProgress(prev => ({
              ...prev,
              [data.stage]: { ...prev[data.stage], status: 'running' }
            }))
          } catch (e) {
            console.error('SSE stage_started parse error:', e)
          }
        })

        eventSource.addEventListener('stage_completed', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE stage_completed:', data)
            setProgress(prev => ({
              ...prev,
              [data.stage]: {
                status: 'complete',
                count: data.count || 0,
                sent: data.sent,
                failed: data.failed
              }
            }))
            fetchData() // Refresh data after stage complete
          } catch (e) {
            console.error('SSE stage_completed parse error:', e)
          }
        })

        eventSource.addEventListener('pipeline_completed', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE pipeline_completed:', data)
            setRunning(false)
            setCurrentStage(null)
            setLastMessage(`✅ Pipeline completed! ${data.sent || 0} sent, ${data.failed || 0} failed`)
            fetchData()
          } catch (e) {
            console.error('SSE pipeline_completed parse error:', e)
          }
        })

        eventSource.addEventListener('metrics_update', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE metrics_update:', data)
            setMetrics({
              total: data.total,
              status_counts: data.status_counts
            })
          } catch (e) {
            console.error('SSE metrics_update parse error:', e)
          }
        })

        eventSource.addEventListener('pipeline_error', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE pipeline_error:', data)
            setRunning(false)
            setCurrentStage(null)
            setLastMessage(`❌ Pipeline error: ${data.error}`)
          } catch (e) {
            console.error('SSE pipeline_error parse error:', e)
          }
        })

        eventSource.addEventListener('pipeline_stopped', (event) => {
          try {
            const data = JSON.parse(event.data)
            console.log('SSE pipeline_stopped:', data)
            setRunning(false)
            setCurrentStage(null)
            setLastMessage(`⏹️ Pipeline stopped: ${data.message}`)
          } catch (e) {
            console.error('SSE pipeline_stopped parse error:', e)
          }
        })

        eventSource.onerror = () => {
          console.log('SSE error, reconnecting...')
          setSseConnected(false)
          eventSource.close()
          // Retry connection after 3 seconds
          setTimeout(connectSSE, 3000)
        }
      } catch (err) {
        console.error('SSE connection failed:', err)
        setSseConnected(false)
      }
    }

    // Fetch current state first, then connect SSE
    fetchPipelineStatus()
    connectSSE()

    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [fetchData, fetchPipelineStatus])

  // Fallback polling when SSE is not connected
  useEffect(() => {
    fetchData()
    const interval = setInterval(() => {
      if (!sseConnected) {
        fetchData()
      }
    }, 2000)
    return () => clearInterval(interval)
  }, [sseConnected, fetchData])

  // Check if pipeline finished
  useEffect(() => {
    if (running && metrics.total > 0) {
      const sent = metrics.status_counts?.SENT || 0
      const failed = metrics.status_counts?.FAILED || 0
      if (sent + failed >= metrics.total) {
        setRunning(false)
        setCurrentStage(null)
        setLastMessage(`✅ Pipeline completed! ${sent} sent, ${failed} failed`)
      }
    }
  }, [metrics, running])

  const handleLeadClick = async (lead) => {
    setSelectedLead(lead)
    setLeadMessages([])
    setModalOpen(true)

    try {
      const response = await fetch(`${API_BASE}/leads/${lead.id}/messages`)
      if (response.ok) {
        const data = await response.json()
        setLeadMessages(data.messages || [])
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err)
    }
  }

  const startPipeline = async () => {
    setLastMessage('Starting pipeline...')
    setRunning(true)
    setProgress({
      generate: { status: 'pending', count: 0 },
      enrich: { status: 'pending', count: 0 },
      message: { status: 'pending', count: 0 },
      send: { status: 'pending', count: 0, sent: 0, failed: 0 },
    })

    try {
      let response = await fetch(`${API_BASE}/pipeline/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          dry_run: config.dryRun,
          ai_mode: config.aiMode,
          count: config.count,
        })
      })

      if (!response.ok && response.status === 404) {
        response = await fetch(`${API_BASE}/run`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            dry_run: config.dryRun,
            ai_mode: config.aiMode,
            count: config.count,
          })
        })
      }

      if (response.ok) {
        setLastMessage(`Pipeline started! Processing ${config.count} leads...`)
        setTimeout(fetchData, 1000)
      } else {
        const error = await response.text()
        setLastMessage(`❌ Error: ${error}`)
        setRunning(false)
      }
    } catch (err) {
      setLastMessage(`❌ Error: ${err.message}`)
      setRunning(false)
    }
  }

  const stopPipeline = async () => {
    try {
      await fetch(`${API_BASE}/pipeline/stop`, { method: 'POST' })
      setLastMessage('⏹️ Stop signal sent')
    } catch (err) {
      setLastMessage(`❌ Error: ${err.message}`)
    }
    setRunning(false)
    setCurrentStage(null)
  }

  const resetDatabase = async () => {
    if (confirm('Are you sure you want to clear all data?')) {
      try {
        await fetch(`${API_BASE}/reset`, { method: 'POST' })
        setMetrics({ total: 0, status_counts: {} })
        setLeads([])
        setLogs([])
        setProgress({
          generate: { status: 'pending', count: 0 },
          enrich: { status: 'pending', count: 0 },
          message: { status: 'pending', count: 0 },
          send: { status: 'pending', count: 0, sent: 0, failed: 0 },
        })
        setLastMessage('Database cleared')
      } catch (err) {
        setLastMessage(`❌ Error: ${err.message}`)
      }
    }
  }

  return (
    <div style={styles.container}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(30, 41, 59, 0.5); border-radius: 3px; }
        ::-webkit-scrollbar-thumb { background: #475569; border-radius: 3px; }
        select option { background: #1e293b; color: #e2e8f0; }
      `}</style>

      <header style={styles.header}>
        <h1 style={styles.title}>Outreach Agent</h1>
        <p style={styles.subtitle}>MCP-Powered Lead Generation & Outreach Pipeline</p>
        <div style={{
          ...styles.sseIndicator,
          background: sseConnected ? 'rgba(16, 185, 129, 0.1)' : 'rgba(239, 68, 68, 0.1)',
          border: `1px solid ${sseConnected ? '#10b98140' : '#ef444440'}`,
          color: sseConnected ? '#34d399' : '#f87171',
        }}>
          <span style={{
            width: '8px',
            height: '8px',
            borderRadius: '50%',
            background: sseConnected ? '#10b981' : '#ef4444',
            animation: sseConnected ? 'pulse 2s infinite' : 'none',
          }} />
          {sseConnected ? 'Real-time updates enabled' : 'Polling mode (reconnecting...)'}
        </div>
      </header>

      <div style={styles.grid}>

        <ControlPanel
          running={running}
          onStart={startPipeline}
          onStop={stopPipeline}
          onReset={resetDatabase}
          config={config}
          setConfig={setConfig}
          lastMessage={lastMessage}
          sseConnected={sseConnected}
        />

        <PipelineProgress progress={progress} currentStage={currentStage} metrics={metrics} />

        <ExportButtons />

        <EventLog logs={logs} />

        <LeadTable
          leads={leads}
          onLeadClick={handleLeadClick}
          statusFilter={statusFilter}
          setStatusFilter={setStatusFilter}
        />
      </div>

      {/* Message Modal */}
      {modalOpen && (
        <MessageModal
          lead={selectedLead}
          messages={leadMessages}
          onClose={() => setModalOpen(false)}
        />
      )}

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.5; }
        }
      `}</style>
    </div>
  )
}

export default App
