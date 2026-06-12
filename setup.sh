#!/bin/bash
# =============================================================================
# Job Intelligence Platform - Setup Script
# =============================================================================
# Run this script to set up the environment for first-time use

set -e

echo "============================================"
echo "  Job Intelligence Platform - Setup"
echo "============================================"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check Python version
echo "Checking Python version..."
PYTHON_VERSION=$(python3 --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}Error: Python 3.10 or higher is required${NC}"
    echo "Current version: Python $PYTHON_VERSION"
    exit 1
fi
echo -e "${GREEN}✓ Python $PYTHON_VERSION detected${NC}"
echo ""

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    echo -e "${GREEN}✓ Virtual environment created${NC}"
else
    echo -e "${YELLOW}⚠ Virtual environment already exists${NC}"
fi
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo -e "${GREEN}✓ Virtual environment activated${NC}"
echo ""

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip > /dev/null 2>&1
echo -e "${GREEN}✓ pip upgraded${NC}"
echo ""

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt
echo -e "${GREEN}✓ Dependencies installed${NC}"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p logs
mkdir -p credentials
touch logs/.gitkeep
touch credentials/.gitkeep
echo -e "${GREEN}✓ Directories created${NC}"
echo ""

# Copy .env.example to .env if it doesn't exist
if [ ! -f ".env" ]; then
    echo "Creating .env file from template..."
    cp .env.example .env
    echo -e "${YELLOW}⚠ Please edit .env file with your credentials${NC}"
else
    echo -e "${YELLOW}⚠ .env file already exists${NC}"
fi
echo ""

# Run verification tests
echo "============================================"
echo "  Running Verification Tests"
echo "============================================"
echo ""

echo "Testing --help command..."
python src/main.py --help > /dev/null 2>&1
echo -e "${GREEN}✓ --help command works${NC}"

echo "Testing --test-scorer command..."
python src/main.py --test-scorer > /dev/null 2>&1
echo -e "${GREEN}✓ --test-scorer command works${NC}"

echo ""
echo "============================================"
echo -e "${GREEN}  Setup Complete!${NC}"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Edit config/user_profile.yaml with your preferences"
echo "  2. (Optional) Edit .env with your credentials"
echo "  3. Run: python src/main.py --test-scorer"
echo ""