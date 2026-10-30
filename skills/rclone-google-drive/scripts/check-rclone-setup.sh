#!/bin/bash

# Rclone Google Drive Setup Checker
# Verifies installation and guides through configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}   Rclone Google Drive Setup Checker${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""

# Check if rclone is installed
echo -e "${YELLOW}[1/3] Checking rclone installation...${NC}"
if command -v rclone &> /dev/null; then
    VERSION=$(rclone version | head -n 1)
    echo -e "${GREEN}✅ Rclone is installed${NC}"
    echo "    Version: $VERSION"
    echo ""
else
    echo -e "${RED}❌ Rclone is not installed${NC}"
    echo ""

    # Detect OS and offer installation
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo -e "${YELLOW}Installing rclone via Homebrew...${NC}"
        if ! command -v brew &> /dev/null; then
            echo -e "${RED}❌ Homebrew is not installed${NC}"
            echo "Install Homebrew first: https://brew.sh"
            echo "Then run: brew install rclone"
            exit 1
        fi

        brew install rclone
        echo -e "${GREEN}✅ Rclone installed successfully${NC}"
        echo ""
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        echo "Install rclone using your package manager:"
        echo "  Ubuntu/Debian: sudo apt-get install rclone"
        echo "  RedHat/CentOS: sudo yum install rclone"
        echo "  Or from source: curl https://rclone.org/install.sh | sudo bash"
        exit 1
    else
        echo "Visit https://rclone.org/install for installation instructions"
        exit 1
    fi
fi

# Check for Google Drive remote configuration
echo -e "${YELLOW}[2/3] Checking Google Drive remote configuration...${NC}"

CONFIG_FILE="${HOME}/.config/rclone/rclone.conf"

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}❌ No rclone configuration found${NC}"
    echo "    Configuration file: $CONFIG_FILE"
    GDRIVE_CONFIGURED=false
else
    # Check if any Google Drive remote exists
    if grep -q "type = drive" "$CONFIG_FILE" 2>/dev/null; then
        echo -e "${GREEN}✅ Google Drive remote(s) found${NC}"

        # List configured remotes
        echo ""
        echo "Configured remotes:"
        rclone listremotes | grep -v "^$" | sed 's/^/    /'

        GDRIVE_CONFIGURED=true
    else
        echo -e "${RED}❌ No Google Drive remote configured${NC}"
        GDRIVE_CONFIGURED=false
    fi
fi

echo ""

# Verify access to first Google Drive remote
if [ "$GDRIVE_CONFIGURED" = true ]; then
    echo -e "${YELLOW}[3/3] Verifying Google Drive access...${NC}"

    FIRST_REMOTE=$(rclone listremotes | head -n 1 | tr -d ':')

    if [ -z "$FIRST_REMOTE" ]; then
        echo -e "${RED}❌ No remotes found${NC}"
    else
        echo "Testing remote: ${FIRST_REMOTE}"

        if rclone lsd "${FIRST_REMOTE}:" &> /dev/null; then
            echo -e "${GREEN}✅ Successfully connected to Google Drive (${FIRST_REMOTE}:)${NC}"

            # Show quota info if available (not supported on Shared Drives)
            echo ""
            rclone about "${FIRST_REMOTE}:" 2>/dev/null || true
        else
            echo -e "${YELLOW}⚠️  Cannot access remote (may need re-authentication or drive scope)${NC}"
            echo "Use the google-oauth skill to authenticate and update rclone:"
            echo "  uv run skills/google-oauth/scripts/google_oauth.py status"
            echo "  uv run skills/google-oauth/scripts/google_oauth.py url --scopes drive"
            echo "  uv run skills/google-oauth/scripts/google_oauth.py exchange '<REDIRECT_URL>'"
            echo "  uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote ${FIRST_REMOTE}"
        fi
    fi

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Rclone Google Drive is ready to use!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Quick start commands:"
    echo "  rclone lsd ${FIRST_REMOTE}:                  # List top-level directories"
    echo "  rclone ls ${FIRST_REMOTE}:\"MyFolder\"         # List files in a specific folder"
    echo "  rclone about ${FIRST_REMOTE}:                # View quota (My Drive)"
    echo ""
    echo "For detailed help, see: SKILL.md"
    echo ""

else
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Setting up Google Drive access via google-oauth skill...${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Use the google-oauth skill to authenticate and configure rclone:"
    echo ""
    echo "  1. Check existing credentials/scopes:"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py status"
    echo ""
    echo "  2. If 'drive' scope is not yet granted, generate an auth URL and exchange:"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py url --scopes drive"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py exchange '<REDIRECT_URL>'"
    echo ""
    echo "  3. Configure the rclone remote (for My Drive or a Shared Drive):"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive"
    echo "     # Or for a Shared Drive:"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --list-shared-drives"
    echo "     uv run skills/google-oauth/scripts/google_oauth.py configure-rclone --remote gdrive --shared-drive \"<NAME_OR_ID>\""
    echo ""
fi
