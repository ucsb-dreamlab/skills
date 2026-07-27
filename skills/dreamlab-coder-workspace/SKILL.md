---
name: dreamlab-coder-workspace
description: Use features of the DREAM Lab Coder Workspace Environment
---

You are running in an Ubuntu-based virtual machine with sudo access. 
Coder workspace documentation is at https://dreamlab.ucsb.edu

Check if you are running in coder workspace:

```sh
if [ "$CODER" == "true" ]; then echo "this is a coder workspace"; else echo "this IS NOT a coder workspace"; fi
```

## Reverse Proxy & TLS Termination for Locahost Ports

The user doesn't have direct access to http ports on localhost (e.g, for local
web development), however there is a reverse proxy with TLS termination
forwarding traffic to local ports:

If you start an http server on `$SERVER_PORT`, the server can be accessed at:
`https://${SERVER_PORT}--workspace--$(hostname)--${CODER_WORKSPACE_OWNER_NAME}.coder.dreamlab.ucsb.edu`

The user may need to configure the proxy to accept public traffic.

## Additional Docs

- To enable browser support in opencode (chrome devtools mcp), read docs/browser-mcp.md