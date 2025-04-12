import os
import sys

# Add compatibility imports
import importlib.metadata
try:
    importlib.metadata.version('werkzeug')
except importlib.metadata.PackageNotFoundError:
    import pkg_resources
    pkg_resources.require('werkzeug')

# Explicit URL quote import
from werkzeug.urls import url_quote_plus as url_quote


import csv
import os
import time
import json
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from datetime import datetime, timedelta
from flask import Flask, jsonify, send_file, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Global variables
latest_data = {}  # Stores the most recent data
csv_filename = "mcx_aluminium_prices.csv"

# Ensure directory exists if needed
os.makedirs(os.path.dirname(csv_filename) if os.path.dirname(csv_filename) else '.', exist_ok=True)

# URL of the page
url = "https://www.5paisa.com/commodity-trading/mcx-aluminium-price"

# Setup Selenium WebDriver
def get_driver():
    """Initialize and return a Chrome WebDriver with appropriate settings for headless operation."""
    try:
        # Debug output for Chrome location
        chrome_path = os.environ.get('CHROME_PATH')
        print(f"Chrome path from environment: {chrome_path}")
        
        if not chrome_path:
            # Try to find Chrome in common locations
            possible_paths = [
                "/usr/bin/google-chrome-stable",
                "/usr/bin/google-chrome",
                "/usr/local/bin/google-chrome",
                "/opt/google/chrome/google-chrome"
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    chrome_path = path
                    print(f"Found Chrome at: {chrome_path}")
                    break
        
        options = webdriver.ChromeOptions()
        
        # Configure Chrome options for headless environment
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36")
        
        # Add data directory to prevent profile errors
        options.add_argument("--user-data-dir=/tmp/chrome-data")
        
        # Set binary location if we have a path
        if chrome_path and os.path.exists(chrome_path):
            print(f"Setting Chrome binary location to: {chrome_path}")
            options.binary_location = chrome_path
        
        # First try with ChromeDriverManager
        try:
            print("Attempting to initialize Chrome with ChromeDriverManager...")
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=options)
            print("Successfully initialized Chrome with ChromeDriverManager")
            return driver
        except Exception as manager_err:
            print(f"Error using ChromeDriverManager: {str(manager_err)}")
            
            # Try with default Service
            try:
                print("Attempting to initialize Chrome with default Service...")
                service = Service()
                driver = webdriver.Chrome(service=service, options=options)
                print("Successfully initialized Chrome with default Service")
                return driver
            except Exception as service_err:
                print(f"Error using default Service: {str(service_err)}")
                
                # Try with explicit chromedriver path
                try:
                    print("Attempting to initialize Chrome with explicit chromedriver path...")
                    chromedriver_path = "/usr/local/bin/chromedriver"
                    service = Service(executable_path=chromedriver_path)
                    driver = webdriver.Chrome(service=service, options=options)
                    print("Successfully initialized Chrome with explicit chromedriver path")
                    return driver
                except Exception as explicit_err:
                    print(f"Error using explicit chromedriver path: {str(explicit_err)}")
                    raise
    
    except Exception as e:
        print(f"❌ Error initializing Chrome driver: {str(e)}")
        raise Exception(f"Failed to initialize Chrome: {str(e)}")

def get_contract_months():
    today = datetime.today()
    contract_months = {}
    
    for i in range(3):
        future_date = today.replace(day=1) + timedelta(days=32 * i)  # Jump to next month
        future_date = future_date.replace(day=30)  # Always set to the 30th
        month_year_str = future_date.strftime("%B %Y")  # Format: "April 2025"
        
        month_name = future_date.strftime("%B").lower()
        month_num = future_date.month
        year = future_date.year
        
        xpath_options = [
            f"//input[contains(@value, '{month_num}-30-{year}')]",
            f"//input[contains(@value, '{month_name}-30-{year}')]",
            f"//label[contains(text(), '{month_name}')]/input",
            f"//label[contains(normalize-space(), '{month_name} {year}')]",
            f"//div[contains(@class, 'contract') and contains(text(), '{month_name}')]",
            f"//div[contains(@class, 'month') and contains(text(), '{month_name}')]"
        ]
        
        contract_months[month_year_str] = {
            "month_name": month_name,
            "month_num": month_num,
            "year": year,
            "xpath_options": xpath_options
        }
    
    return contract_months

contract_months = get_contract_months()

def scrape_data():
    """Scrape the data from the website and return it in JSON format"""
    global latest_data
    
    print(f"\n🚀 Scraping started at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    driver = None
    
    try:
        # Initialize the driver
        try:
            driver = get_driver()
            driver.get(url)
            print(f"Page loaded: {driver.title}")
        except Exception as browser_error:
            print(f"❌ Browser initialization error: {str(browser_error)}")
            # Return last data if available or error message
            if latest_data:
                return latest_data
            return {"error": f"Browser error: {str(browser_error)}"}
        
        # Get the date and time from the website
        market_timestamp = None
        date_time_text = None
        date_selectors = [
            "//div[contains(@class, 'date')]",
            "//div[contains(@class, 'commodity-page__date')]",
            "//span[contains(@class, 'date')]",
            "//p[contains(text(), 'As on')]",
            "//*[contains(text(), 'As on')]"
        ]
        
        for selector in date_selectors:
            try:
                date_element = WebDriverWait(driver, 5).until(
                    EC.visibility_of_element_located((By.XPATH, selector))
                )
                date_time_text = date_element.text.strip() if date_element.text else ""
                if date_time_text:
                    print(f"Found date with selector: {selector}")
                    print(f"Date text: {date_time_text}")
                    break
            except Exception as e:
                print(f"Date selector {selector} failed: {str(e)}")
                continue
        
        # Parse the date and time
        if date_time_text:
            # Remove "As on" or similar prefixes
            date_time_text = date_time_text.replace("As on", "").strip()
            
            # Try different date formats
            date_formats = [
                "%d %B, %Y | %H:%M",
                "%d %B %Y | %H:%M",
                "%d %B, %Y %H:%M",
                "%d %b, %Y | %H:%M",
                "%B %d, %Y | %H:%M"
            ]
            
            for fmt in date_formats:
                try:
                    market_timestamp = datetime.strptime(date_time_text, fmt)
                    print(f"Parsed date using format {fmt}: {market_timestamp}")
                    break
                except ValueError:
                    continue
                    
        # If we couldn't parse the date, use current time
        if not market_timestamp:
            market_timestamp = datetime.now()
            print(f"Using current time: {market_timestamp}")
        
        # Format date and time
        date_str = market_timestamp.strftime("%Y-%m-%d")
        time_str = market_timestamp.strftime("%H:%M:%S")
        timestamp_str = market_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Prepare data structure
        data = {
            "date": date_str,
            "time": time_str,
            "timestamp": timestamp_str,  # Full timestamp
            "prices": {}
        }
        
        # Get data for each contract month
        for month_key, month_info in contract_months.items():
            # Try each XPath option to find the contract element
            found = False
            
            for xpath in month_info["xpath_options"]:
                try:
                    # Find and click the contract month
                    print(f"Trying to find element for {month_key} with xpath: {xpath}")
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, xpath))
                    )
                    driver.execute_script("arguments[0].click();", element)
                    print(f"Clicked element for {month_key}")
                    time.sleep(3)  # Wait for price to update
                    found = True
                    break
                except Exception as e:
                    print(f"Failed to find/click xpath {xpath}: {str(e)}")
                    continue
            
            if not found:
                print(f"Could not locate any element for {month_key}")
                data["prices"][month_key] = {
                    "price": "N/A",
                    "site_rate_change": "N/A"
                }
                continue
            
            # Get the price - trying multiple different selectors
            price_selectors = [
                # Try specific classes
                "//div[contains(@class, 'commodity-page__value')]", 
                "//div[contains(@class, 'value')]/span", 
                "//div[contains(@class, 'value')]", 
                "//span[contains(@class, 'value')]",
                
                # Try by content type
                "//span[contains(text(), '₹')]",
                "//div[contains(text(), '₹')]",
                "//h1[contains(text(), '₹')]",
                "//h2[contains(text(), '₹')]",
                "//h3[contains(text(), '₹')]",
                "//p[contains(text(), '₹')]",
                
                # Try by structure
                "//div[contains(@class, 'price')]/parent::div",
                "//div[contains(@class, 'rate')]/parent::div"
            ]
            
            price_found = False
            for selector in price_selectors:
                try:
                    price_element = WebDriverWait(driver, 5).until(
                        EC.visibility_of_element_located((By.XPATH, selector))
                    )
                    price_text = price_element.text.strip()
                    print(f"Found price with selector: {selector}")
                    print(f"Price text: {price_text}")
                    
                    # If multiple values are in the text, extract the one with a Rupee symbol
                    if "₹" in price_text:
                        # Extract the price using a more robust approach
                        import re
                        price_match = re.search(r'₹\s*([\d,.]+)', price_text)
                        if price_match:
                            price_text = price_match.group(1)
                    
                    # Clean the price text
                    price_text = price_text.replace("₹", "").replace(",", "").strip()
                    
                    # Try to convert to float
                    try:
                        price = float(price_text)
                        price_found = True
                        print(f"Successfully parsed price: {price}")
                        break
                    except ValueError:
                        print(f"Could not convert '{price_text}' to float")
                        continue
                except Exception as e:
                    print(f"Price selector {selector} failed: {str(e)}")
                    continue
            
            if not price_found:
                print(f"Could not find price for {month_key}")
                
                # Try a fallback method - look through the whole page source
                try:
                    # Look for any elements with "₹" symbol
                    elements = driver.find_elements(By.XPATH, "//*[contains(text(), '₹')]")
                    if elements:
                        for el in elements:
                            text = el.text.strip()
                            print(f"Potential price element: {text}")
                            try:
                                import re
                                price_match = re.search(r'₹\s*([\d,.]+)', text)
                                if price_match:
                                    price_text = price_match.group(1).replace(",", "")
                                    price = float(price_text)
                                    price_found = True
                                    print(f"Fallback price found: {price}")
                                    break
                            except:
                                continue
                except Exception as fallback_err:
                    print(f"Fallback price search failed: {str(fallback_err)}")
            
            if not price_found:
                # Last resort - extract from rate change if available
                price = "N/A"
            
            # Get the rate change
            rate_change = "N/A"
            rate_selectors = [
                "//div[contains(@class, 'commodity-page__percentage')]",
                "//div[contains(@class, 'percentage')]",
                "//span[contains(@class, 'change')]",
                "//div[contains(@class, 'change')]",
                "//span[contains(text(), '%')]",
                "//div[contains(text(), '%')]"
            ]
            
            for selector in rate_selectors:
                try:
                    rate_element = WebDriverWait(driver, 3).until(
                        EC.visibility_of_element_located((By.XPATH, selector))
                    )
                    rate_change = rate_element.text.strip()
                    print(f"Found rate change with selector: {selector}")
                    print(f"Rate change text: {rate_change}")
                    
                    # Try to extract price from rate change if price is N/A
                    if price == "N/A" and "(" in rate_change and ")" in rate_change:
                        try:
                            # Parse the rate change to get the price
                            import re
                            # Something like "-5 (-2.1%)" - the absolute value is the first number
                            change_match = re.search(r'([+-]?\d+(\.\d+)?)', rate_change)
                            percent_match = re.search(r'\(([-+]?\d+(\.\d+)?)%\)', rate_change)
                            
                            if change_match and percent_match:
                                change_value = float(change_match.group(1))
                                percent = float(percent_match.group(1))
                                
                                # Calculate original price: change_value is percent% of original
                                # So original = change_value / (percent/100)
                                if percent != 0:  # Avoid division by zero
                                    calculated_price = abs(change_value / (percent/100))
                                    price = calculated_price
                                    print(f"Calculated price from rate change: {price}")
                        except Exception as calc_err:
                            print(f"Failed to calculate price from rate change: {str(calc_err)}")
                    
                    break
                except Exception as e:
                    print(f"Rate selector {selector} failed: {str(e)}")
                    continue
            
            # Add to data
            data["prices"][month_key] = {
                "price": price,
                "site_rate_change": rate_change
            }
        
        # Close the driver
        driver.quit()
        
        # Save to CSV
        save_to_csv(data)
        
        # Update the global latest_data
        latest_data = data
        
        print(f"✅ Scraping completed for timestamp: {data['timestamp']}")
        return data
        
    except Exception as e:
        print(f"❌ Error during scraping: {str(e)}")
        # If driver is still open, close it
        try:
            if driver:
                driver.quit()
        except:
            pass
        
        # Return error or latest data if available
        if latest_data:
            return latest_data
        return {"error": str(e)}

def save_to_csv(data):
    """Save the scraped data to a CSV file"""
    headers = ["Date", "Time", "Timestamp"]
    for month in contract_months:
        headers.extend([
            f"{month}_Price", 
            f"{month}_Rate_Change"
        ])
    
    row = [
        data["date"], 
        data["time"],
        data["timestamp"]
    ]
    
    for month in contract_months:
        if month in data["prices"]:
            row.extend([
                data["prices"][month].get("price", "N/A"),
                data["prices"][month].get("site_rate_change", "N/A")
            ])
        else:
            row.extend(["N/A", "N/A"])
    
    file_exists = os.path.exists(csv_filename)
    with open(csv_filename, "a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if not file_exists:
            writer.writerow(headers)
        writer.writerow(row)
    
    print(f"Data saved to {csv_filename}")

# Simple background thread that scrapes data every 10 seconds
def background_scraper():
    while True:
        try:
            scrape_data()
        except Exception as e:
            print(f"Error in background scraper: {str(e)}")
        
        time.sleep(10)  # 10-second interval as requested


@app.route("/", methods=["GET"])
def index():
    return """
    <html>
      <head>
        <title>MCX Aluminium Scraper</title>
        <style>
          body { font-family: Arial, sans-serif; margin: 40px; line-height: 1.6; }
          h1 { color: #333; }
          .container { max-width: 800px; margin: 0 auto; }
          .endpoint { background: #f4f4f4; padding: 10px; margin-bottom: 10px; border-radius: 5px; }
          code { background: #e0e0e0; padding: 2px 5px; border-radius: 3px; }
        </style>
      </head>
      <body>
        <div class="container">
          <h1>MCX Aluminium Scraper API</h1>
          <p>Welcome to the MCX Aluminium Scraper API. Use the following endpoints:</p>
          
          <div class="endpoint">
            <h3>Scrape Data</h3>
            <p><code>GET /scrape</code> - Trigger the scraping process</p>
          </div>
          
          <div class="endpoint">
            <h3>Stream Data</h3>
            <p><code>GET /stream</code> - Stream real-time data updates</p>
          </div>
          
          <div class="endpoint">
            <h3>Download CSV</h3>
            <p><code>GET /download</code> - Download scraped data as CSV</p>
          </div>
        </div>
      </body>
    </html>
    """

@app.route("/scrape", methods=["GET"])
def scrape():
    data = scrape_data()
    return jsonify(data)

@app.route("/stream")   
def stream():
    def event_stream():
        """Server-sent event generator function."""
        while True:
            yield f"data: {json.dumps(latest_data)}\n\n"
            time.sleep(10)  # Send updates every 10 seconds
    
    return Response(event_stream(), mimetype="text/event-stream")

@app.route("/download", methods=["GET"])
def download_csv():
    """Download the complete CSV file with all historical data"""
    if os.path.exists(csv_filename):
        return send_file(csv_filename, as_attachment=True)
    return jsonify({"error": "CSV file not found"}), 404

if __name__ == "__main__":
    # Perform initial data scrape
    scrape_data()
    
    # Start background scraper thread
    thread = threading.Thread(target=background_scraper, daemon=True)
    thread.start()
    
    # Run the Flask app
    app.run(debug=True, port=5002, host="0.0.0.0")
