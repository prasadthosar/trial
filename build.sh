#!/usr/bin/env bash
# Install Chrome
apt-get update
apt-get install -y wget unzip gnupg
wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
apt-get install -y ./google-chrome-stable_current_amd64.deb
rm google-chrome-stable_current_amd64.deb

# Install ChromeDriver
# Get Chrome version safely handling any errors
CHROME_VERSION=$(google-chrome --version 2>/dev/null || echo "")
if [ -z "$CHROME_VERSION" ]; then
    # Default to a recent version if we can't detect
    CHROME_VERSION="114"
else
    # Extract just the major version number
    CHROME_VERSION=$(echo $CHROME_VERSION | grep -oP '\d+' | head -1 || echo "114")
fi
echo "Detected Chrome version: $CHROME_VERSION"

# Get the matching ChromeDriver
CHROMEDRIVER_VERSION=$(curl -s "https://chromedriver.storage.googleapis.com/LATEST_RELEASE_$CHROME_VERSION" || echo "114.0.5735.90")
echo "Using ChromeDriver version: $CHROMEDRIVER_VERSION"

wget -q "https://chromedriver.storage.googleapis.com/$CHROMEDRIVER_VERSION/chromedriver_linux64.zip"
unzip chromedriver_linux64.zip
mv chromedriver /usr/local/bin/
rm chromedriver_linux64.zip

# Set Chrome path for the app to use
export CHROME_PATH=$(which google-chrome-stable)
