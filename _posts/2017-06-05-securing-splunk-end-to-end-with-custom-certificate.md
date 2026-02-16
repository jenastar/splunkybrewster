---
layout: post
title: Securing Splunk End-to-End with Custom Certificates
date: '2017-06-05T09:00:00-07:00'
tags:
- splunk
- certificates
- security
- deployment
- forwarders
permalink: /2017/06/securing-splunk-end-to-end-with-custom.html
---

By 2017, relying on Splunk’s default self-signed certificates wasn’t sufficient for any serious production environment. Whether you were dealing with regulatory frameworks like FedRAMP or just internal security policy, you needed to replace default certs across every connection surface.

This post outlines how we implemented internal PKI-backed TLS across Universal Forwarders, Deployment Server, Indexers, Search Heads, and Web UI. It covers certificate placement, config examples, validation tips, and failure points.

## Why Replace Splunk's Default Certs

- Default certs are self-signed and shared across installs
- No trust chain = warnings and audit failures
- Can't support client verification
- Impossible to manage at scale

## What Needs to Be Secured

- Universal Forwarders ➝ Deployment Server (8089)
- Universal Forwarders ➝ Indexers (9997)
- Search Heads ➝ Indexers (management and search)
- Web interface (8000)
- Indexer Cluster comms
- API and REST interfaces

## Certificate Types

We used:
- A single internal CA
- Unique certs per host role (`uf`, `idx`, `sh`, `ds`, `web`)
- Full PEM chain bundles (leaf, intermediate, root)
- Encrypted private keys where required

Each cert was stored at:

```
$SPLUNK_HOME/etc/auth/certs/<role>.pem
$SPLUNK_HOME/etc/auth/certs/internal-rootCA.pem
```

## Config Sections

### Universal Forwarder ➝ Deployment Server (`deploymentclient.conf`)

```ini
[deployment-client]
clientName = uf01.company.com

[target-broker:deploymentServer]
targetUri=https://splunk-ds.internal.company.com:8089

[sslConfig]
sslRootCAPath = $SPLUNK_HOME/etc/auth/certs/internal-rootCA.pem
sslVerifyServerCert = true
```

### Universal Forwarder ➝ Indexers (`outputs.conf`)

```ini
[tcpout:indexer_group]
server = idx1.internal.company.com:9997
sslCertPath = $SPLUNK_HOME/etc/auth/certs/uf.pem
sslPassword = $1$YourEncryptedPassword
sslRootCAPath = $SPLUNK_HOME/etc/auth/certs/internal-rootCA.pem
sslVerifyServerCert = true
```

### Indexer Configuration (`server.conf` and `inputs.conf`)

```ini
[sslConfig]
enableSplunkdSSL = true
serverCert = $SPLUNK_HOME/etc/auth/certs/indexer.pem
sslRootCAPath = $SPLUNK_HOME/etc/auth/certs/internal-rootCA.pem
sslVerifyClient = true
```

```ini
[splunktcp-ssl:9997]
disabled = 0
requireClientCert = true
```

### Web Interface (`web.conf`)

```ini
[settings]
enableSplunkWebSSL = true
serverCert = $SPLUNK_HOME/etc/auth/certs/web.pem
sslRootCAPath = $SPLUNK_HOME/etc/auth/certs/internal-rootCA.pem
```

## Operational Notes

- Certs must include the full chain if your CA uses intermediates
- Permissions on cert and key files must allow Splunk user read access
- Restart Splunk after applying cert changes
- Validate with:

```bash
openssl s_client -connect idx1.internal.company.com:9997
```

## Common Errors

| Symptom | Likely Cause |
|---------|---------------|
| "unknown CA" | Missing rootCA or broken chain |
| Forwarder won't connect | Hostname mismatch or `sslVerifyServerCert=true` |
| Web UI down | Incorrect file path or unreadable key |
| Internal components fail to handshake | Cert mismatch or server restarted without reload |

## Lessons Learned

- Secure from day one—retrofits are painful and high risk
- Use naming conventions for cert files by role and hostname
- Schedule cert rotation with automation and validation
- Always test on lower-tier environments before global rollout

Once we implemented this across the environment, our posture improved significantly. It also allowed us to meet internal compliance requirements with minimal recurring maintenance beyond cert renewals.

