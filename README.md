# NEXUS HQ - THE MOTHERSHIP

Central command center for all NEXUS deployments.

## Quick Start

```bash
# Windows
run_hq.bat

# Or manually
pip install -r requirements.txt
python hq_server.py
```

Open browser: http://localhost:5050

## Features

| Feature | Description |
|---------|-------------|
| **Client Registry** | Track all shops using NEXUS |
| **Revenue Dashboard** | Sales volume + NEXUS commission fees |
| **Phone-Home API** | Clients automatically report sales |
| **Network Analytics** | Aggregate data across all clients |
| **Grading Oversight** | AI accuracy monitoring |

## Subscription Tiers

| Tier | Monthly Fee | Commission |
|------|-------------|------------|
| Starter | $29 | 8% |
| Professional | $79 | 6% |
| Enterprise | $199 | 4% |
| Founder's Edition | $0 | 5% |

## API Endpoints

### Status
- `GET /health` - Health check
- `GET /api/status` - Quick status with stats

### Dashboard
- `GET /api/dashboard` - Full dashboard data
- `GET /api/dashboard/stats` - Stats only
- `GET /api/dashboard/leaderboard` - Client rankings
- `GET /api/dashboard/sales` - Recent sales

### Client Management
- `GET /api/clients` - List all clients
- `POST /api/clients/register` - Register new client
- `GET /api/clients/<id>` - Get client details

### Phone Home (Clients use these)
- `POST /api/phone-home/sale` - Report a sale
- `POST /api/phone-home/scan` - Report a card scan
- `POST /api/phone-home/batch-scans` - Report multiple scans

## Client Integration

When a client NEXUS sells a deck, it calls:

```python
import requests

response = requests.post(
    'https://nexus-hq.example.com/api/phone-home/sale',
    headers={'X-API-Key': 'nxs_abc123...'},
    json={
        'deck_name': 'Gruul Aggro',
        'format': 'Commander',
        'card_count': 100,
        'sale_value': 45.67,
        'cards': [{'name': 'Lightning Bolt', 'qty': 4}, ...]
    }
)

# Response:
# {
#     'success': True,
#     'sale_id': 'SALE-ABC123',
#     'sale_value': 45.67,
#     'nexus_fee': 2.74,  # 6% for Professional tier
#     'client_keeps': 42.93
# }
```

## Database

SQLite database at `data/nexus_hq.db`

Tables:
- `clients` - Registered NEXUS shops
- `sales` - All sales across network
- `scans` - Card scans (network analytics)
- `grading_disputes` - AI grading disputes

## Patent Claims Supported

- Network effects (Claim 47-52)
- Grading oversight (Claim 67-73)
- Universal lifecycle management (Claim 1-5)

---

**NEXUS HQ** - Where the money comes home 💰
