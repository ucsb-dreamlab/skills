# Browser MCP Integration with Chrome DevTools

This guide covers how to set up and configure the Chrome DevTools MCP server for
opencode, enabling browser automation and screenshots.

## 1. Installing Headless Chrome

Chrome DevTools MCP requires a running Chrome or Chromium instance. In
non-graphical environments (like Coder Workspaces), Chrome must run in
**headless** mode.

```bash
# Install dependencies with apt:
sudo apt-get update && apt-get install -y wget curl gnupg nodejs npm

# Download and install official Google Chrome package:
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt-get install -y ./google-chrome-stable_current_amd64.deb
```

## 2. Configuring opencode

Once Chrome and npm are installed, register the `chrome-devtools` server in your
opencode configuration file.

- **Global Config:** `~/.config/opencode/opencode.json`
- **Project Config:** `opencode.json` (in your workspace root)

Add the following configuration block under the `"mcp"` key:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "chrome-devtools": {
      "type": "local",
      "command": ["npx", "-y", "chrome-devtools-mcp@latest", "--headless"],
      "enabled": true
    }
  }
}
```
The `--headless` flag is crucial when running opencode in a virtualized or
containerized terminal context that lacks a graphical display.

## 4. Verification

After saving the configuration, **quit and restart opencode**. Test the setup by asking:

```md
Take a screenshot of https://www.library.ucsb.edu
```
