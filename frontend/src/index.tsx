import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { KeycloakProvider } from './auth/KeycloakProvider';
import { VerticalConfigProvider } from './config/VerticalConfigProvider';

const root = ReactDOM.createRoot(
  document.getElementById('root') as HTMLElement
);
root.render(
  <React.StrictMode>
    <KeycloakProvider>
      <VerticalConfigProvider>
        <App />
      </VerticalConfigProvider>
    </KeycloakProvider>
  </React.StrictMode>
);
