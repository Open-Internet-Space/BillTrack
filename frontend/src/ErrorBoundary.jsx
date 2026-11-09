import React from 'react';

export default class ErrorBoundary extends React.Component {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error, info) {
    console.error('Application render failed. Reload and check saved records before retrying.');
  }

  render() {
    if (this.state.failed) {
      return (
        <main role="alert" style={{ minHeight: '100vh', display: 'grid', placeContent: 'center', gap: 12, background: '#0d1117', color: '#e6edf3', fontFamily: 'sans-serif', textAlign: 'center' }}>
          <h1 style={{ fontSize: 20 }}>This screen ran into a problem.</h1>
          <p>Reloading discards unsaved input. Check saved records before repeating a save, then reload the page to continue.</p>
          <button onClick={() => window.location.reload()} style={{ justifySelf: 'center', padding: '8px 16px', cursor: 'pointer' }}>Reload page</button>
        </main>
      );
    }
    return this.props.children;
  }
}
