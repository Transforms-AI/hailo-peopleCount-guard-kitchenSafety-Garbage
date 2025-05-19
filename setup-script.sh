# Create directory for project
#!/bin/bash
set -e

PROJECT_DIR="$HOME/hajj_system"
VENV_DIR="$PROJECT_DIR/degirum_env"
REPO_URL="https://github.com/Transforms-AI/hailo-peopleCount-guard-kitchenSafety-Garbage.git"


# Function to print colored output for better readability
print_colored() {
    echo -e "\e[1;34m$1\e[0m"
}

# Function to check if command was successful
check_status() {
    if [ $? -eq 0 ]; then
        echo -e "\e[1;32m✓ Success\e[0m"
    else
        echo -e "\e[1;31m✗ Failed\e[0m"
        echo "Error occurred. Exiting script."
        exit 1
    fi
}

# Script header
print_colored "====================================================================="
print_colored "    Raspberry Pi Setup Script for DeGirum PySDK and Hailo Hardware   "
print_colored "====================================================================="

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo "Please run this script as root or with sudo."
    exit 1
fi


# Step 1: Update system
print_colored "\n[1/10] Updating system packages..."
# Set environment variables to avoid interactive prompts
export DEBIAN_FRONTEND=noninteractive
apt update && apt full-upgrade -y -o Dpkg::Options::="--force-confnew"
check_status

# Step 2: Update Raspberry Pi firmware
print_colored "\n[2/10] Updating Raspberry Pi firmware..."
rpi-eeprom-update -a -y
check_status

# Step 3: Configure PCIe settings
print_colored "\n[3/10] Configuring PCIe settings..."
if ! grep -q "dtparam=pciex1_gen=3" /boot/firmware/config.txt; then
    echo "Adding PCIe Gen 3.0 speed configuration to /boot/firmware/config.txt"
    echo "dtparam=pciex1_gen=3" >> /boot/firmware/config.txt
    check_status
else
    echo "PCIe Gen 3.0 speed configuration already exists in config.txt"
fi

# Alternative method for configuring PCIe via raspi-config (commented out)
# This can be uncommented and used instead of directly modifying config.txt if needed
# echo "Configuring PCIe settings via raspi-config..."
# raspi-config nonint do_pciex1_gen 3
# check_status

# Step 4: Install Hailo Tools
print_colored "\n[4/10] Installing Hailo Tools..."
DEBIAN_FRONTEND=noninteractive apt install -y -o Dpkg::Options::="--force-confnew" hailo-all
check_status

# Step 5: Install Python Hailo runtime
print_colored "\n[5/10] Installing Python Hailo runtime..."
DEBIAN_FRONTEND=noninteractive apt install -y -o Dpkg::Options::="--force-confnew" python3-hailort
check_status

# Remove Step 6 (Hailo verification) - will be done after reboot
# Step 6: Set up project directory and clone repository
print_colored "\n[6/9] Setting up project directory and cloning repository..."
mkdir -p $PROJECT_DIR
cd $PROJECT_DIR

# Clone the repository
if [ -d "hailo-peopleCount-guard-kitchenSafety-Garbage" ]; then
    echo "Repository already exists. Pulling latest changes..."
    cd hailo-peopleCount-guard-kitchenSafety-Garbage
    git pull
    check_status
else
    echo "Cloning repository..."
    git clone "$REPO_URL"
    check_status
    cd hailo-peopleCount-guard-kitchenSafety-Garbage
    ls -lh
fi

# Create virtual environment
# Step 7: Set up Python virtual environment and installing dependencies
print_colored "\n[7/9] Setting up Python virtual environment and installing dependencies..."

# Check Python version
PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null)
if [[ ! "$PYTHON_VERSION" == "3.11" ]]; then
    echo "Warning: This script requires Python 3.11, but found Python $PYTHON_VERSION"
    echo "The Hailo runtime wheel might not be compatible."
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Exiting script."
        exit 1
    fi
fi

# Install python3-venv which is needed for virtual environment creation
print_colored "Installing python3-venv package..."
apt install -y python3-venv python3-full
check_status

if [ ! -d "$VENV_DIR" ]; then
    echo "Creating virtual environment..."
    python3 -m venv $VENV_DIR
    check_status
else
    echo "Virtual environment already exists."
fi

# Activate virtual environment and install dependencies
echo "Installing dependencies..."
if [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Error: Virtual environment activation script not found."
    exit 1
fi

# Use . instead of source for better compatibility
. $VENV_DIR/bin/activate
check_status

pip install --upgrade pip
check_status

pip install -r requirements.txt
check_status

# Download and install Hailo runtime wheel
echo "Downloading Hailo runtime wheel..."
# Ensure gdown is installed in the virtual environment
pip install gdown
check_status

# Check if wheel file already exists
if [ ! -f "hailort-4.20.0-cp311-cp311-linux_aarch64.whl" ]; then
    gdown "https://drive.google.com/uc?id=1NrRxzcMc45nQ4_nnoOd1xiU0o8e3EOUo"
    check_status
else
    echo "Hailo runtime wheel already downloaded."
fi

echo "Installing Hailo runtime wheel..."
pip install hailort-4.20.0-cp311-cp311-linux_aarch64.whl
check_status



# Download model files
print_colored "\n[8/9] Downloading model files and videos..."
cd $PROJECT_DIR/hailo-peopleCount-guard-kitchenSafety-Garbage

# Ensure gdown is installed in the virtual environment
pip install gdown
check_status

# Make the download_resources.sh script executable
chmod +x download_resources.sh

# Run the resource download script
./download_resources.sh
check_status

# Now we can deactivate the virtual environment
deactivate


# Create a launch script for testing
# Step 9: Create post-reboot check script and auto-run on login

print_colored "\n[9/9] Creating post-reboot check script..."

cat > $PROJECT_DIR/post_reboot_check.sh << 'EOS'
#!/bin/bash
set -e

PROJECT_DIR="$HOME/hajj_system"
VENV_DIR="$PROJECT_DIR/degirum_env"

print_colored() {
    echo -e "\e[1;34m$1\e[0m"
}

check_status() {
    if [ $? -eq 0 ]; then
        echo -e "\e[1;32m✓ Success\e[0m"
    else
        echo -e "\e[1;31m✗ Failed\e[0m"
        exit 1
    fi
}

print_colored "Checking Hailo hardware connection and driver/library version..."

IDENTIFY_OUTPUT=$(hailortcli fw-control identify 2>&1 || true)

if echo "$IDENTIFY_OUTPUT" | grep -q "Driver version.*is different from library version"; then
    print_colored "Driver/library version mismatch detected. Attempting to fix..."

    HAILORT_VERSION=$(dpkg -l | grep python3-hailort | awk '{print $3}' | cut -d'-' -f1)
    if [ -z "$HAILORT_VERSION" ]; then
        echo "Could not determine HailoRT version. Exiting."
        exit 1
    fi
    print_colored "Detected HailoRT library version: $HAILORT_VERSION"

    print_colored "Installing kernel headers..."
    sudo apt install -y linux-headers-$(uname -r)
    check_status

    print_colored "Cloning HailoRT driver repository..."
    rm -rf /tmp/hailort-drivers
    git clone --depth 1 --branch v$HAILORT_VERSION https://github.com/hailo-ai/hailort-drivers.git /tmp/hailort-drivers
    check_status

    cd /tmp/hailort-drivers/linux/pcie

    print_colored "Building and installing Hailo PCIe driver..."
    sudo make all
    sudo make install
    check_status

    print_colored "Loading hailo_pci module..."
    sudo modprobe hailo_pci
    lsmod | grep hailo_pci

    cd /tmp/hailort-drivers
    ./download_firmware.sh
    sudo mkdir -p /lib/firmware/hailo
    sudo mv hailo8_fw.*.bin /lib/firmware/hailo/hailo8_fw.bin
    sudo cp ./linux/pcie/51-hailo-udev.rules /etc/udev/rules.d/
    sudo udevadm control --reload-rules && sudo udevadm trigger
    check_status

    print_colored "Driver upgrade complete. Rebooting to load new driver..."
    sudo rm -f /etc/profile.d/post_reboot_check.sh
    sudo reboot
    exit 0
else
    print_colored "No driver/library version mismatch detected."
fi

print_colored "Running test script..."
cd "$PROJECT_DIR/hailo-peopleCount-guard-kitchenSafety-Garbage"
source "$VENV_DIR/bin/activate"
python test.py
deactivate

if systemctl is-active --quiet hailo-postreboot.service; then
    sudo systemctl disable hailo-postreboot.service
    sudo rm -f /etc/systemd/system/hailo-postreboot.service
    sudo systemctl daemon-reload
fi
EOS

chmod +x $PROJECT_DIR/post_reboot_check.sh
check_status

# Will run on reboot automatically
sudo tee /etc/systemd/system/hailo-postreboot.service > /dev/null << 'EOF'
[Unit]
Description=Hailo post-reboot check and driver fix
After=network-online.target

[Service]
Type=oneshot
User=admin
ExecStart=/home/admin/hajj_system/post_reboot_check.sh
StandardOutput=append:/home/admin/hailort.log
StandardError=append:/home/admin/hailort.log
RemainAfterExit=no

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable hailo-postreboot.service

check_status

print_colored "\n====================================================================="
print_colored "                        Setup Complete!                              "
print_colored "====================================================================="
echo ""
echo "A reboot is required for PCIe and Hailo driver changes to take effect."
echo "After reboot, the system will automatically:"
echo "  1. Verify the Hailo hardware connection"
echo "  2. If needed, update the kernel driver and reboot again"
echo "  3. Run a test to verify the installation"
echo ""
echo "You do not need to log in for this to happen."
echo ""
echo "Press any key to reboot now, or CTRL+C to cancel and reboot later."
read -n 1 -s
echo "Rebooting..."
reboot