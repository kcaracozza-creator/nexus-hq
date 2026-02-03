#!/usr/bin/env python3
"""
NEXUS HQ Demo Data Seeder
Creates sample clients, sales, and invoices for testing
"""

import sys
sys.path.insert(0, '.')

from hq_server import (register_client, record_sale, record_scan, 
                       get_dashboard_stats, create_invoice, mark_invoice_paid,
                       get_subscription_revenue)

print("=" * 50)
print("  SEEDING NEXUS HQ DEMO DATA")
print("=" * 50)

# Register demo clients
clients = [
    {
        'name': 'CardVault NYC',
        'email': 'tom@cardvault.com',
        'tier': 'enterprise',
        'location': 'New York, NY',
        'notes': 'Tom Brady flagship store'
    },
    {
        'name': 'Jersey Cards',
        'email': 'mike@jerseycards.com',
        'tier': 'professional',
        'location': 'East Rutherford, NJ',
        'notes': 'First deployment partner'
    },
    {
        'name': "Mike's MTG Emporium",
        'email': 'mike@mikesmtg.com',
        'tier': 'starter',
        'location': 'Newark, NJ',
        'notes': 'Small LGS'
    },
    {
        'name': 'Collectors Haven',
        'email': 'sarah@collectorshaven.com',
        'tier': 'founders',
        'location': 'Hoboken, NJ',
        'notes': "Founder's Edition - early adopter"
    },
]

registered = []
for c in clients:
    result = register_client(**c)
    if result.get('success'):
        print(f"[OK] Registered: {c['name']} ({c['tier']}) - API Key: {result['api_key'][:20]}...")
        registered.append(result)
    else:
        print(f"[!] {c['name']}: {result.get('error', 'Already exists')}")

# Add some sample sales
if registered:
    sales_data = [
        ('Gruul Aggro', 'Commander', 100, 45.67),
        ('Mono Blue Control', 'Commander', 100, 12.34),
        ('Burn', 'Modern', 60, 89.00),
        ('Elves', 'Legacy', 60, 234.50),
        ('Goblins', 'Pauper', 60, 8.99),
    ]
    
    print("\n[+] Adding sample sales...")
    for i, (deck, fmt, cards, value) in enumerate(sales_data):
        client = registered[i % len(registered)]
        result = record_sale(
            client_id=client['client_id'],
            deck_name=deck,
            format=fmt,
            card_count=cards,
            sale_value=value
        )
        print(f"   {deck}: ${value:.2f} -> Fee: ${result['nexus_fee']:.2f}")
    
    # Create and pay some invoices
    print("\n[$] Creating subscription invoices...")
    for client in registered:
        if client.get('monthly_fee', 0) > 0:
            invoice = create_invoice(client['client_id'])
            if invoice:
                # Mark some as paid
                mark_invoice_paid(invoice['invoice_id'], 'demo')
                print(f"   {invoice['tier']}: ${invoice['amount']:.2f} - PAID")

# Show stats
print("\n" + "=" * 50)
print("  DASHBOARD STATS")
print("=" * 50)

stats = get_dashboard_stats()
sub_revenue = get_subscription_revenue()

print(f"""
  Active Clients:    {stats['clients']['total']}
  
  SUBSCRIPTION REVENUE:
  MRR (Monthly):     ${sub_revenue['mrr']:.2f}
  Collected (Month): ${sub_revenue['month_collected']:.2f}
  Total Collected:   ${sub_revenue['total_collected']:.2f}
  
  COMMISSION FEES:
  This Month:        ${stats['revenue']['month_fees']:.2f}
  Total:             ${stats['revenue']['total_fees']:.2f}
  
  SALES:
  This Month:        {stats['sales']['this_month']} sales
  Volume:            ${stats['volume']['this_month']:.2f}
""")

print("=" * 50)
print("  Demo data seeded! Run 'python hq_server.py' to start.")
print("  Then open http://localhost:5050")
print("=" * 50)
