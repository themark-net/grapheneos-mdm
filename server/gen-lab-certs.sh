#!/usr/bin/env bash
# Generate a throwaway lab CA + server + client PKCS#12 for closed-loop mTLS tests.
# Not for production. Aligns with step-ca lab pattern: one CA, device client certs.
set -euo pipefail
OUT="${1:-lab-certs}"
mkdir -p "$OUT"
cd "$OUT"

# CA with CA:TRUE + keyUsage (required by OpenSSL 3 / Python 3.13 verify)
cat > ca.cnf << 'CNF'
[req]
distinguished_name = dn
x509_extensions = v3_ca
prompt = no
[dn]
CN = grapheneos-mdm-lab-ca
[v3_ca]
basicConstraints = critical,CA:TRUE
keyUsage = critical, keyCertSign, cRLSign
subjectKeyIdentifier = hash
CNF

openssl req -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
  -keyout ca-key.pem -out ca.pem -config ca.cnf 2>/dev/null

# Server
cat > server.cnf << 'CNF'
[req]
distinguished_name = dn
prompt = no
[dn]
CN = localhost
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = DNS:localhost,IP:127.0.0.1
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
CNF

openssl req -newkey rsa:2048 -nodes -keyout server-key.pem -out server.csr -config server.cnf 2>/dev/null
openssl x509 -req -in server.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out server.pem -days 825 -sha256 -extfile server.cnf -extensions v3_req 2>/dev/null

# Client (device)
cat > client.cnf << 'CNF'
[req]
distinguished_name = dn
prompt = no
[dn]
CN = lab-device-01
[v3_req]
basicConstraints = CA:FALSE
keyUsage = critical, digitalSignature
extendedKeyUsage = clientAuth
subjectKeyIdentifier = hash
authorityKeyIdentifier = keyid,issuer
CNF

openssl req -newkey rsa:2048 -nodes -keyout client-key.pem -out client.csr -config client.cnf 2>/dev/null
openssl x509 -req -in client.csr -CA ca.pem -CAkey ca-key.pem -CAcreateserial \
  -out client.pem -days 825 -sha256 -extfile client.cnf -extensions v3_req 2>/dev/null

openssl pkcs12 -export -out client.p12 -inkey client-key.pem -in client.pem \
  -certfile ca.pem -passout pass: 2>/dev/null

rm -f server.csr client.csr ca.srl ca.cnf server.cnf client.cnf
chmod 600 ./*-key.pem client.p12 2>/dev/null || true
echo "Wrote lab certs under $OUT (ca.pem, server.pem, server-key.pem, client.pem, client-key.pem, client.p12)"
