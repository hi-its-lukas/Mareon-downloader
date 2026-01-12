import sqlite3
import os
from datetime import datetime

DB_PATH = "data/app.db"

def ensure_db_folder():
    os.makedirs("data", exist_ok=True)

def get_connection():
    ensure_db_folder()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            mandant_dropdown TEXT,
            username TEXT NOT NULL,
            password TEXT NOT NULL,
            butler_api_key TEXT NOT NULL
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            rechnungs_nr TEXT PRIMARY KEY
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            level TEXT NOT NULL,
            message TEXT NOT NULL
        )
    ''')
    
    conn.commit()
    conn.close()

def add_account(name, mandant_dropdown, username, password, butler_api_key):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO accounts (name, mandant_dropdown, username, password, butler_api_key)
        VALUES (?, ?, ?, ?, ?)
    ''', (name, mandant_dropdown, username, password, butler_api_key))
    conn.commit()
    conn.close()

def get_all_accounts():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM accounts')
    accounts = cursor.fetchall()
    conn.close()
    return accounts

def delete_account(account_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM accounts WHERE id = ?', (account_id,))
    conn.commit()
    conn.close()

def is_invoice_processed(rechnungs_nr):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT 1 FROM history WHERE rechnungs_nr = ?', (rechnungs_nr,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def add_to_history(rechnungs_nr):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('INSERT OR IGNORE INTO history (rechnungs_nr) VALUES (?)', (rechnungs_nr,))
    conn.commit()
    conn.close()

def add_log(level, message):
    conn = get_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''
        INSERT INTO logs (timestamp, level, message)
        VALUES (?, ?, ?)
    ''', (timestamp, level, message))
    conn.commit()
    conn.close()

def get_logs(limit=100):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM logs ORDER BY id DESC LIMIT ?', (limit,))
    logs = cursor.fetchall()
    conn.close()
    return logs

def clear_logs():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM logs')
    conn.commit()
    conn.close()
