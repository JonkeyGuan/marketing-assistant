let _getToken: (() => string | null) | null = null;

export function setTokenGetter(getter: () => string | null) {
  _getToken = getter;
}

export async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  const token = _getToken?.();
  if (token) {
    const headers = new Headers(init?.headers);
    if (!headers.has('Authorization')) {
      headers.set('Authorization', `Bearer ${token}`);
    }
    return fetch(input, { ...init, headers });
  }
  return fetch(input, init);
}
