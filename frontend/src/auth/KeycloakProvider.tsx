import React, { createContext, useContext, useEffect, useState, useCallback, useRef } from 'react';
import Keycloak from 'keycloak-js';
import { setTokenGetter } from './authFetch';

interface AuthUser {
  username: string;
  name: string;
  email: string;
  roles: string[];
  token: string;
}

interface AuthContextType {
  authenticated: boolean;
  user: AuthUser | null;
  token: string | null;
  keycloak: Keycloak | null;
  login: () => void;
  logout: () => void;
  loading: boolean;
  enabled: boolean;
}

const AuthContext = createContext<AuthContextType>({
  authenticated: false,
  user: null,
  token: null,
  keycloak: null,
  login: () => {},
  logout: () => {},
  loading: true,
  enabled: false,
});

export const useAuth = () => useContext(AuthContext);

const KEYCLOAK_URL = (window as any).__KEYCLOAK_URL__
  || process.env.REACT_APP_KEYCLOAK_URL
  || '';
const KEYCLOAK_REALM = (window as any).__KEYCLOAK_REALM__
  || process.env.REACT_APP_KEYCLOAK_REALM
  || 'kagenti';
const KEYCLOAK_CLIENT_ID = (window as any).__KEYCLOAK_CLIENT_ID__
  || process.env.REACT_APP_KEYCLOAK_CLIENT_ID
  || 'marketing-ui';

function parseUser(kc: Keycloak): AuthUser {
  const parsed = kc.tokenParsed as any;
  return {
    username: parsed?.preferred_username || 'unknown',
    name: parsed?.name || parsed?.preferred_username || 'User',
    email: parsed?.email || '',
    roles: parsed?.realm_access?.roles || [],
    token: kc.token || '',
  };
}

export const KeycloakProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [authenticated, setAuthenticated] = useState(false);
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);
  const kcRef = useRef<Keycloak | null>(null);
  const initCalled = useRef(false);

  const enabled = Boolean(KEYCLOAK_URL);

  useEffect(() => {
    if (!enabled || initCalled.current) {
      setLoading(false);
      return;
    }
    initCalled.current = true;

    const kc = new Keycloak({
      url: KEYCLOAK_URL,
      realm: KEYCLOAK_REALM,
      clientId: KEYCLOAK_CLIENT_ID,
    });
    kcRef.current = kc;

    kc.init({
      onLoad: 'login-required',
      pkceMethod: 'S256',
      checkLoginIframe: false,
    })
      .then((auth) => {
        setAuthenticated(auth);
        if (auth) {
          setUser(parseUser(kc));
        }
        setLoading(false);
      })
      .catch((err) => {
        console.error('[Auth] Keycloak init failed:', err);
        setLoading(false);
      });

    setTokenGetter(() => kc.token || null);

    kc.onTokenExpired = () => {
      kc.updateToken(30).then((refreshed) => {
        if (refreshed && kc.token) {
          setUser(parseUser(kc));
        }
      }).catch(() => {
        setAuthenticated(false);
        setUser(null);
      });
    };
  }, [enabled]);

  const login = useCallback(() => {
    kcRef.current?.login();
  }, []);

  const logout = useCallback(() => {
    setAuthenticated(false);
    setUser(null);
    kcRef.current?.logout({ redirectUri: window.location.origin + '/?logout=1' });
  }, []);

  return (
    <AuthContext.Provider
      value={{
        authenticated,
        user,
        token: user?.token || null,
        keycloak: kcRef.current,
        login,
        logout,
        loading,
        enabled,
      }}
    >
      {enabled && (loading || !authenticated) ? (
        <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100vh',background:'#0f172a',color:'#fff',fontFamily:'Manrope,sans-serif'}}>
          <div style={{textAlign:'center'}}>
            <div style={{fontSize:'24px',fontWeight:700,marginBottom:'8px'}}>Campaign Manager</div>
            <div style={{fontSize:'14px',opacity:0.6}}>Redirecting to sign in...</div>
          </div>
        </div>
      ) : children}
    </AuthContext.Provider>
  );
};
