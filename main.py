import threading
from flask import Flask, render_template, request, redirect, url_for, jsonify
from database import init_db, add_account, get_all_accounts, delete_account, get_logs, clear_logs
from scraper import run_scraper

app = Flask(__name__)

bot_running = False
bot_lock = threading.Lock()

def run_bot_thread():
    global bot_running
    try:
        run_scraper()
    finally:
        with bot_lock:
            bot_running = False

@app.route('/')
def index():
    accounts = get_all_accounts()
    logs = get_logs(limit=100)
    return render_template('index.html', accounts=accounts, logs=logs, bot_running=bot_running)

@app.route('/add', methods=['POST'])
def add():
    name = request.form.get('name', '').strip()
    mandant = request.form.get('mandant', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    api_key = request.form.get('api_key', '').strip()
    save_path = request.form.get('save_path', '').strip()
    
    if name and username and password and (api_key or save_path):
        add_account(
            name, 
            mandant if mandant else None, 
            username, 
            password, 
            api_key if api_key else None,
            save_path if save_path else None
        )
    
    return redirect(url_for('index'))

@app.route('/delete/<int:account_id>', methods=['POST'])
def delete(account_id):
    delete_account(account_id)
    return redirect(url_for('index'))

@app.route('/run', methods=['POST'])
def run():
    global bot_running
    
    with bot_lock:
        if bot_running:
            return jsonify({'status': 'error', 'message': 'Bot is already running'})
        bot_running = True
    
    thread = threading.Thread(target=run_bot_thread, daemon=True)
    thread.start()
    
    return jsonify({'status': 'success', 'message': 'Bot started'})

@app.route('/logs')
def logs():
    logs = get_logs(limit=100)
    return jsonify([dict(log) for log in logs])

@app.route('/clear_logs', methods=['POST'])
def clear():
    clear_logs()
    return redirect(url_for('index'))

@app.route('/status')
def status():
    return jsonify({'running': bot_running})

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=8080, debug=False)
