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
  }

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div style={{
        minHeight: '100vh', display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center',
        background: '#111', color: '#f5f5f5', fontFamily: 'Inter, sans-serif', padding: 32,
      }}>
        <div style={{ fontSize: 32, marginBottom: 16 }}>Something went wrong</div>
        <p style={{ color: '#a0a0a0', marginBottom: 24, textAlign: 'center', maxWidth: 480 }}>
          An unexpected error occurred. Please refresh the page. If the problem persists, contact support.
        </p>
        <button
          onClick={() => window.location.reload()}
          style={{
            background: '#4f8ff7', color: '#fff', border: 'none', borderRadius: 8,
            padding: '10px 24px', fontSize: 14, fontWeight: 600, cursor: 'pointer',
          }}
        >
          Refresh page
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
