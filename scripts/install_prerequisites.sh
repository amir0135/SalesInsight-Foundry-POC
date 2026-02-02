#!/bin/bash
# =============================================================================
# Prerequisites Installer for Chat With Your Data
# =============================================================================
# Installs all required tools for local development.
# Supports macOS (Homebrew) and Linux (apt/yum).
#
# Usage:
#   ./scripts/install_prerequisites.sh
# =============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     Chat With Your Data - Prerequisites Installer          ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Detect OS
OS="unknown"
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
elif [[ -f /etc/debian_version ]]; then
    OS="debian"
elif [[ -f /etc/redhat-release ]]; then
    OS="redhat"
fi

echo -e "${BLUE}Detected OS: $OS${NC}"
echo ""

# =============================================================================
# macOS Installation (Homebrew)
# =============================================================================
install_macos() {
    # Install Homebrew if not present
    if ! command -v brew &> /dev/null; then
        echo -e "${YELLOW}Installing Homebrew...${NC}"
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    echo -e "${GREEN}✓ Homebrew installed${NC}"

    # Install tools
    echo -e "${BLUE}Installing development tools...${NC}"
    
    # Azure CLI
    if ! command -v az &> /dev/null; then
        echo -e "${YELLOW}Installing Azure CLI...${NC}"
        brew install azure-cli
    fi
    echo -e "${GREEN}✓ Azure CLI$(az --version 2>/dev/null | head -1 | awk '{print " "$2}')${NC}"

    # Azure Developer CLI
    if ! command -v azd &> /dev/null; then
        echo -e "${YELLOW}Installing Azure Developer CLI...${NC}"
        brew install azure/azd/azd
    fi
    echo -e "${GREEN}✓ Azure Developer CLI installed${NC}"

    # Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Installing Docker...${NC}"
        brew install --cask docker
        echo -e "${YELLOW}⚠ Please open Docker Desktop to complete installation${NC}"
    fi
    echo -e "${GREEN}✓ Docker installed${NC}"

    # Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Installing Node.js...${NC}"
        brew install node@20
    fi
    echo -e "${GREEN}✓ Node.js $(node --version 2>/dev/null)${NC}"

    # Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Installing Python...${NC}"
        brew install python@3.11
    fi
    echo -e "${GREEN}✓ Python $(python3 --version 2>/dev/null | cut -d' ' -f2)${NC}"

    # Poetry
    if ! command -v poetry &> /dev/null; then
        echo -e "${YELLOW}Installing Poetry...${NC}"
        curl -sSL https://install.python-poetry.org | python3 -
    fi
    echo -e "${GREEN}✓ Poetry installed${NC}"

    # Azure Functions Core Tools
    if ! command -v func &> /dev/null; then
        echo -e "${YELLOW}Installing Azure Functions Core Tools...${NC}"
        brew tap azure/functions
        brew install azure-functions-core-tools@4
    fi
    echo -e "${GREEN}✓ Azure Functions Core Tools installed${NC}"
}

# =============================================================================
# Linux (Debian/Ubuntu) Installation
# =============================================================================
install_debian() {
    sudo apt-get update

    # Azure CLI
    if ! command -v az &> /dev/null; then
        echo -e "${YELLOW}Installing Azure CLI...${NC}"
        curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash
    fi
    echo -e "${GREEN}✓ Azure CLI installed${NC}"

    # Azure Developer CLI
    if ! command -v azd &> /dev/null; then
        echo -e "${YELLOW}Installing Azure Developer CLI...${NC}"
        curl -fsSL https://aka.ms/install-azd.sh | bash
    fi
    echo -e "${GREEN}✓ Azure Developer CLI installed${NC}"

    # Docker
    if ! command -v docker &> /dev/null; then
        echo -e "${YELLOW}Installing Docker...${NC}"
        curl -fsSL https://get.docker.com | sudo sh
        sudo usermod -aG docker $USER
        echo -e "${YELLOW}⚠ Log out and back in for Docker permissions${NC}"
    fi
    echo -e "${GREEN}✓ Docker installed${NC}"

    # Node.js
    if ! command -v node &> /dev/null; then
        echo -e "${YELLOW}Installing Node.js...${NC}"
        curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
        sudo apt-get install -y nodejs
    fi
    echo -e "${GREEN}✓ Node.js $(node --version 2>/dev/null)${NC}"

    # Python
    if ! command -v python3 &> /dev/null; then
        echo -e "${YELLOW}Installing Python...${NC}"
        sudo apt-get install -y python3.11 python3.11-venv python3-pip
    fi
    echo -e "${GREEN}✓ Python installed${NC}"

    # Poetry
    if ! command -v poetry &> /dev/null; then
        echo -e "${YELLOW}Installing Poetry...${NC}"
        curl -sSL https://install.python-poetry.org | python3 -
    fi
    echo -e "${GREEN}✓ Poetry installed${NC}"

    # Azure Functions Core Tools
    if ! command -v func &> /dev/null; then
        echo -e "${YELLOW}Installing Azure Functions Core Tools...${NC}"
        npm install -g azure-functions-core-tools@4 --unsafe-perm true
    fi
    echo -e "${GREEN}✓ Azure Functions Core Tools installed${NC}"
}

# =============================================================================
# Run Installation
# =============================================================================
case $OS in
    macos)
        install_macos
        ;;
    debian)
        install_debian
        ;;
    *)
        echo -e "${RED}Unsupported OS. Please install manually:${NC}"
        echo "  - Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli"
        echo "  - Azure Developer CLI: https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd"
        echo "  - Docker: https://docs.docker.com/get-docker/"
        echo "  - Node.js 20+: https://nodejs.org"
        echo "  - Python 3.11+: https://www.python.org"
        echo "  - Poetry: https://python-poetry.org"
        exit 1
        ;;
esac

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║     ✓ All prerequisites installed successfully!            ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Next steps:"
echo -e "  1. ${BLUE}az login${NC}              # Login to Azure"
echo -e "  2. ${BLUE}azd up${NC}                # Deploy to Azure"
echo -e "  3. ${BLUE}./scripts/setup_local.sh${NC}  # Configure local dev"
echo -e "  4. ${BLUE}./start_local.sh${NC}      # Start the app"
echo ""
echo -e "Or use Docker:"
echo -e "  1. ${BLUE}cp .env.example .env${NC}  # Create config file"
echo -e "  2. ${BLUE}# Edit .env with your Azure values${NC}"
echo -e "  3. ${BLUE}docker-compose -f docker/docker-compose.local.yml up${NC}"
echo ""
