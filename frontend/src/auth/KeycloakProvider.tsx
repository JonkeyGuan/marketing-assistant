import React, { createContext, useContext } from 'react';

interface AuthContextType {
  authenticated: boolean;
  user: { username: string; name: string; email: string; roles: string[] } | null;
  token: string | null;
  keycloak: null;
  login: () => void;
  logout: () => void;
  loading: boolean;
  enabled: boolean;
}

const AuthContext = createContext<AuthContextType>({
  authenticated: true,
  user: { username: 'demo', name: 'Demo User', email: 'demo@example.com', roles: ['platinum-access'] },
  token: null,
  keycloak: null,
  login: () => {},
  logout: () => {},
  loading: false,
  enabled: false,
});

export const useAuth = () => useContext(AuthContext);

export const KeycloakProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  return (
    <AuthContext.Provider
      value={{
        authenticated: true,
        user: { username: 'demo', name: 'Demo User', email: 'demo@example.com', roles: ['platinum-access'] },
        token: null,
        keycloak: null,
        login: () => {},
        logout: () => {},
        loading: false,
        enabled: false,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};
