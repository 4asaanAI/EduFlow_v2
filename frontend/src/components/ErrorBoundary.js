import React from 'react';

export default class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info.componentStack);
    if (this.props.onError) this.props.onError(error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    const name = this.props.name || 'this panel';
    return (
      <div style={{
        minHeight: 200,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        justifyContent: 'center',
        background: 'var(--bg-card, #1e1e1e)',
        color: 'var(--text-primary, #f5f5f5)',
        border: '1px solid var(--border, #2e2e2e)',
        borderRadius: 12,
        fontFamily: 'Inter, sans-serif',
        padding: 24,
        margin: 16,
      }}>
        <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 8 }}>Something went wrong in {name}</div>
        <p style={{ color: 'var(--text-secondary, #a0a0a0)', marginBottom: 18, maxWidth: 520 }}>
          Other tools are still available. Reload this panel or switch to another tool.
        </p>
        <button
          onClick={this.reset}
          style={{
            background: '#4f8ff7', color: '#fff', border: 'none', borderRadius: 8,
            padding: '10px 24px', fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}
        >
          Reload this panel
        </button>
        {process.env.NODE_ENV === 'development' && this.state.error && (
          <pre style={{ marginTop: 24, color: '#f87171', fontSize: 11, maxWidth: 640, overflow: 'auto' }}>
            {this.state.error.toString()}
          </pre>
        )}
      </div>
    );
  }
}
