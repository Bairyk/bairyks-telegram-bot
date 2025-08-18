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
    
    if command -v yt-dlp &> /dev/null; then
        print_success "yt-dlp already installed"
        return
    fi
    
    # Try to install via system package manager first
    case $DISTRO in
        "debian")
            if apt-cache show yt-dlp &> /dev/null; then
                sudo apt-get install -y yt-dlp
            else
                # Fallback to pip installation
                python3 -m pip install --user yt-dlp
            fi
            ;;
        "arch")
            sudo pacman -S yt-dlp
            ;;
        *)
            # Fallback to pip installation
            python3 -m pip install --user yt-dlp
            ;;
    esac
    
    if [[ "$OS" == "macos" ]]; then
        brew install yt-dlp
    fi
    
    # Verify installation
    if command -v yt-dlp &> /dev/null; then
        print_success "yt-dlp installed successfully"
    else
        print_error "Failed to install yt-dlp"
        exit 1
    fi
}

# Install gallery-dl
install_gallery_dl() {
    print_status "Installing gallery-dl..."
    
    if command -v gallery-dl &> /dev/null; then
        print_success "gallery-dl already installed"
        return
    fi
    
    # Install via pip
    python3 -m pip install --user gallery-dl
    
    # Verify installation
    if command -v gallery-dl &> /dev/null || python3 -m gallery_dl --version &> /dev/null; then
        print_success "gallery-dl installed successfully"
    else
        print_error "Failed to install gallery-dl"
        exit 1
    fi
}

# Create project directory and virtual environment
setup_project() {
    print_status "Setting up project directory..."
    
    # Ask for installation directory
    echo -n "Enter installation directory [/opt/telegram-bot]: "
    read INSTALL_DIR
    INSTALL_DIR=${INSTALL_DIR:-/opt/telegram-bot}
    
    # Create directory
    if [[ ! -d "$INSTALL_DIR" ]]; then
        sudo mkdir -p "$INSTALL_DIR"
        sudo chown $USER:$USER "$INSTALL_DIR"
    fi
    
    cd "$INSTALL_DIR"
    
    # Create virtual environment
    if [[ ! -d "venv" ]]; then
        print_status "Creating virtual environment..."
        python3 -m venv venv
    fi
    
    # Activate virtual environment
    source venv/bin/activate
    
    # Upgrade pip
    pip install --upgrade pip
    
    print_success "Project directory setup complete: $INSTALL_DIR"
}

# Install Python dependencies
install_python_deps() {
    print_status "Installing Python dependencies..."
    
    # Create requirements.txt if it doesn't exist
    if [[ ! -f "requirements.txt" ]]; then
        cat > requirements.txt << EOF
# Core Telegram bot dependencies
python-telegram-bot==20.7
requests==2.31.0

# Media downloading tools
yt-dlp>=2023.12.30
gallery-dl>=1.26.0

# Additional utilities
pathlib2==2.3.7
aiofiles==23.2.1
python-dotenv==1.0.0

# Optional: For Deezer downloading
pydeezer==1.4.1
mutagen==1.47.0

# For deployment
gunicorn==21.2.0
uvloop==0.19.0
EOF
    fi
    
    # Install requirements
    pip install -r requirements.txt
    
    print_success "Python dependencies installed"
}

# Setup configuration
setup_config() {
    print_status "Setting up configuration..."
    
    # Create .env file
    if [[ ! -f ".env" ]]; then
        echo "# Telegram Bot Configuration" > .env
        echo "" >> .env
        
        # Get Telegram Bot Token
        echo -n "Enter your Telegram Bot Token (from @BotFather): "
        read -s BOT_TOKEN
        echo ""
        
        if [[ -z "$BOT_TOKEN" ]]; then
            print_error "Bot token is required!"
            exit 1
        fi
        
        echo "TELEGRAM_BOT_TOKEN=$BOT_TOKEN" >> .env
        
        # Get Deezer ARL (optional)
        echo -n "Enter your Deezer ARL token (optional, press Enter to skip): "
        read -s DEEZER_ARL
        echo ""
        
        if [[ -n "$DEEZER_ARL" ]]; then
            echo "DEEZER_ARL=$DEEZER_ARL" >> .env
        else
            echo "# DEEZER_ARL=your_arl_token_here" >> .env
        fi
        
        # Add other configuration
        cat >> .env << EOF

# Optional: Custom settings
MAX_FILE_SIZE=52428800
TEMP_DIR=/tmp/telegram_bot
LOG_LEVEL=INFO
EOF
        
        # Secure the file
        chmod 600 .env
        
        print_success "Configuration file created: .env"
    else
        print_warning ".env file already exists. Skipping configuration setup."
    fi
}

# Download bot files
download_bot_files() {
    print_status "Setting up bot files..."
    
    # Create directories
    mkdir -p logs temp config tests
    
    # If running from repository, files should already exist
    if [[ -f "bot.py" ]]; then
        print_success "Bot files already present"
        return
    fi
    
    # Otherwise, create basic bot.py (user should replace with actual implementation)
    print_warning "bot.py not found. Please ensure you have the complete bot implementation."
    print_warning "You can download it from the repository or copy the provided code."
}

# Create systemd service (Linux only)
create_systemd_service() {
    if [[ "$OS" != "linux" ]]; then
        return
    fi
    
    echo -n "Do you want to create a systemd service for auto-startup? [y/N]: "
    read CREATE_SERVICE
    
    if [[ "$CREATE_SERVICE" =~ ^[Yy]$ ]]; then
        print_status "Creating systemd service..."
        
        # Ask for service user
        echo -n "Enter username to run the service [$USER]: "
        read SERVICE_USER
        SERVICE_USER=${SERVICE_USER:-$USER}
        
        # Create service file
        sudo tee /etc/systemd/system/telegram-media-bot.service > /dev/null << EOF
[Unit]
Description=Telegram Media Downloader Bot
After=network.target
Wants=network.target

[Service]
Type=simple
User=$SERVICE_USER
Group=$SERVICE_USER
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/venv/bin/python $INSTALL_DIR/bot.py
Restart=always
RestartSec=10
Environment=PATH=/usr/bin:/usr/local/bin
EnvironmentFile=$INSTALL_DIR/.env

# Security settings
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$INSTALL_DIR/logs $INSTALL_DIR/temp /tmp/telegram_bot
PrivateTmp=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true

[Install]
WantedBy=multi-user.target
EOF
        
        # Reload systemd and enable service
        sudo systemctl daemon-reload
        sudo systemctl enable telegram-media-bot
        
        print_success "Systemd service created and enabled"
        print_status "Start the service with: sudo systemctl start telegram-media-bot"
        print_status "View logs with: sudo journalctl -u telegram-media-bot -f"
    fi
}

# Setup firewall (if needed)
setup_firewall() {
    if [[ "$OS" != "linux" ]]; then
        return
    fi
    
    if command -v ufw &> /dev/null; then
        echo -n "Do you want to configure UFW firewall? [y/N]: "
        read SETUP_FIREWALL
        
        if [[ "$SETUP_FIREWALL" =~ ^[Yy]$ ]]; then
            print_status "Configuring UFW firewall..."
            
            # Allow SSH
            sudo ufw allow ssh
            
            # Allow HTTP/HTTPS if setting up webhooks
            echo -n "Will you be using webhooks (HTTP/HTTPS)? [y/N]: "
            read USE_WEBHOOKS
            
            if [[ "$USE_WEBHOOKS" =~ ^[Yy]$ ]]; then
                sudo ufw allow 80
                sudo ufw allow 443
            fi
            
            # Enable firewall
            sudo ufw --force enable
            
            print_success "Firewall configured"
        fi
    fi
}

# Run tests
run_tests() {
    echo -n "Do you want to run tests to verify the installation? [y/N]: "
    read RUN_TESTS
    
    if [[ "$RUN_TESTS" =~ ^[Yy]$ ]]; then
        print_status "Running tests..."
        
        # Install test dependencies
        pip install pytest pytest-asyncio
        
        # Run tests if test file exists
        if [[ -f "test_bot.py" ]]; then
            python -m pytest test_bot.py -v
        else
            print_warning "Test file not found. Skipping tests."
        fi
    fi
}

# Create startup script
create_startup_script() {
    print_status "Creating startup script..."
    
    cat > start_bot.sh << 'EOF'
#!/bin/bash

# Get script directory
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to script directory
cd "$DIR"

# Activate virtual environment
source venv/bin/activate

# Start the bot
python bot.py
EOF
    
    chmod +x start_bot.sh
    
    print_success "Startup script created: start_bot.sh"
}

# Print final instructions
print_final_instructions() {
    print_success "Installation completed successfully!"
    echo ""
    echo -e "${BLUE}=== NEXT STEPS ===${NC}"
    echo ""
    
    if [[ -f ".env" ]]; then
        print_status "1. Your bot is configured and ready to run"
    else
        print_warning "1. Configure your bot by editing the .env file:"
        echo "   nano .env"
        echo "   Add your TELEGRAM_BOT_TOKEN and optionally DEEZER_ARL"
    fi
    
    echo ""
    print_status "2. Start your bot:"
    echo "   cd $INSTALL_DIR"
    echo "   ./start_bot.sh"
    echo "   OR"
    echo "   source venv/bin/activate && python bot.py"
    
    if [[ "$OS" == "linux" ]] && systemctl is-enabled telegram-media-bot &> /dev/null; then
        echo "   OR (using systemd service):"
        echo "   sudo systemctl start telegram-media-bot"
    fi
    
    echo ""
    print_status "3. Test your bot:"
    echo "   Send /start to your bot on Telegram"
    echo "   Try /search <song name>"
    echo "   Try /download <supported URL>"
    
    echo ""
    print_status "4. Monitor your bot:"
    echo "   View logs: tail -f $INSTALL_DIR/logs/bot.log"
    if systemctl is-enabled telegram-media-bot &> /dev/null; then
        echo "   Service logs: sudo journalctl -u telegram-media-bot -f"
    fi
    
    echo ""
    print_status "5. Useful commands:"
    echo "   Update bot: git pull (if using git)"
    echo "   Restart: sudo systemctl restart telegram-media-bot"
    echo "   Stop: sudo systemctl stop telegram-media-bot"
    
    echo ""
    echo -e "${GREEN}Happy botting! 🤖${NC}"
}

# Main installation function
main() {
    echo -e "${BLUE}"
    echo "=================================="
    echo "Telegram Media Downloader Bot"
    echo "Setup and Installation Script"
    echo "=================================="
    echo -e "${NC}"
    
    check_root
    detect_os
    
    echo ""
    print_status "This script will install and configure the Telegram Media Downloader Bot"
    echo -n "Do you want to continue? [Y/n]: "
    read CONTINUE
    
    if [[ "$CONTINUE" =~ ^[Nn]$ ]]; then
        print_status "Installation cancelled"
        exit 0
    fi
    
    # Installation steps
    install_system_deps
    install_ytdlp
    install_gallery_dl
    setup_project
    install_python_deps
    download_bot_files
    setup_config
    create_startup_script
    
    # Optional steps
    create_systemd_service
    setup_firewall
    run_tests
    
    # Final instructions
    print_final_instructions
}

# Run main function
main "$@"
