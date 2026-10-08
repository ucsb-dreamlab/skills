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

        if rclone about "${FIRST_REMOTE}:" &> /dev/null; then
            echo -e "${GREEN}✅ Successfully connected to Google Drive${NC}"

            # Show quota info
            echo ""
            rclone about "${FIRST_REMOTE}:" 2>/dev/null || true
        else
            echo -e "${YELLOW}⚠️  Cannot access remote (may need re-authentication)${NC}"
            echo "Run: rclone config edit"
            echo "Then re-authenticate when prompted"
        fi
    fi

    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}✅ Rclone Google Drive is ready to use!${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Quick start commands:"
    echo "  rclone lsd ${FIRST_REMOTE}:           # List directories"
    echo "  rclone ls ${FIRST_REMOTE}:            # List all files"
    echo "  rclone about ${FIRST_REMOTE}:         # View quota"
    echo "  rclone help                # Show all commands"
    echo ""
    echo "For detailed help, see: SKILL.md"
    echo ""

else
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}Setting up Google Drive access...${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Run the following command to configure Google Drive:"
    echo ""
    echo -e "${YELLOW}    rclone config${NC}"
    echo ""
    echo "Configuration steps:"
    echo "  1. Type 'n' to add a new remote"
    echo "  2. Enter remote name (e.g., 'gdrive')"
    echo "  3. Select '17' for Google Drive storage type"
    echo "  4. Leave OAuth Client ID/Secret blank (use defaults)"
    echo "  5. Select scope '1' for 'drive' (full access)"
    echo "  6. Answer 'y' to auto config (browser will open)"
    echo "  7. Sign in with your Google account"
    echo "  8. Grant permission"
    echo "  9. Type 'q' to quit config"
    echo ""
    echo "Then run this script again to verify setup."
    echo ""

    read -p "Ready to run 'rclone config'? (y/n): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rclone config
        echo ""
        echo "Configuration complete! Running setup check again..."
        echo ""
        # Re-run this script to verify
        bash "$(dirname "$0")/check-rclone-setup.sh"
    fi
fi
