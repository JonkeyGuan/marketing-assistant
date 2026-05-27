declare module 'keycloak-js' {
  interface KeycloakConfig {
    url: string;
    realm: string;
    clientId: string;
  }

  interface KeycloakInitOptions {
    onLoad?: 'check-sso' | 'login-required';
    pkceMethod?: string;
    silentCheckSsoRedirectUri?: string;
    checkLoginIframe?: boolean;
  }

  interface KeycloakTokenParsed {
    preferred_username?: string;
    name?: string;
    email?: string;
    realm_access?: { roles: string[] };
    [key: string]: any;
  }

  class Keycloak {
    token?: string;
    tokenParsed?: KeycloakTokenParsed;
    authenticated?: boolean;
    onTokenExpired?: () => void;

    constructor(config: KeycloakConfig);
    init(options: KeycloakInitOptions): Promise<boolean>;
    login(options?: { redirectUri?: string }): Promise<void>;
    logout(options?: { redirectUri?: string }): Promise<void>;
    updateToken(minValidity: number): Promise<boolean>;
  }

  export default Keycloak;
}
