import React from 'react';
import { AlertCircle } from 'lucide-react';

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error, info) {
    console.error('[ErrorBoundary]', error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="error-banner" style={{ margin: '1rem 0', padding: '1rem' }}>
          <AlertCircle size={20} />
          <div>
            <strong>Error en: {this.props.name || 'sección'}</strong>
            <p style={{ fontSize: '0.8rem', marginTop: '0.25rem' }}>{this.state.error.message}</p>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
