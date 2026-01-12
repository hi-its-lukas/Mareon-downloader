import os
import time
import glob
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from database import get_all_accounts, is_invoice_processed, add_to_history, add_log
from butler_api import upload_invoice

DOWNLOAD_DIR = os.path.abspath("downloads")
LOGIN_URL = "https://www.mareon.com/login"
INVOICES_URL = "https://www.mareon.com/portal/rechnungen"

def setup_driver():
    os.makedirs(DOWNLOAD_DIR, exist_ok=True)
    
    chrome_options = Options()
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-popup-blocking")
    
    prefs = {
        "download.default_directory": DOWNLOAD_DIR,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "plugins.always_open_pdf_externally": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        service = Service("/nix/store/chromium-chromedriver/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
    except Exception:
        try:
            service = Service()
            driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            from webdriver_manager.chrome import ChromeDriverManager
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
    
    driver.implicitly_wait(10)
    return driver

def login(driver, username, password):
    add_log("INFO", f"Attempting login for user: {username}")
    
    try:
        driver.get(LOGIN_URL)
        time.sleep(2)
        
        username_field = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "modlgn_username"))
        )
        username_field.clear()
        username_field.send_keys(username)
        
        password_field = driver.find_element(By.ID, "modlgn_passwd")
        password_field.clear()
        password_field.send_keys(password)
        
        submit_button = driver.find_element(By.NAME, "Submit")
        submit_button.click()
        
        time.sleep(3)
        
        if "login" not in driver.current_url.lower():
            add_log("INFO", f"Successfully logged in as: {username}")
            return True
        else:
            add_log("ERROR", f"Login failed for user: {username}")
            return False
            
    except TimeoutException:
        add_log("ERROR", f"Timeout during login for user: {username}")
        return False
    except Exception as e:
        add_log("ERROR", f"Login error for {username}: {str(e)}")
        return False

def switch_mandant(driver, mandant_text):
    if not mandant_text:
        return True
        
    add_log("INFO", f"Attempting to switch to mandant: {mandant_text}")
    
    try:
        time.sleep(2)
        
        dropdown_selectors = [
            "//div[contains(@class, 'dropdown')]//a",
            "//nav//div[contains(@class, 'dropdown')]",
            "//ul[contains(@class, 'navbar')]//li[contains(@class, 'dropdown')]",
            "//header//div[contains(@class, 'dropdown')]"
        ]
        
        for selector in dropdown_selectors:
            try:
                dropdowns = driver.find_elements(By.XPATH, selector)
                for dropdown in dropdowns:
                    dropdown.click()
                    time.sleep(1)
                    break
            except Exception:
                continue
        
        mandant_li = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((By.XPATH, f"//li[contains(text(), '{mandant_text}')]"))
        )
        mandant_li.click()
        
        add_log("INFO", f"Successfully switched to mandant: {mandant_text}")
        time.sleep(2)
        return True
        
    except TimeoutException:
        add_log("ERROR", f"Could not find mandant: {mandant_text}")
        return False
    except Exception as e:
        add_log("ERROR", f"Error switching mandant: {str(e)}")
        return False

def wait_for_download(existing_files, timeout=30):
    end_time = time.time() + timeout
    while time.time() < end_time:
        current_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))
        new_files = current_files - existing_files
        completed_new_files = [f for f in new_files if not f.endswith('.crdownload')]
        if completed_new_files:
            newest = max(completed_new_files, key=os.path.getctime)
            return newest
        time.sleep(1)
    return None

def cleanup_downloads():
    for f in glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")):
        try:
            os.remove(f)
        except Exception:
            pass

def process_invoices(driver, api_key):
    add_log("INFO", "Navigating to invoices page")
    
    try:
        driver.get(INVOICES_URL)
        time.sleep(3)
        
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "tbody"))
        )
        
        rows = driver.find_elements(By.CSS_SELECTOR, "tbody tr")
        add_log("INFO", f"Found {len(rows)} invoice rows")
        
        processed_count = 0
        skipped_count = 0
        
        for i, row in enumerate(rows):
            try:
                row_text = row.text
                
                invoice_match = re.search(r'S-\d+', row_text)
                if not invoice_match:
                    continue
                    
                invoice_nr = invoice_match.group()
                
                if is_invoice_processed(invoice_nr):
                    add_log("INFO", f"Skipping already processed invoice: {invoice_nr}")
                    skipped_count += 1
                    continue
                
                add_log("INFO", f"Processing invoice: {invoice_nr}")
                
                try:
                    download_link = row.find_element(By.CSS_SELECTOR, 'a[title="Rechnungsdruck"]')
                except NoSuchElementException:
                    try:
                        download_link = row.find_element(By.XPATH, './/a[contains(@title, "Rechnung")]')
                    except NoSuchElementException:
                        add_log("ERROR", f"No download link found for invoice: {invoice_nr}")
                        continue
                
                existing_files = set(glob.glob(os.path.join(DOWNLOAD_DIR, "*.pdf")))
                
                download_link.click()
                add_log("INFO", f"Clicked download for invoice: {invoice_nr}")
                
                downloaded_file = wait_for_download(existing_files)
                
                if downloaded_file:
                    add_log("INFO", f"Downloaded file: {downloaded_file}")
                    
                    if upload_invoice(downloaded_file, api_key):
                        add_to_history(invoice_nr)
                        
                        try:
                            os.remove(downloaded_file)
                            add_log("INFO", f"Deleted local file: {downloaded_file}")
                        except Exception as e:
                            add_log("ERROR", f"Could not delete file: {str(e)}")
                        
                        processed_count += 1
                    else:
                        add_log("ERROR", f"Upload failed for invoice: {invoice_nr}")
                        try:
                            os.remove(downloaded_file)
                            add_log("INFO", f"Cleaned up failed upload file: {downloaded_file}")
                        except Exception:
                            pass
                else:
                    add_log("ERROR", f"Download timeout for invoice: {invoice_nr}")
                    
            except Exception as e:
                add_log("ERROR", f"Error processing row {i}: {str(e)}")
                continue
        
        add_log("INFO", f"Completed: {processed_count} processed, {skipped_count} skipped")
        return processed_count
        
    except TimeoutException:
        add_log("ERROR", "Timeout loading invoices page")
        return 0
    except Exception as e:
        add_log("ERROR", f"Error processing invoices: {str(e)}")
        return 0

def run_scraper():
    add_log("INFO", "=== Starting Mareon Invoice Scraper ===")
    
    cleanup_downloads()
    add_log("INFO", "Cleaned up any leftover download files")
    
    accounts = get_all_accounts()
    
    if not accounts:
        add_log("ERROR", "No accounts configured. Please add an account first.")
        return
    
    add_log("INFO", f"Found {len(accounts)} account(s) to process")
    
    driver = None
    
    try:
        driver = setup_driver()
        add_log("INFO", "WebDriver initialized successfully")
        
        for account in accounts:
            account_name = account['name']
            add_log("INFO", f"--- Processing account: {account_name} ---")
            
            if login(driver, account['username'], account['password']):
                if account['mandant_dropdown']:
                    switch_mandant(driver, account['mandant_dropdown'])
                
                process_invoices(driver, account['butler_api_key'])
            else:
                add_log("ERROR", f"Skipping account due to login failure: {account_name}")
            
            driver.delete_all_cookies()
            
    except Exception as e:
        add_log("ERROR", f"Scraper error: {str(e)}")
    finally:
        if driver:
            driver.quit()
            add_log("INFO", "WebDriver closed")
    
    add_log("INFO", "=== Scraper run completed ===")
