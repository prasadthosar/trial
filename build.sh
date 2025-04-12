#!/usr/bin/env bash
# Exit on any error
set -e

echo "===== Starting Chrome and Chromedriver installation ====="

# Install dependencies
echo "Installing dependencies..."
apt-get update
apt-get install -y wget unzip gnupg apt-transport-https ca-certificates

# Add Google Chrome repository
echo "Adding Chrome repository..."
wget -q -O - https://dl.google.com/linux/linux_signing_key.pub | apt-key add -
echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list
apt-get update

# Install Chrome
echo "Installing Google Chrome..."
apt-get install -y google-chrome-stable
chrome_path=$(which google-chrome-stable || echo "/usr/bin/google-chrome-stable")
echo "Chrome installed at: $chrome_path"

# Verify Chrome installation
echo "Verifying Chrome installation..."
if [ -f "$chrome_path" ]; then
    echo "Chrome binary exists at $chrome_path"
else
    echo "Chrome binary not found at expected location"
    # Try to find it elsewhere
    chrome_path=$(find /usr -name google-chrome-stable 2>/dev/null | head -1)
    if [ -n "$chrome_path" ]; then
        echo "Found Chrome at: $chrome_path"
    else
        echo "WARNING: Could not find Chrome binary"
    fi
fi

# Get Chrome version with fallback
chrome_version=$($chrome_path --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+\.[0-9]+' | cut -d. -f1 || echo "114")
echo "Chrome version: $chrome_version"

# Install ChromeDriver
echo "Installing ChromeDriver for Chrome version $chrome_version..."
chromedriver_version=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$chrome_version" || echo "114.0.5735.90")
echo "ChromeDriver version: $chromedriver_version"

wget -q "https://chromedriver.storage.googleapis.com/$chromedriver_version/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
chmod +x chromedriver
mv chromedriver /usr/local/bin/
echo "ChromeDriver installed at: $(which chromedriver)"
rm chromedriver_linux64.zip

# Set environment variables
echo "Setting environment variables..."
echo "export CHROME_PATH=\"$chrome_path\"" >> $HOME/.profile
echo "export CHROME_PATH=\"$chrome_path\"" >> $HOME/.bashrc
export CHROME_PATH="$chrome_path"

# Create a directory for browser data
mkdir -p /tmp/chrome-data

echo "===== Chrome and ChromeDriver installation completed ====="
