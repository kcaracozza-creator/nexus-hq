#!/usr/bin/env python3
"""
███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗    ██╗  ██╗ ██████╗ 
████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝    ██║  ██║██╔═══██╗
██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗    ███████║██║   ██║
██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║    ██╔══██║██║▄▄ ██║
██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝███████║    ██║  ██║╚██████╔╝
╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚══════╝    ╚═╝  ╚═╝ ╚══▀▀═╝ 
                                                                 
THE MOTHERSHIP - Central Command for All NEXUS Deployments
==========================================================

This is a STANDALONE program - completely separate from client NEXUS.

Features:
- Client Registry: Track all shops using NEXUS
- Revenue Dashboard: Sales volume + NEXUS fees
- Phone-Home API: Clients report sales here
- Network Analytics: Aggregate data across all clients
- Grading Oversight: AI accuracy monitoring

Patent Claims Supported:
- Network effects (Claim 47-52)
- Grading oversight (Claim 67-73)  
- Universal lifecycle management (Claim 1-5)

Author: Kevin Caracozza / NEXUS Team
"""

from flask import Flask, jsonify, request, render_template_string, send_from_directory
from flask_cors import CORS
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
import uuid
import json

# ============================================
# APP SETUP
# ============================================

app = Flask(__name__)
CORS(app)

DB_PATH = Path(__file__).parent / 'data' / 'nexus_hq.db'
DB_PATH.parent.mkdir(exist_ok=True)

# ============================================
# SUBSCRIPTION TIERS
# ============================================

TIERS = {
    'starter':      {'name': 'Starter',           'price': 29,  'commission': 8.0},
    'professional': {'name': 'Professional',      'price': 79,  'commission': 6.0},
    'enterprise':   {'name': 'Enterprise',        'price': 199, 'commission': 4.0},
    'founders':     {'name': "Founder's Edition", 'price': 0,   'commission': 5.0},
}

# ============================================
# DATABASE
# ============================================

def get_db():
    """Get database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initialize HQ database"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS clients (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            api_key TEXT UNIQUE,
            subscription_tier TEXT DEFAULT 'starter',
            commission_rate REAL DEFAULT 8.0,
            monthly_fee REAL DEFAULT 29.0,
            status TEXT DEFAULT 'active',
            created_at TEXT,
            last_seen TEXT,
            location TEXT,
            contact_phone TEXT,
            notes TEXT
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS sales (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            deck_name TEXT,
            format TEXT,
            card_count INTEGER,
            sale_value REAL,
            nexus_fee REAL,
            client_keeps REAL,
            sold_at TEXT,
            cards_json TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS scans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id TEXT,
            card_name TEXT,
            set_code TEXT,
            rarity TEXT,
            price REAL,
            scanned_at TEXT,
            ai_confidence REAL,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS grading_disputes (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            card_name TEXT,
            ai_grade TEXT,
            disputed_grade TEXT,
            resolution TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT,
            resolved_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    # Subscription billing history
    c.execute('''
        CREATE TABLE IF NOT EXISTS subscription_invoices (
            id TEXT PRIMARY KEY,
            client_id TEXT,
            tier TEXT,
            amount REAL,
            period_start TEXT,
            period_end TEXT,
            status TEXT DEFAULT 'pending',
            paid_at TEXT,
            payment_method TEXT,
            stripe_invoice_id TEXT,
            created_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id)
        )
    ''')
    
    # Add billing columns to clients if not exist
    try:
        c.execute('ALTER TABLE clients ADD COLUMN billing_email TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE clients ADD COLUMN stripe_customer_id TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE clients ADD COLUMN subscription_start TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE clients ADD COLUMN next_billing_date TEXT')
    except:
        pass
    try:
        c.execute('ALTER TABLE clients ADD COLUMN billing_status TEXT DEFAULT "active"')
    except:
        pass
    
    conn.commit()
    conn.close()
    print("[OK] NEXUS HQ Database initialized")

init_db()


# ============================================
# HELPER FUNCTIONS
# ============================================

def generate_api_key():
    """Generate unique API key for client"""
    return f"nxs_{uuid.uuid4().hex[:24]}"

def get_commission_rate(tier):
    """Get commission rate for a tier"""
    return TIERS.get(tier, TIERS['starter'])['commission']

def get_monthly_fee(tier):
    """Get monthly subscription fee for a tier"""
    return TIERS.get(tier, TIERS['starter'])['price']

# ============================================
# CLIENT MANAGEMENT
# ============================================

def register_client(name, email, tier='starter', location='', phone='', notes=''):
    """Register a new NEXUS client (shop)"""
    conn = get_db()
    c = conn.cursor()
    
    client_id = str(uuid.uuid4())[:8].upper()
    api_key = generate_api_key()
    commission = get_commission_rate(tier)
    monthly_fee = get_monthly_fee(tier)
    
    try:
        c.execute('''
            INSERT INTO clients (id, name, email, api_key, subscription_tier, 
                                commission_rate, monthly_fee, created_at, last_seen, 
                                location, contact_phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (client_id, name, email, api_key, tier, commission, monthly_fee,
              datetime.now().isoformat(), datetime.now().isoformat(),
              location, phone, notes))
        conn.commit()
        conn.close()
        return {
            'success': True,
            'client_id': client_id, 
            'api_key': api_key, 
            'tier': tier, 
            'commission': commission,
            'monthly_fee': monthly_fee
        }
    except sqlite3.IntegrityError as e:
        conn.close()
        return {'success': False, 'error': str(e)}

def get_client_by_api_key(api_key):
    """Authenticate client by API key"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM clients WHERE api_key = ? AND status = "active"', (api_key,))
    row = c.fetchone()
    conn.close()
    
    if row:
        # Update last seen
        update_last_seen(row['id'])
        return dict(row)
    return None

def update_last_seen(client_id):
    """Update client's last seen timestamp"""
    conn = get_db()
    c = conn.cursor()
    c.execute('UPDATE clients SET last_seen = ? WHERE id = ?',
              (datetime.now().isoformat(), client_id))
    conn.commit()
    conn.close()

def get_all_clients():
    """Get all registered clients"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM clients ORDER BY created_at DESC')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

# ============================================
# SALES TRACKING (PHONE HOME)
# ============================================

def record_sale(client_id, deck_name, format, card_count, sale_value, cards_json=''):
    """Record a sale reported by a client"""
    conn = get_db()
    c = conn.cursor()
    
    # Get client's commission rate
    c.execute('SELECT commission_rate FROM clients WHERE id = ?', (client_id,))
    row = c.fetchone()
    commission_rate = row['commission_rate'] if row else 8.0
    
    # Calculate NEXUS fee
    nexus_fee = round(sale_value * (commission_rate / 100), 2)
    client_keeps = round(sale_value - nexus_fee, 2)
    
    sale_id = f"SALE-{uuid.uuid4().hex[:8].upper()}"
    
    c.execute('''
        INSERT INTO sales (id, client_id, deck_name, format, card_count, 
                          sale_value, nexus_fee, client_keeps, sold_at, cards_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (sale_id, client_id, deck_name, format, card_count, sale_value,
          nexus_fee, client_keeps, datetime.now().isoformat(), cards_json))
    
    conn.commit()
    conn.close()
    
    return {
        'sale_id': sale_id,
        'sale_value': sale_value,
        'nexus_fee': nexus_fee,
        'client_keeps': client_keeps,
        'commission_rate': commission_rate
    }

def record_scan(client_id, card_name, set_code, rarity='', price=0, confidence=0):
    """Record a card scan from a client"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        INSERT INTO scans (client_id, card_name, set_code, rarity, price, scanned_at, ai_confidence)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (client_id, card_name, set_code, rarity, price, datetime.now().isoformat(), confidence))
    conn.commit()
    conn.close()


# ============================================
# SUBSCRIPTION MANAGEMENT
# ============================================

def create_invoice(client_id, tier=None):
    """Create a subscription invoice for a client"""
    conn = get_db()
    c = conn.cursor()
    
    # Get client info
    c.execute('SELECT subscription_tier, monthly_fee FROM clients WHERE id = ?', (client_id,))
    row = c.fetchone()
    if not row:
        conn.close()
        return None
    
    tier = tier or row['subscription_tier']
    amount = TIERS.get(tier, TIERS['starter'])['price']
    
    invoice_id = f"INV-{uuid.uuid4().hex[:8].upper()}"
    period_start = datetime.now()
    period_end = period_start + timedelta(days=30)
    
    c.execute('''
        INSERT INTO subscription_invoices 
        (id, client_id, tier, amount, period_start, period_end, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', ?)
    ''', (invoice_id, client_id, tier, amount, period_start.isoformat(), 
          period_end.isoformat(), datetime.now().isoformat()))
    
    # Update client's next billing date
    c.execute('UPDATE clients SET next_billing_date = ? WHERE id = ?',
              (period_end.isoformat(), client_id))
    
    conn.commit()
    conn.close()
    
    return {
        'invoice_id': invoice_id,
        'client_id': client_id,
        'tier': tier,
        'amount': amount,
        'period_start': period_start.isoformat(),
        'period_end': period_end.isoformat(),
        'status': 'pending'
    }

def mark_invoice_paid(invoice_id, payment_method='manual'):
    """Mark an invoice as paid"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        UPDATE subscription_invoices 
        SET status = 'paid', paid_at = ?, payment_method = ?
        WHERE id = ?
    ''', (datetime.now().isoformat(), payment_method, invoice_id))
    
    conn.commit()
    conn.close()
    return True

def get_client_invoices(client_id):
    """Get all invoices for a client"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM subscription_invoices WHERE client_id = ? ORDER BY created_at DESC', (client_id,))
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_pending_invoices():
    """Get all unpaid invoices"""
    conn = get_db()
    c = conn.cursor()
    c.execute('''
        SELECT i.*, c.name as client_name, c.email 
        FROM subscription_invoices i
        JOIN clients c ON i.client_id = c.id
        WHERE i.status = 'pending'
        ORDER BY i.created_at
    ''')
    rows = c.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def get_subscription_revenue():
    """Get subscription revenue stats"""
    conn = get_db()
    c = conn.cursor()
    
    # MRR from active clients
    c.execute('SELECT COALESCE(SUM(monthly_fee), 0) as mrr FROM clients WHERE status = "active"')
    mrr = c.fetchone()['mrr']
    
    # Total collected this month
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
    c.execute('''
        SELECT COALESCE(SUM(amount), 0) as collected 
        FROM subscription_invoices 
        WHERE status = 'paid' AND paid_at >= ?
    ''', (month_start,))
    month_collected = c.fetchone()['collected']
    
    # Total collected all time
    c.execute('SELECT COALESCE(SUM(amount), 0) as total FROM subscription_invoices WHERE status = "paid"')
    total_collected = c.fetchone()['total']
    
    # Pending invoices
    c.execute('SELECT COUNT(*) as count, COALESCE(SUM(amount), 0) as amount FROM subscription_invoices WHERE status = "pending"')
    row = c.fetchone()
    pending_count = row['count']
    pending_amount = row['amount']
    
    # By tier breakdown
    c.execute('''
        SELECT subscription_tier, COUNT(*) as count, SUM(monthly_fee) as revenue
        FROM clients WHERE status = 'active'
        GROUP BY subscription_tier
    ''')
    tier_breakdown = [dict(row) for row in c.fetchall()]
    
    conn.close()
    
    return {
        'mrr': round(mrr, 2),
        'month_collected': round(month_collected, 2),
        'total_collected': round(total_collected, 2),
        'pending_invoices': pending_count,
        'pending_amount': round(pending_amount, 2),
        'tier_breakdown': tier_breakdown
    }

def change_client_tier(client_id, new_tier):
    """Change a client's subscription tier"""
    if new_tier not in TIERS:
        return {'success': False, 'error': 'Invalid tier'}
    
    conn = get_db()
    c = conn.cursor()
    
    tier_info = TIERS[new_tier]
    c.execute('''
        UPDATE clients 
        SET subscription_tier = ?, commission_rate = ?, monthly_fee = ?
        WHERE id = ?
    ''', (new_tier, tier_info['commission'], tier_info['price'], client_id))
    
    conn.commit()
    conn.close()
    
    return {
        'success': True,
        'new_tier': new_tier,
        'commission_rate': tier_info['commission'],
        'monthly_fee': tier_info['price']
    }

def generate_monthly_invoices():
    """Generate invoices for all clients due for billing"""
    conn = get_db()
    c = conn.cursor()
    
    # Find clients whose billing is due (next_billing_date is past or null)
    today = datetime.now().isoformat()
    c.execute('''
        SELECT id FROM clients 
        WHERE status = 'active' 
        AND monthly_fee > 0
        AND (next_billing_date IS NULL OR next_billing_date <= ?)
    ''', (today,))
    
    clients_due = c.fetchall()
    conn.close()
    
    invoices_created = []
    for row in clients_due:
        invoice = create_invoice(row['id'])
        if invoice:
            invoices_created.append(invoice)
    
    return invoices_created


# ============================================
# ANALYTICS & DASHBOARD
# ============================================

def get_dashboard_stats():
    """Get stats for HQ dashboard"""
    conn = get_db()
    c = conn.cursor()
    
    # Total clients
    c.execute('SELECT COUNT(*) as count FROM clients WHERE status = "active"')
    total_clients = c.fetchone()['count']
    
    # Total sales
    c.execute('SELECT COUNT(*) as count, COALESCE(SUM(sale_value), 0) as volume, COALESCE(SUM(nexus_fee), 0) as revenue FROM sales')
    row = c.fetchone()
    total_sales = row['count']
    total_volume = row['volume']
    total_revenue = row['revenue']
    
    # This month
    month_start = datetime.now().replace(day=1, hour=0, minute=0, second=0).isoformat()
    c.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(sale_value), 0) as volume, COALESCE(SUM(nexus_fee), 0) as revenue 
        FROM sales WHERE sold_at >= ?
    ''', (month_start,))
    row = c.fetchone()
    month_sales = row['count']
    month_volume = row['volume']
    month_revenue = row['revenue']
    
    # Today
    today_start = datetime.now().replace(hour=0, minute=0, second=0).isoformat()
    c.execute('''
        SELECT COUNT(*) as count, COALESCE(SUM(sale_value), 0) as volume, COALESCE(SUM(nexus_fee), 0) as revenue 
        FROM sales WHERE sold_at >= ?
    ''', (today_start,))
    row = c.fetchone()
    today_sales = row['count']
    today_volume = row['volume']
    today_revenue = row['revenue']
    
    # Network stats
    c.execute('SELECT COUNT(*) as count FROM scans')
    total_scans = c.fetchone()['count']
    
    c.execute('SELECT COUNT(*) as count FROM grading_disputes WHERE status = "pending"')
    pending_disputes = c.fetchone()['count']
    
    # Monthly subscription revenue
    c.execute('SELECT COALESCE(SUM(monthly_fee), 0) as mrr FROM clients WHERE status = "active"')
    mrr = c.fetchone()['mrr']
    
    conn.close()
    
    return {
        'clients': {'total': total_clients, 'active': total_clients},
        'sales': {'total': total_sales, 'today': today_sales, 'this_month': month_sales},
        'volume': {'total': round(total_volume, 2), 'today': round(today_volume, 2), 'this_month': round(month_volume, 2)},
        'revenue': {
            'total_fees': round(total_revenue, 2), 
            'today_fees': round(today_revenue, 2), 
            'month_fees': round(month_revenue, 2),
            'mrr': round(mrr, 2)
        },
        'network': {'total_scans': total_scans, 'pending_disputes': pending_disputes}
    }

def get_client_leaderboard():
    """Get top clients by sales volume"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        SELECT c.id, c.name, c.subscription_tier, c.commission_rate, c.location, c.last_seen,
               COUNT(s.id) as sale_count,
               COALESCE(SUM(s.sale_value), 0) as total_volume,
               COALESCE(SUM(s.nexus_fee), 0) as total_fees
        FROM clients c
        LEFT JOIN sales s ON c.id = s.client_id
        WHERE c.status = 'active'
        GROUP BY c.id
        ORDER BY total_volume DESC
    ''')
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]

def get_recent_sales(limit=50):
    """Get recent sales across all clients"""
    conn = get_db()
    c = conn.cursor()
    
    c.execute('''
        SELECT s.*, c.name as client_name
        FROM sales s
        JOIN clients c ON s.client_id = c.id
        ORDER BY s.sold_at DESC
        LIMIT ?
    ''', (limit,))
    
    rows = c.fetchall()
    conn.close()
    
    return [dict(row) for row in rows]


# ============================================
# API ROUTES - HEALTH & STATUS
# ============================================

@app.route('/health')
def health():
    """Health check"""
    return jsonify({
        'status': 'healthy',
        'service': 'NEXUS HQ',
        'version': '1.0.0',
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/status')
def api_status():
    """Quick status with stats"""
    stats = get_dashboard_stats()
    return jsonify({
        'status': 'online',
        'clients': stats['clients']['total'],
        'total_volume': stats['volume']['total'],
        'total_revenue': stats['revenue']['total_fees'],
        'mrr': stats['revenue']['mrr']
    })

# ============================================
# API ROUTES - CLIENT MANAGEMENT
# ============================================

@app.route('/api/clients', methods=['GET'])
def list_clients():
    """List all clients (admin only - add auth later)"""
    clients = get_all_clients()
    # Remove sensitive data
    for c in clients:
        c.pop('api_key', None)
    return jsonify({'clients': clients, 'count': len(clients)})

@app.route('/api/clients/register', methods=['POST'])
def api_register_client():
    """Register a new client"""
    data = request.get_json()
    
    required = ['name', 'email']
    for field in required:
        if not data.get(field):
            return jsonify({'error': f'Missing required field: {field}'}), 400
    
    result = register_client(
        name=data['name'],
        email=data['email'],
        tier=data.get('tier', 'starter'),
        location=data.get('location', ''),
        phone=data.get('phone', ''),
        notes=data.get('notes', '')
    )
    
    if result.get('success'):
        return jsonify(result), 201
    else:
        return jsonify(result), 400

@app.route('/api/clients/<client_id>', methods=['GET'])
def get_client(client_id):
    """Get client details"""
    conn = get_db()
    c = conn.cursor()
    c.execute('SELECT * FROM clients WHERE id = ?', (client_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        client = dict(row)
        client.pop('api_key', None)  # Don't expose API key
        return jsonify(client)
    return jsonify({'error': 'Client not found'}), 404

# ============================================
# API ROUTES - SUBSCRIPTIONS
# ============================================

@app.route('/api/subscriptions/tiers', methods=['GET'])
def list_tiers():
    """List all subscription tiers"""
    return jsonify(TIERS)

@app.route('/api/subscriptions/revenue', methods=['GET'])
def subscription_revenue():
    """Get subscription revenue stats"""
    return jsonify(get_subscription_revenue())

@app.route('/api/subscriptions/invoices', methods=['GET'])
def list_invoices():
    """List all pending invoices"""
    return jsonify({'invoices': get_pending_invoices()})

@app.route('/api/subscriptions/invoices/<client_id>', methods=['GET'])
def client_invoices(client_id):
    """Get invoices for a specific client"""
    return jsonify({'invoices': get_client_invoices(client_id)})

@app.route('/api/subscriptions/invoices/create', methods=['POST'])
def create_client_invoice():
    """Create an invoice for a client"""
    data = request.get_json()
    client_id = data.get('client_id')
    tier = data.get('tier')
    
    if not client_id:
        return jsonify({'error': 'Missing client_id'}), 400
    
    invoice = create_invoice(client_id, tier)
    if invoice:
        return jsonify({'success': True, 'invoice': invoice}), 201
    return jsonify({'error': 'Failed to create invoice'}), 400

@app.route('/api/subscriptions/invoices/<invoice_id>/pay', methods=['POST'])
def pay_invoice(invoice_id):
    """Mark an invoice as paid"""
    data = request.get_json() or {}
    payment_method = data.get('payment_method', 'manual')
    
    mark_invoice_paid(invoice_id, payment_method)
    return jsonify({'success': True, 'message': f'Invoice {invoice_id} marked as paid'})

@app.route('/api/subscriptions/client/<client_id>/tier', methods=['PUT'])
def update_client_tier(client_id):
    """Change a client's subscription tier"""
    data = request.get_json()
    new_tier = data.get('tier')
    
    if not new_tier:
        return jsonify({'error': 'Missing tier'}), 400
    
    result = change_client_tier(client_id, new_tier)
    if result.get('success'):
        return jsonify(result)
    return jsonify(result), 400

@app.route('/api/subscriptions/generate-invoices', methods=['POST'])
def trigger_invoice_generation():
    """Manually trigger invoice generation for due clients"""
    invoices = generate_monthly_invoices()
    return jsonify({
        'success': True,
        'invoices_created': len(invoices),
        'invoices': invoices
    })

# ============================================
# API ROUTES - PHONE HOME (Clients report here)
# ============================================

@app.route('/api/phone-home/sale', methods=['POST'])
def phone_home_sale():
    """Client reports a sale - THIS IS THE MONEY ENDPOINT"""
    # Authenticate via API key
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    client = get_client_by_api_key(api_key)
    if not client:
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    
    result = record_sale(
        client_id=client['id'],
        deck_name=data.get('deck_name', 'Unknown Deck'),
        format=data.get('format', 'Unknown'),
        card_count=data.get('card_count', 0),
        sale_value=float(data.get('sale_value', 0)),
        cards_json=json.dumps(data.get('cards', []))
    )
    
    return jsonify({
        'success': True,
        'message': f"Sale recorded! NEXUS fee: ${result['nexus_fee']:.2f}",
        **result
    })

@app.route('/api/phone-home/scan', methods=['POST'])
def phone_home_scan():
    """Client reports a card scan"""
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    client = get_client_by_api_key(api_key)
    if not client:
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    
    record_scan(
        client_id=client['id'],
        card_name=data.get('card_name', ''),
        set_code=data.get('set_code', ''),
        rarity=data.get('rarity', ''),
        price=float(data.get('price', 0)),
        confidence=float(data.get('confidence', 0))
    )
    
    return jsonify({'success': True, 'message': 'Scan recorded'})

@app.route('/api/phone-home/batch-scans', methods=['POST'])
def phone_home_batch_scans():
    """Client reports multiple scans at once"""
    api_key = request.headers.get('X-API-Key') or request.headers.get('Authorization', '').replace('Bearer ', '')
    
    if not api_key:
        return jsonify({'error': 'Missing API key'}), 401
    
    client = get_client_by_api_key(api_key)
    if not client:
        return jsonify({'error': 'Invalid API key'}), 401
    
    data = request.get_json()
    scans = data.get('scans', [])
    
    for scan in scans:
        record_scan(
            client_id=client['id'],
            card_name=scan.get('card_name', ''),
            set_code=scan.get('set_code', ''),
            rarity=scan.get('rarity', ''),
            price=float(scan.get('price', 0)),
            confidence=float(scan.get('confidence', 0))
        )
    
    return jsonify({'success': True, 'recorded': len(scans)})


# ============================================
# API ROUTES - DASHBOARD DATA
# ============================================

@app.route('/api/dashboard')
def api_dashboard():
    """Get full dashboard data"""
    return jsonify({
        'stats': get_dashboard_stats(),
        'leaderboard': get_client_leaderboard(),
        'recent_sales': get_recent_sales(20)
    })

@app.route('/api/dashboard/stats')
def api_dashboard_stats():
    """Get dashboard stats only"""
    return jsonify(get_dashboard_stats())

@app.route('/api/dashboard/leaderboard')
def api_dashboard_leaderboard():
    """Get client leaderboard"""
    return jsonify(get_client_leaderboard())

@app.route('/api/dashboard/sales')
def api_dashboard_sales():
    """Get recent sales"""
    limit = request.args.get('limit', 50, type=int)
    return jsonify(get_recent_sales(limit))

# ============================================
# WEB DASHBOARD (HTML)
# ============================================

DASHBOARD_HTML = '''
<!DOCTYPE html>
<html>
<head>
    <title>NEXUS HQ - Command Center</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: 'Segoe UI', Arial, sans-serif; 
            background: #0a0a0a; 
            color: #e0e0e0;
            min-height: 100vh;
        }
        .header {
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            padding: 20px 40px;
            border-bottom: 2px solid #d4af37;
        }
        .header h1 { 
            color: #d4af37; 
            font-size: 28px;
            display: flex;
            align-items: center;
            gap: 15px;
        }
        .header h1 span { font-size: 14px; color: #888; }
        .container { padding: 30px 40px; max-width: 1600px; margin: 0 auto; }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #1a1a2e;
            border: 1px solid #333;
            border-radius: 10px;
            padding: 20px;
            text-align: center;
        }
        .stat-card.gold { border-color: #d4af37; }
        .stat-card h3 { color: #888; font-size: 12px; text-transform: uppercase; margin-bottom: 10px; }
        .stat-card .value { font-size: 32px; font-weight: bold; color: #fff; }
        .stat-card.gold .value { color: #d4af37; }
        .stat-card .sub { font-size: 12px; color: #666; margin-top: 5px; }
        
        .section { margin-bottom: 30px; }
        .section h2 { 
            color: #d4af37; 
            font-size: 18px; 
            margin-bottom: 15px;
            padding-bottom: 10px;
            border-bottom: 1px solid #333;
        }
        
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px 15px; text-align: left; border-bottom: 1px solid #222; }
        th { background: #1a1a2e; color: #d4af37; font-size: 12px; text-transform: uppercase; }
        tr:hover { background: #1a1a2e; }
        .money { color: #4CAF50; }
        .fee { color: #d4af37; }
        .tier { 
            padding: 3px 8px; 
            border-radius: 4px; 
            font-size: 11px;
            text-transform: uppercase;
        }
        .tier.starter { background: #333; color: #888; }
        .tier.professional { background: #1a365d; color: #63b3ed; }
        .tier.enterprise { background: #553c9a; color: #b794f4; }
        .tier.founders { background: #744210; color: #d4af37; }
        
        .refresh-btn {
            background: #d4af37;
            color: #000;
            border: none;
            padding: 10px 20px;
            border-radius: 5px;
            cursor: pointer;
            font-weight: bold;
        }
        .refresh-btn:hover { background: #c9a227; }
        
        .live-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            background: #4CAF50;
            border-radius: 50%;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>
            <span class="live-indicator"></span>
            NEXUS HQ - COMMAND CENTER
            <span>The Mothership</span>
        </h1>
    </div>
    
    <div class="container">
        <div class="stats-grid" id="stats">
            <div class="stat-card gold">
                <h3>Monthly Revenue</h3>
                <div class="value" id="mrr">$0</div>
                <div class="sub">Subscription fees</div>
            </div>
            <div class="stat-card gold">
                <h3>Commission Fees</h3>
                <div class="value" id="month-fees">$0</div>
                <div class="sub">This month</div>
            </div>
            <div class="stat-card">
                <h3>Active Clients</h3>
                <div class="value" id="clients">0</div>
                <div class="sub">Deployed shops</div>
            </div>
            <div class="stat-card">
                <h3>Sales Volume</h3>
                <div class="value" id="volume">$0</div>
                <div class="sub">This month</div>
            </div>
            <div class="stat-card">
                <h3>Total Sales</h3>
                <div class="value" id="sales">0</div>
                <div class="sub">This month</div>
            </div>
            <div class="stat-card">
                <h3>Cards Scanned</h3>
                <div class="value" id="scans">0</div>
                <div class="sub">Network-wide</div>
            </div>
        </div>
        
        <div class="section">
            <h2>Client Leaderboard</h2>
            <table id="leaderboard">
                <thead>
                    <tr>
                        <th>Client</th>
                        <th>Location</th>
                        <th>Tier</th>
                        <th>Sales</th>
                        <th>Volume</th>
                        <th>NEXUS Fees</th>
                        <th>Last Seen</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
        
        <div class="section">
            <h2>Recent Sales <button class="refresh-btn" onclick="loadData()">Refresh</button></h2>
            <table id="recent-sales">
                <thead>
                    <tr>
                        <th>Time</th>
                        <th>Client</th>
                        <th>Deck</th>
                        <th>Format</th>
                        <th>Cards</th>
                        <th>Sale Value</th>
                        <th>NEXUS Fee</th>
                    </tr>
                </thead>
                <tbody></tbody>
            </table>
        </div>
    </div>
    
    <script>
        async function loadData() {
            try {
                const res = await fetch('/api/dashboard');
                const data = await res.json();
                
                // Stats
                document.getElementById('mrr').textContent = '$' + data.stats.revenue.mrr.toFixed(2);
                document.getElementById('month-fees').textContent = '$' + data.stats.revenue.month_fees.toFixed(2);
                document.getElementById('clients').textContent = data.stats.clients.total;
                document.getElementById('volume').textContent = '$' + data.stats.volume.this_month.toFixed(2);
                document.getElementById('sales').textContent = data.stats.sales.this_month;
                document.getElementById('scans').textContent = data.stats.network.total_scans.toLocaleString();
                
                // Leaderboard
                const lb = document.querySelector('#leaderboard tbody');
                lb.innerHTML = data.leaderboard.map(c => `
                    <tr>
                        <td><strong>${c.name}</strong></td>
                        <td>${c.location || '-'}</td>
                        <td><span class="tier ${c.subscription_tier}">${c.subscription_tier}</span></td>
                        <td>${c.sale_count}</td>
                        <td class="money">$${c.total_volume.toFixed(2)}</td>
                        <td class="fee">$${c.total_fees.toFixed(2)}</td>
                        <td>${c.last_seen ? new Date(c.last_seen).toLocaleDateString() : '-'}</td>
                    </tr>
                `).join('');
                
                // Recent sales
                const rs = document.querySelector('#recent-sales tbody');
                rs.innerHTML = data.recent_sales.map(s => `
                    <tr>
                        <td>${new Date(s.sold_at).toLocaleString()}</td>
                        <td>${s.client_name}</td>
                        <td>${s.deck_name}</td>
                        <td>${s.format}</td>
                        <td>${s.card_count}</td>
                        <td class="money">$${s.sale_value.toFixed(2)}</td>
                        <td class="fee">$${s.nexus_fee.toFixed(2)}</td>
                    </tr>
                `).join('');
                
            } catch (err) {
                console.error('Failed to load dashboard:', err);
            }
        }
        
        // Load on start and refresh every 30s
        loadData();
        setInterval(loadData, 30000);
    </script>
</body>
</html>
'''

@app.route('/')
def dashboard():
    """Main dashboard page"""
    return render_template_string(DASHBOARD_HTML)


# ============================================
# STATIC PAGES
# ============================================

@app.route('/kickstarter')
def kickstarter_page():
    """Serve the Kickstarter landing page"""
    return send_from_directory('.', 'kickstarter.html')


# ============================================
# MAIN ENTRY POINT
# ============================================

if __name__ == '__main__':
    print()
    print("=" * 60)
    print("  NEXUS HQ - THE MOTHERSHIP")
    print("  Central Command for All NEXUS Deployments")
    print("=" * 60)
    print()
    print(f"  Database: {DB_PATH}")
    print(f"  Dashboard: http://localhost:5050")
    print(f"  API: http://localhost:5050/api/")
    print()
    print("  Endpoints:")
    print("    GET  /                         - Web Dashboard")
    print("    GET  /api/status               - Quick status")
    print("    GET  /api/dashboard            - Full dashboard data")
    print()
    print("  Clients:")
    print("    GET  /api/clients              - List all clients")
    print("    POST /api/clients/register     - Register new client")
    print()
    print("  Phone Home (clients use these):")
    print("    POST /api/phone-home/sale      - Report a sale")
    print("    POST /api/phone-home/scan      - Report a scan")
    print()
    print("  Subscriptions:")
    print("    GET  /api/subscriptions/tiers     - List tiers")
    print("    GET  /api/subscriptions/revenue   - Revenue stats")
    print("    GET  /api/subscriptions/invoices  - Pending invoices")
    print("    POST /api/subscriptions/invoices/create - Create invoice")
    print("    POST /api/subscriptions/invoices/<id>/pay - Mark paid")
    print("    PUT  /api/subscriptions/client/<id>/tier - Change tier")
    print()
    print("=" * 60)
    print()
    
    import os
    port = int(os.environ.get('PORT', 5050))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(host='0.0.0.0', port=port, debug=debug)
