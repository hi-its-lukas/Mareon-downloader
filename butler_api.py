import requests
import os
from database import add_log

BUTLER_API_URL = "https://api.buchhaltungsbutler.de/v1/documents"

def upload_invoice(filepath, api_key):
    if not os.path.exists(filepath):
        add_log("ERROR", f"File not found: {filepath}")
        return False
    
    try:
        filename = os.path.basename(filepath)
        
        with open(filepath, 'rb') as f:
            files = {
                'file': (filename, f, 'application/pdf')
            }
            headers = {
                'Authorization': f'Bearer {api_key}'
            }
            
            add_log("INFO", f"Uploading invoice to Buchhaltungsbutler: {filename}")
            
            response = requests.post(
                BUTLER_API_URL,
                headers=headers,
                files=files,
                timeout=60
            )
            
            if response.status_code in [200, 201]:
                add_log("INFO", f"Successfully uploaded invoice: {filename}")
                return True
            else:
                add_log("ERROR", f"Failed to upload invoice: {filename}. Status: {response.status_code}, Response: {response.text}")
                return False
                
    except requests.exceptions.RequestException as e:
        add_log("ERROR", f"Network error uploading invoice: {str(e)}")
        return False
    except Exception as e:
        add_log("ERROR", f"Error uploading invoice: {str(e)}")
        return False
