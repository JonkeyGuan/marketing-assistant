import React, { useState } from 'react';
import { useAuth } from '../auth/KeycloakProvider';

export default function Token() {
  const { token, user, enabled } = useAuth();
  const [copied, setCopied] = useState(false);

  if (!enabled) return <div style={styles.container}><p>Keycloak not enabled</p></div>;
  if (!token) return <div style={styles.container}><p>Not authenticated</p></div>;

  const handleCopy = () => {
    navigator.clipboard.writeText(token);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div style={styles.container}>
      <h2 style={styles.title}>JWT Token</h2>
      <p style={styles.user}>{user?.username} ({user?.roles?.join(', ')})</p>
      <div style={styles.tokenBox}>
        <code style={styles.token}>{token}</code>
      </div>
      <button onClick={handleCopy} style={styles.button}>
        {copied ? 'Copied!' : 'Copy Token'}
      </button>
      <p style={styles.hint}>Paste into MCP Inspector → Authentication → Bearer Token</p>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: { maxWidth: 800, margin: '40px auto', padding: '0 20px', fontFamily: 'monospace' },
  title: { fontSize: 20, marginBottom: 8 },
  user: { color: '#666', marginBottom: 16 },
  tokenBox: { background: '#1e1e1e', borderRadius: 8, padding: 16, overflowX: 'auto', marginBottom: 12 },
  token: { color: '#4ec9b0', fontSize: 12, wordBreak: 'break-all', whiteSpace: 'pre-wrap' },
  button: { background: '#0f172a', color: '#fff', border: 'none', borderRadius: 6, padding: '10px 24px', cursor: 'pointer', fontSize: 14 },
  hint: { color: '#999', fontSize: 12, marginTop: 12 },
};
