#!/usr/bin/env python3
"""
NEXUS HQ Phone Home Client
==========================
Drop-in module for NEXUS clients to report sales/scans to HQ

Usage:
    from nexus_hq_client import NexusHQClient
    
    hq = NexusHQClient(api_key='nxs_your_key_here')
    
    # Report a sale
    result = hq.report_sale(
        deck_name='Gruul Aggro',
        format='Commander',
        card_count=100,
        sale_value=45.67
    )
    print(f"NEXUS fee: ${result['nexus_fee']}")
"""

import requests
import json
from typing import Dict, List, Optional

# Default HQ URL - change for production
DEFAULT_HQ_URL = 'http://localhost:5050'
# Production: DEFAULT_HQ_URL = 'https://hq.nexuscollectibles.com'


class NexusHQClient:
    """Client for communicating with NEXUS HQ"""
    
    def __init__(self, api_key: str, hq_url: str = DEFAULT_HQ_URL):
        self.api_key = api_key
        self.hq_url = hq_url.rstrip('/')
        self.headers = {
            'X-API-Key': api_key,
            'Content-Type': 'application/json'
        }
    
    def _post(self, endpoint: str, data: dict) -> dict:
        """Make POST request to HQ"""
        try:
            response = requests.post(
                f'{self.hq_url}{endpoint}',
                headers=self.headers,
                json=data,
                timeout=10
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def _get(self, endpoint: str) -> dict:
        """Make GET request to HQ"""
        try:
            response = requests.get(
                f'{self.hq_url}{endpoint}',
                headers=self.headers,
                timeout=10
            )
            return response.json()
        except requests.exceptions.RequestException as e:
            return {'success': False, 'error': str(e)}
    
    def report_sale(self, deck_name: str, format: str, card_count: int, 
                    sale_value: float, cards: List[dict] = None) -> dict:
        """
        Report a sale to NEXUS HQ
        
        Args:
            deck_name: Name of the deck sold
            format: Format (Commander, Modern, etc.)
            card_count: Number of cards in deck
            sale_value: Total sale price
            cards: Optional list of cards [{'name': 'Card Name', 'qty': 4}, ...]
        
        Returns:
            {
                'success': True,
                'sale_id': 'SALE-ABC123',
                'sale_value': 45.67,
                'nexus_fee': 2.74,
                'client_keeps': 42.93,
                'commission_rate': 6.0
            }
        """
        return self._post('/api/phone-home/sale', {
            'deck_name': deck_name,
            'format': format,
            'card_count': card_count,
            'sale_value': sale_value,
            'cards': cards or []
        })
    
    def report_scan(self, card_name: str, set_code: str = '', 
                    rarity: str = '', price: float = 0, 
                    confidence: float = 0) -> dict:
        """Report a single card scan"""
        return self._post('/api/phone-home/scan', {
            'card_name': card_name,
            'set_code': set_code,
            'rarity': rarity,
            'price': price,
            'confidence': confidence
        })
    
    def report_batch_scans(self, scans: List[dict]) -> dict:
        """
        Report multiple scans at once
        
        Args:
            scans: List of scan dicts [{'card_name': 'X', 'set_code': 'Y', ...}, ...]
        """
        return self._post('/api/phone-home/batch-scans', {'scans': scans})
    
    def check_status(self) -> dict:
        """Check HQ status"""
        return self._get('/api/status')
    
    def is_connected(self) -> bool:
        """Check if HQ is reachable"""
        try:
            result = self.check_status()
            return result.get('status') == 'online'
        except:
            return False


# Convenience function for quick sales
def phone_home_sale(api_key: str, deck_name: str, format: str, 
                    card_count: int, sale_value: float, 
                    hq_url: str = DEFAULT_HQ_URL) -> dict:
    """Quick function to report a sale without creating a client instance"""
    client = NexusHQClient(api_key, hq_url)
    return client.report_sale(deck_name, format, card_count, sale_value)


# Test
if __name__ == '__main__':
    print("Testing NEXUS HQ Client...")
    
    # Test with dummy key (will fail auth but tests connectivity)
    client = NexusHQClient(api_key='nxs_test_key')
    
    print(f"\nHQ URL: {client.hq_url}")
    print(f"Connected: {client.is_connected()}")
    
    # Try reporting a sale
    result = client.report_sale(
        deck_name='Test Deck',
        format='Commander',
        card_count=100,
        sale_value=25.00
    )
    print(f"\nSale Result: {json.dumps(result, indent=2)}")
