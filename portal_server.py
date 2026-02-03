#!/usr/bin/env python3
"""
NEXUS Client Portal Server
==========================
Central server for client authentication, updates, and marketplace.
Runs on Zultan (192.168.1.152:5000)

Patent Pending - Kevin Caracozza
"""

from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import sqlite3
import hashlib
import uuid
import os
import json
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
CORS(app)

# Configuration
DB_PATH = "portal.db"
UPDATES_DIR = "updates"
CURRENT_VERSION = "3.0.1"
SECRET_KEY = os.environ.get("NEXUS_SECRET", "nexus-dev-key-change-in-prod")

# =============================================================================
# DATABASE SETUP
# =============================================================================

def init_db():
    """Initialize database tables"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Users table
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        shop_name TEXT,
        station_api_key TEXT UNIQUE,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_admin INTEGER DEFAULT 0,
        subscription_tier TEXT DEFAULT 'free',
        subscription_expires TIMESTAMP
    )''')

    # Licenses table
    c.execute('''CREATE TABLE IF NOT EXISTS licenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_key TEXT UNIQUE NOT NULL,
        user_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP,
        is_active INTEGER DEFAULT 1,
        max_activations INTEGER DEFAULT 3,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Client installations (activations)
    c.execute('''CREATE TABLE IF NOT EXISTS clients (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        license_id INTEGER NOT NULL,
        machine_id TEXT NOT NULL,
        machine_name TEXT,
        ip_address TEXT,
        version TEXT,
        last_seen TIMESTAMP,
        first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (license_id) REFERENCES licenses(id),
        UNIQUE(license_id, machine_id)
    )''')

    # Versions table
    c.execute('''CREATE TABLE IF NOT EXISTS versions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        version TEXT UNIQUE NOT NULL,
        release_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        changelog TEXT,
        download_url TEXT,
        file_path TEXT,
        is_mandatory INTEGER DEFAULT 0,
        min_version TEXT
    )''')

    # Seller wallets
    c.execute('''CREATE TABLE IF NOT EXISTS wallets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        balance REAL DEFAULT 0.00,
        pending_balance REAL DEFAULT 0.00,
        total_earned REAL DEFAULT 0.00,
        total_withdrawn REAL DEFAULT 0.00,
        payout_email TEXT,
        payout_method TEXT DEFAULT 'paypal',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )''')

    # Wallet transactions
    c.execute('''CREATE TABLE IF NOT EXISTS wallet_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        wallet_id INTEGER NOT NULL,
        type TEXT NOT NULL,
        amount REAL NOT NULL,
        description TEXT,
        order_id TEXT,
        status TEXT DEFAULT 'completed',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (wallet_id) REFERENCES wallets(id)
    )''')

    # Audit log
    c.execute('''CREATE TABLE IF NOT EXISTS audit_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        user_id INTEGER,
        client_id INTEGER,
        action TEXT,
        details TEXT
    )''')

    conn.commit()
    conn.close()

    # Create updates directory
    os.makedirs(UPDATES_DIR, exist_ok=True)

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    """Hash password with salt"""
    return hashlib.sha256((password + SECRET_KEY).encode()).hexdigest()

def generate_license_key():
    """Generate unique license key"""
    return f"NEXUS-{uuid.uuid4().hex[:8].upper()}-{uuid.uuid4().hex[:8].upper()}"

def generate_station_api_key():
    """Generate unique station API key for marketplace integration"""
    return f"nxs_{uuid.uuid4().hex}"

def get_machine_id():
    """Generate machine ID from request"""
    return hashlib.md5(request.remote_addr.encode()).hexdigest()[:16]

# =============================================================================
# AUTH DECORATORS
# =============================================================================

def require_license(f):
    """Decorator to require valid license"""
    @wraps(f)
    def decorated(*args, **kwargs):
        license_key = request.headers.get('X-License-Key')
        if not license_key:
            return jsonify({'error': 'License key required'}), 401

        conn = get_db()
        license = conn.execute(
            'SELECT * FROM licenses WHERE license_key = ? AND is_active = 1',
            (license_key,)
        ).fetchone()
        conn.close()

        if not license:
            return jsonify({'error': 'Invalid license'}), 401

        if license['expires_at'] and datetime.fromisoformat(license['expires_at']) < datetime.now():
            return jsonify({'error': 'License expired'}), 401

        request.license = dict(license)
        return f(*args, **kwargs)
    return decorated

def require_admin(f):
    """Decorator to require admin access"""
    @wraps(f)
    def decorated(*args, **kwargs):
        admin_key = request.headers.get('X-Admin-Key')
        if admin_key != SECRET_KEY:
            return jsonify({'error': 'Admin access required'}), 403
        return f(*args, **kwargs)
    return decorated

# =============================================================================
# AUTH ENDPOINTS
# =============================================================================

@app.route('/api/auth/register', methods=['POST'])
def register():
    """Register new user"""
    data = request.json
    email = data.get('email')
    password = data.get('password')
    shop_name = data.get('shop_name', '')

    if not email or not password:
        return jsonify({'error': 'Email and password required'}), 400

    conn = get_db()
    try:
        # Create user with station API key
        c = conn.cursor()
        station_api_key = generate_station_api_key()
        c.execute(
            'INSERT INTO users (email, password_hash, shop_name, station_api_key) VALUES (?, ?, ?, ?)',
            (email, hash_password(password), shop_name, station_api_key)
        )
        user_id = c.lastrowid

        # Generate license
        license_key = generate_license_key()
        c.execute(
            'INSERT INTO licenses (license_key, user_id) VALUES (?, ?)',
            (license_key, user_id)
        )

        # Create seller wallet
        c.execute(
            'INSERT INTO wallets (user_id, payout_email) VALUES (?, ?)',
            (user_id, email)
        )

        conn.commit()

        return jsonify({
            'success': True,
            'user_id': user_id,
            'license_key': license_key,
            'station_api_key': station_api_key,
            'message': 'Registration successful'
        })
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Email already registered'}), 409
    finally:
        conn.close()

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Login and get license key"""
    data = request.json
    email = data.get('email')
    password = data.get('password')

    conn = get_db()
    user = conn.execute(
        'SELECT * FROM users WHERE email = ? AND password_hash = ?',
        (email, hash_password(password))
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({'error': 'Invalid credentials'}), 401

    # Get license
    license = conn.execute(
        'SELECT * FROM licenses WHERE user_id = ? AND is_active = 1',
        (user['id'],)
    ).fetchone()
    conn.close()

    return jsonify({
        'success': True,
        'user_id': user['id'],
        'email': user['email'],
        'shop_name': user['shop_name'],
        'license_key': license['license_key'] if license else None,
        'station_api_key': user['station_api_key'],
        'subscription_tier': user['subscription_tier'],
        'is_admin': bool(user['is_admin'])
    })

@app.route('/api/auth/validate', methods=['POST'])
@require_license
def validate_license():
    """Validate license and register client"""
    data = request.json or {}
    machine_id = data.get('machine_id', get_machine_id())
    machine_name = data.get('machine_name', 'Unknown')
    version = data.get('version', 'Unknown')

    conn = get_db()

    # Check activation count
    activations = conn.execute(
        'SELECT COUNT(*) as count FROM clients WHERE license_id = ?',
        (request.license['id'],)
    ).fetchone()['count']

    max_activations = request.license['max_activations']

    # Check if this machine already registered
    existing = conn.execute(
        'SELECT * FROM clients WHERE license_id = ? AND machine_id = ?',
        (request.license['id'], machine_id)
    ).fetchone()

    if not existing and activations >= max_activations:
        conn.close()
        return jsonify({
            'valid': False,
            'error': f'Maximum activations ({max_activations}) reached'
        }), 403

    # Register/update client
    if existing:
        conn.execute(
            '''UPDATE clients SET
               machine_name = ?, ip_address = ?, version = ?, last_seen = CURRENT_TIMESTAMP
               WHERE id = ?''',
            (machine_name, request.remote_addr, version, existing['id'])
        )
        client_id = existing['id']
    else:
        c = conn.cursor()
        c.execute(
            '''INSERT INTO clients (license_id, machine_id, machine_name, ip_address, version, last_seen)
               VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)''',
            (request.license['id'], machine_id, machine_name, request.remote_addr, version)
        )
        client_id = c.lastrowid

    conn.commit()
    conn.close()

    return jsonify({
        'valid': True,
        'client_id': client_id,
        'activations_used': activations + (0 if existing else 1),
        'max_activations': max_activations
    })

@app.route('/api/auth/station_key', methods=['GET'])
@require_license
def get_station_key():
    """Get station API key for marketplace integration"""
    conn = get_db()
    user = conn.execute(
        'SELECT station_api_key, shop_name FROM users WHERE id = (SELECT user_id FROM licenses WHERE id = ?)',
        (request.license['id'],)
    ).fetchone()
    conn.close()

    if not user:
        return jsonify({'error': 'User not found'}), 404

    return jsonify({
        'station_api_key': user['station_api_key'],
        'shop_name': user['shop_name']
    })

@app.route('/api/auth/station_key/regenerate', methods=['POST'])
@require_license
def regenerate_station_key():
    """Regenerate station API key"""
    conn = get_db()
    new_key = generate_station_api_key()
    conn.execute(
        'UPDATE users SET station_api_key = ? WHERE id = (SELECT user_id FROM licenses WHERE id = ?)',
        (new_key, request.license['id'])
    )
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'station_api_key': new_key
    })

# =============================================================================
# WALLET ENDPOINTS
# =============================================================================

@app.route('/api/wallet', methods=['GET'])
@require_license
def get_wallet():
    """Get seller wallet info"""
    conn = get_db()
    user_id = conn.execute(
        'SELECT user_id FROM licenses WHERE id = ?',
        (request.license['id'],)
    ).fetchone()['user_id']

    wallet = conn.execute(
        'SELECT * FROM wallets WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if not wallet:
        # Create wallet if missing
        conn.execute(
            'INSERT INTO wallets (user_id) VALUES (?)',
            (user_id,)
        )
        conn.commit()
        wallet = conn.execute(
            'SELECT * FROM wallets WHERE user_id = ?',
            (user_id,)
        ).fetchone()

    # Get recent transactions
    transactions = conn.execute(
        '''SELECT * FROM wallet_transactions
           WHERE wallet_id = ?
           ORDER BY created_at DESC LIMIT 20''',
        (wallet['id'],)
    ).fetchall()
    conn.close()

    return jsonify({
        'balance': wallet['balance'],
        'pending_balance': wallet['pending_balance'],
        'total_earned': wallet['total_earned'],
        'total_withdrawn': wallet['total_withdrawn'],
        'payout_email': wallet['payout_email'],
        'payout_method': wallet['payout_method'],
        'transactions': [dict(t) for t in transactions]
    })

@app.route('/api/wallet/payout', methods=['POST'])
@require_license
def update_payout_settings():
    """Update payout settings"""
    data = request.json
    payout_email = data.get('payout_email')
    payout_method = data.get('payout_method', 'paypal')

    conn = get_db()
    user_id = conn.execute(
        'SELECT user_id FROM licenses WHERE id = ?',
        (request.license['id'],)
    ).fetchone()['user_id']

    conn.execute(
        '''UPDATE wallets SET payout_email = ?, payout_method = ?, updated_at = CURRENT_TIMESTAMP
           WHERE user_id = ?''',
        (payout_email, payout_method, user_id)
    )
    conn.commit()
    conn.close()

    return jsonify({'success': True})

@app.route('/api/wallet/withdraw', methods=['POST'])
@require_license
def request_withdrawal():
    """Request withdrawal from wallet"""
    data = request.json
    amount = data.get('amount', 0)

    if amount <= 0:
        return jsonify({'error': 'Invalid amount'}), 400

    conn = get_db()
    user_id = conn.execute(
        'SELECT user_id FROM licenses WHERE id = ?',
        (request.license['id'],)
    ).fetchone()['user_id']

    wallet = conn.execute(
        'SELECT * FROM wallets WHERE user_id = ?',
        (user_id,)
    ).fetchone()

    if not wallet or wallet['balance'] < amount:
        conn.close()
        return jsonify({'error': 'Insufficient balance'}), 400

    # Deduct from balance, add to pending withdrawal
    new_balance = wallet['balance'] - amount
    conn.execute(
        '''UPDATE wallets SET balance = ?, updated_at = CURRENT_TIMESTAMP
           WHERE user_id = ?''',
        (new_balance, user_id)
    )

    # Record transaction
    conn.execute(
        '''INSERT INTO wallet_transactions (wallet_id, type, amount, description, status)
           VALUES (?, 'withdrawal', ?, 'Withdrawal request', 'pending')''',
        (wallet['id'], -amount)
    )
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'new_balance': new_balance,
        'withdrawal_amount': amount
    })

@app.route('/api/wallet/credit', methods=['POST'])
@require_admin
def credit_wallet():
    """Admin: Credit a seller's wallet (for sales)"""
    data = request.json
    station_api_key = data.get('station_api_key')
    amount = data.get('amount', 0)
    order_id = data.get('order_id')
    description = data.get('description', 'Sale credit')

    if not station_api_key or amount <= 0:
        return jsonify({'error': 'Invalid request'}), 400

    conn = get_db()
    user = conn.execute(
        'SELECT id FROM users WHERE station_api_key = ?',
        (station_api_key,)
    ).fetchone()

    if not user:
        conn.close()
        return jsonify({'error': 'Seller not found'}), 404

    wallet = conn.execute(
        'SELECT * FROM wallets WHERE user_id = ?',
        (user['id'],)
    ).fetchone()

    if not wallet:
        conn.close()
        return jsonify({'error': 'Wallet not found'}), 404

    # Add to balance
    new_balance = wallet['balance'] + amount
    new_total = wallet['total_earned'] + amount
    conn.execute(
        '''UPDATE wallets SET balance = ?, total_earned = ?, updated_at = CURRENT_TIMESTAMP
           WHERE id = ?''',
        (new_balance, new_total, wallet['id'])
    )

    # Record transaction
    conn.execute(
        '''INSERT INTO wallet_transactions (wallet_id, type, amount, description, order_id)
           VALUES (?, 'credit', ?, ?, ?)''',
        (wallet['id'], amount, description, order_id)
    )
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'new_balance': new_balance
    })

# =============================================================================
# UPDATE ENDPOINTS
# =============================================================================

@app.route('/api/updates/check', methods=['GET'])
@require_license
def check_updates():
    """Check for available updates"""
    current = request.args.get('version', '0.0.0')

    conn = get_db()
    latest = conn.execute(
        'SELECT * FROM versions ORDER BY release_date DESC LIMIT 1'
    ).fetchone()
    conn.close()

    if not latest:
        return jsonify({
            'update_available': False,
            'current_version': current,
            'latest_version': CURRENT_VERSION
        })

    update_available = latest['version'] > current

    return jsonify({
        'update_available': update_available,
        'current_version': current,
        'latest_version': latest['version'],
        'changelog': latest['changelog'] if update_available else None,
        'is_mandatory': bool(latest['is_mandatory']) if update_available else False,
        'download_url': f'/api/updates/download/{latest["version"]}' if update_available else None
    })

@app.route('/api/updates/download/<version>', methods=['GET'])
@require_license
def download_update(version):
    """Download specific version"""
    conn = get_db()
    ver = conn.execute(
        'SELECT * FROM versions WHERE version = ?', (version,)
    ).fetchone()
    conn.close()

    if not ver or not ver['file_path']:
        return jsonify({'error': 'Version not found'}), 404

    file_path = os.path.join(UPDATES_DIR, ver['file_path'])
    if not os.path.exists(file_path):
        return jsonify({'error': 'Update file not found'}), 404

    return send_file(file_path, as_attachment=True)

@app.route('/api/updates/changelog', methods=['GET'])
def get_changelog():
    """Get changelog for all versions"""
    conn = get_db()
    versions = conn.execute(
        'SELECT version, release_date, changelog FROM versions ORDER BY release_date DESC LIMIT 10'
    ).fetchall()
    conn.close()

    return jsonify({
        'versions': [dict(v) for v in versions]
    })

# =============================================================================
# ADMIN ENDPOINTS
# =============================================================================

@app.route('/api/admin/clients', methods=['GET'])
@require_admin
def list_clients():
    """List all registered clients"""
    conn = get_db()
    clients = conn.execute('''
        SELECT c.*, l.license_key, u.email, u.shop_name
        FROM clients c
        JOIN licenses l ON c.license_id = l.id
        JOIN users u ON l.user_id = u.id
        ORDER BY c.last_seen DESC
    ''').fetchall()
    conn.close()

    return jsonify({
        'clients': [dict(c) for c in clients]
    })

@app.route('/api/admin/users', methods=['GET'])
@require_admin
def list_users():
    """List all users"""
    conn = get_db()
    users = conn.execute('''
        SELECT u.*, COUNT(c.id) as client_count
        FROM users u
        LEFT JOIN licenses l ON u.id = l.user_id
        LEFT JOIN clients c ON l.id = c.license_id
        GROUP BY u.id
        ORDER BY u.created_at DESC
    ''').fetchall()
    conn.close()

    return jsonify({
        'users': [dict(u) for u in users]
    })

@app.route('/api/admin/versions', methods=['POST'])
@require_admin
def add_version():
    """Add new version"""
    data = request.json
    version = data.get('version')
    changelog = data.get('changelog', '')
    is_mandatory = data.get('is_mandatory', False)
    file_path = data.get('file_path')

    if not version:
        return jsonify({'error': 'Version required'}), 400

    conn = get_db()
    try:
        conn.execute(
            '''INSERT INTO versions (version, changelog, is_mandatory, file_path)
               VALUES (?, ?, ?, ?)''',
            (version, changelog, int(is_mandatory), file_path)
        )
        conn.commit()
        return jsonify({'success': True, 'version': version})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Version already exists'}), 409
    finally:
        conn.close()

@app.route('/api/admin/push_update', methods=['POST'])
@require_admin
def push_update():
    """Push update notification to specific clients"""
    data = request.json
    client_ids = data.get('client_ids', [])
    version = data.get('version')

    # In a real system, this would send push notifications
    # For now, clients poll for updates

    conn = get_db()
    for client_id in client_ids:
        conn.execute(
            'INSERT INTO audit_log (client_id, action, details) VALUES (?, ?, ?)',
            (client_id, 'push_update', json.dumps({'version': version}))
        )
    conn.commit()
    conn.close()

    return jsonify({
        'success': True,
        'message': f'Update {version} pushed to {len(client_ids)} clients'
    })

@app.route('/api/admin/stats', methods=['GET'])
@require_admin
def get_stats():
    """Get portal statistics"""
    conn = get_db()

    stats = {
        'total_users': conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_clients': conn.execute('SELECT COUNT(*) FROM clients').fetchone()[0],
        'active_today': conn.execute(
            "SELECT COUNT(*) FROM clients WHERE last_seen > datetime('now', '-1 day')"
        ).fetchone()[0],
        'total_licenses': conn.execute('SELECT COUNT(*) FROM licenses WHERE is_active = 1').fetchone()[0],
    }

    # Version distribution
    versions = conn.execute('''
        SELECT version, COUNT(*) as count
        FROM clients
        GROUP BY version
        ORDER BY count DESC
    ''').fetchall()
    stats['version_distribution'] = {v['version']: v['count'] for v in versions}

    conn.close()
    return jsonify(stats)

# =============================================================================
# STATIC PAGES
# =============================================================================

@app.route('/kickstarter')
def kickstarter_page():
    """Serve the Kickstarter landing page"""
    return send_from_directory('.', 'kickstarter.html')

# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'version': CURRENT_VERSION,
        'timestamp': datetime.now().isoformat()
    })

# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 50)
    print("NEXUS Client Portal Server")
    print("=" * 50)

    init_db()
    print(f"Database initialized: {DB_PATH}")
    print(f"Updates directory: {UPDATES_DIR}")
    print(f"Current version: {CURRENT_VERSION}")
    print()
    print("Starting server on 0.0.0.0:5000")

    app.run(host='0.0.0.0', port=5000, debug=True)
