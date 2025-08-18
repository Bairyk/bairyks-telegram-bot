#!/bin/bash

# Telegram Media Downloader Bot - Setup Script
# This script automates the installation and setup process

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
check_root() {
    if [[ $EUID -eq 0 ]]; then
        print_warning "Running as root. Consider creating a dedicated user for the bot."
    fi
}

# Detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="linux"
        if command -v apt-get &> /dev/null; then
            DISTRO="debian"
        elif command -v yum &> /dev/null; then
            DISTRO="redhat"
        elif command -v pacman &> /dev/null; then
            DISTRO="arch"
        fi
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
    else
        print_error "Unsupported operating system: $OSTYPE"
        exit 1
    fi
    
    print_status "Detected OS: $OS ($DISTRO)"
}

# Install system dependencies
install_system_deps() {
    print_status "Installing system dependencies..."
    
    case $DISTRO in
        "debian")
            sudo apt-get update
            sudo apt-get install -y python3 python3-pip python3-venv ffmpeg curl wget git
            ;;
        "redhat")
            sudo yum update -y
            sudo yum install -y python3 python3-pip python3-venv ffmpeg curl wget git
            ;;
        "arch")
            sudo pacman -Sy python python-pip python-virtualenv ffmpeg curl wget git
            ;;
        *)
            if [[ "$OS" == "macos" ]]; then
                if ! command -v brew &> /dev/null; then
                    print_error "Homebrew not found. Please install Homebrew first."
                    exit 1
                fi
                brew install python ffmpeg wget git
            else
                print_error "Unsupported distribution. Please install dependencies manually."
                exit 1
            fi
            ;;
    esac
    
    print_success "System dependencies installed"
}

# Install yt-dlp
install_ytdlp() {
    print_status "Installing yt-dlp..."
    
    if command -v yt-dlp &> /
