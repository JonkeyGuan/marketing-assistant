#!/bin/sh
cat > /usr/share/nginx/html/keycloak-config.js <<EOF
window.__KEYCLOAK_URL__ = "${KEYCLOAK_URL:-}";
window.__KEYCLOAK_REALM__ = "${KEYCLOAK_REALM:-kagenti}";
window.__KEYCLOAK_CLIENT_ID__ = "${KEYCLOAK_CLIENT_ID:-marketing-ui}";
EOF

exec nginx -g 'daemon off;'
