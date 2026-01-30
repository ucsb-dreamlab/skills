---
name: dreamlab-coder-workspace
description: Use features of the DREAM Lab Coder Workspace Environment
---

You are running in a virtual machine using ubuntu 24.04.
- you have `sudo` access
- available commands: `uv`, `R`, `Rscript`, `gh`, `docker`, `jq`
- the user does not have access to ports running on localhost (see TLS termination)

## TLS Termination for HTTP ports

If you start an http server on `$SERVER_PORT`, the server can be accessed at:
`https://${SERVER_PORT}--workspace--$(hostname)--${CODER_WORKSPACE_OWNER_NAME}.coder.dreamlab.ucsb.edu`

## LiteLLM AI Gateway

API endpoint: http://litellm.dreamlab.ucsb.edu:4000

To access to the admin interface (web ui):

```sh
# forward workspace's :4000 to gateways's :4000
nohup socat TCP-LISTEN:4000,fork,reuseaddr TCP:litellm.dreamlab.ucsb.edu:4000 &

# the admin interface is now accessible at
echo "The LiteLLM Admin interface is availble at:"
echo "https://4000--workspace--$(hostname)--${CODER_WORKSPACE_OWNER_NAME}.coder.dreamlab.ucsb.edu"
```
