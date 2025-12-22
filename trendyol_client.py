"""
Trendyol API Client for order management and status updates.
Handles authentication, order retrieval, and invoice status notifications.
"""

import requests
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import logging

from config import get_config
from logging_config import get_logger


class TrendyolAPIError(Exception):
    """Custom exception for Trendyol API errors."""
    
    def __init__(self, message: str, status_code: int = None, response_data: Dict = None):
        self.message = message
        self.status_code = status_code
        self.response_data = response_data
        super().__init__(self.message)


class TrendyolClient:
    """Client for interacting with Trendyol Marketplace API."""
    
    def __init__(self):
        """Initialize Trendyol client."""
        self.config = get_config()
        self.logger = get_logger('trendyol')
        
        # API configuration
        self.base_url = self.config.trendyol_endpoint
        self.supplier_id = self.config.trendyol_supplier_id
        
        # Create session for HTTP requests
        self.session = requests.Session()
        
        # Request headers
        self.headers = {
            'Authorization': self.config.trendyol_auth_header,
            'User-Agent': self.config.trendyol_user_agent,
            'Content-Type': 'application/json'
        }
        self.session.headers.update(self.headers)
    
    def _create_session_with_retries(self) -> requests.Session:
        """Create a requests session with retry strategy for resilience."""
        session = requests.Session()
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=2,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session
    
    def _make_request(self, method: str, endpoint: str, params: Dict = None, 
                     json_data: Dict = None, timeout: int = 30) -> Tuple[int, Dict]:
        """
        Make HTTP request to Trendyol API with error handling.
        
        Args:
            method: HTTP method (GET, PUT, POST, DELETE)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json_data: JSON data for request body
            timeout: Request timeout in seconds
            
        Returns:
            Tuple of (status_code, response_data)
            
        Raises:
            TrendyolAPIError: On API errors
        """
        url = f"{self.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=timeout
            )
            
            # Try to parse JSON response
            try:
                response_data = response.json() if response.content else {}
            except json.JSONDecodeError:
                response_data = {"raw_response": response.text}
            
            # Log request details
            self.logger.debug(f"{method} {url} -> {response.status_code}")
            
            # Handle different status codes
            if response.status_code in [200, 201]:
                return response.status_code, response_data
            elif response.status_code == 401:
                raise TrendyolAPIError(
                    "Authentication failed. Check API credentials.", 
                    response.status_code, 
                    response_data
                )
            elif response.status_code == 403:
                raise TrendyolAPIError(
                    "Access forbidden. Check User-Agent header and permissions.", 
                    response.status_code, 
                    response_data
                )
            elif response.status_code == 429:
                raise TrendyolAPIError(
                    "Rate limit exceeded. Too many requests.", 
                    response.status_code, 
                    response_data
                )
            elif response.status_code == 503:
                raise TrendyolAPIError(
                    "Service unavailable. Check IP authorization for staging environment.", 
                    response.status_code, 
                    response_data
                )
            else:
                raise TrendyolAPIError(
                    f"API request failed with status {response.status_code}: {response_data.get('message', 'Unknown error')}", 
                    response.status_code, 
                    response_data
                )
                
        except requests.exceptions.Timeout:
            raise TrendyolAPIError("Request timed out")
        except requests.exceptions.ConnectionError:
            raise TrendyolAPIError("Connection error")
        except requests.exceptions.RequestException as e:
            raise TrendyolAPIError(f"Request failed: {str(e)}")
    
    def get_orders(self, status: str = "Created", start_date: datetime = None, 
                   end_date: datetime = None, page: int = 0, size: int = 100,
                   order_by_field: str = "PackageLastModifiedDate",
                   order_by_direction: str = "DESC") -> Dict[str, Any]:
        """
        Retrieve orders from Trendyol.
        
        Args:
            status: Order status to filter by (Created, Picking, Invoiced, Shipped, etc.)
            start_date: Start date for filtering orders
            end_date: End date for filtering orders  
            page: Page number for pagination
            size: Number of orders per page (max 100)
            order_by_field: Field to sort by (PackageLastModifiedDate, CreatedDate)
            order_by_direction: Sort direction (ASC, DESC)
            
        Returns:
            Dictionary containing order data
        """
        endpoint = f"/integration/order/sellers/{self.supplier_id}/orders"
        
        params = {
            'status': status,
            'page': page,
            'size': min(size, 100),  # Limit to max 100
            'orderByField': order_by_field,
            'orderByDirection': order_by_direction
        }
        
        # Add date filters if provided
        if start_date:
            # Convert to timestamp (milliseconds)
            params['startDate'] = int(start_date.timestamp() * 1000)
        
        if end_date:
            params['endDate'] = int(end_date.timestamp() * 1000)
        
        self.logger.info(f"Fetching orders with status '{status}' (page {page}, size {size})")
        
        status_code, response_data = self._make_request('GET', endpoint, params=params)
        
        self.logger.info(f"Retrieved {len(response_data.get('content', []))} orders")
        
        return response_data
    
    def get_orders_to_process(self, limit: int = 100) -> Dict[str, Any]:
        """
        Get orders that are ready to be processed.
        Fetches orders from BOTH "Picking" and "Invoiced" statuses.
        Fetches ALL orders across multiple pages if needed.
        
        Args:
            limit: Maximum number of orders to fetch
            
        Returns:
            Dictionary with 'success' flag and 'orders' list
        """
        try:
            # Fetch orders from both Picking and Invoiced statuses
            statuses = ['Picking', 'Invoiced']
            all_orders = []
            
            for status in statuses:
                page = 0
                page_size = 100
                status_orders = []
                
                while len(status_orders) < limit:
                    response = self.get_orders(status=status, size=page_size, page=page)
                    
                    orders = response.get('content', [])
                    if not orders:
                        break
                    
                    status_orders.extend(orders)
                    
                    # Check if we have more pages
                    total_pages = response.get('totalPages', 0)
                    if page >= total_pages - 1:
                        break
                    
                    page += 1
                
                all_orders.extend(status_orders)
                self.logger.info(f"Fetched {len(status_orders)} orders with status '{status}'")
            
            # Remove duplicates by package_id (in case same order appears in both)
            seen_ids = set()
            unique_orders = []
            for order in all_orders:
                order_id = order.get('id')
                if order_id not in seen_ids:
                    seen_ids.add(order_id)
                    unique_orders.append(order)
            
            # Limit to requested amount
            unique_orders = unique_orders[:limit]
            
            self.logger.info(f"Total unique orders fetched: {len(unique_orders)}")
            
            return {
                'success': True,
                'orders': unique_orders,
                'total': len(unique_orders)
            }
            
        except Exception as e:
            self.logger.error(f"Failed to get orders to process: {e}")
            return {
                'success': False,
                'error': str(e),
                'orders': []
            }
    
    def extract_order_info(self, order_data: Dict) -> Dict[str, Any]:
        """
        Extract relevant information from Trendyol order for processing.
        
        Args:
            order_data: Raw order data from Trendyol API
            
        Returns:
            Cleaned order information dictionary
        """
        lines = order_data.get('lines', [])
        invoice_address = order_data.get('invoiceAddress', {})
        
        order_info = {
            'package_id': order_data.get('id'),
            'order_number': order_data.get('orderNumber'),
            'order_date': datetime.fromtimestamp(order_data.get('orderDate', 0) / 1000),
            'total_price': order_data.get('totalPrice', 0),
            'currency': order_data.get('currencyCode', 'TRY'),
            'is_corporate': order_data.get('commercial', False),
            'cargo_tracking_number': order_data.get('cargoTrackingNumber'),
            'customer': {
                'first_name': invoice_address.get('firstName', ''),
                'last_name': invoice_address.get('lastName', ''),
                'full_name': invoice_address.get('fullName', ''),
                'email': order_data.get('customerEmail', ''),
                'phone': invoice_address.get('phone', ''),
                'address': invoice_address.get('fullAddress', ''),
                'city': invoice_address.get('city', ''),
                'district': invoice_address.get('district', ''),
                'county': invoice_address.get('countyName', ''),
                'country_code': invoice_address.get('countryCode', 'TR'),
            },
            'items': [],
            'order_lines': []
        }
        
        # Process order items
        for line in lines:
            # Get quantity from discountDetails array length (each entry = 1 physical item)
            discount_details = line.get('discountDetails', [])
            quantity = len(discount_details) if discount_details else 1
            
            item = {
                'line_id': line.get('id'),
                'sku': line.get('merchantSku', ''),
                'product_code': line.get('productCode'),  # Item number for mapping
                'product_name': line.get('productName', ''),  # English name from API
                'quantity': quantity,
                'unit_price': line.get('price', 0),
                'amount': line.get('amount', 0) * quantity,
                'discount': line.get('discount', 0) * quantity,
                'barcode': line.get('barcode', ''),
                'product_color': line.get('productColor', ''),
                'product_size': line.get('productSize', ''),
            }
            order_info['items'].append(item)
            
            # Prepare order lines for status updates
            for i in range(quantity):
                order_line = {
                    'lineId': line.get('id'),
                    'quantity': 1
                }
                order_info['order_lines'].append(order_line)
        
        return order_info
    
    def health_check(self) -> bool:
        """
        Perform a health check of the Trendyol API connection.
        
        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Try to fetch a small number of orders to test connection
            self.get_orders(size=1, page=0)
            self.logger.info("Trendyol API health check passed")
            return True
        except TrendyolAPIError as e:
            self.logger.error(f"Trendyol API health check failed: {e.message}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error in health check: {str(e)}")
            return False


if __name__ == "__main__":
    # Test the Trendyol client
    import logging
    logging.basicConfig(level=logging.INFO)
    
    try:
        client = TrendyolClient()
        print("Trendyol client initialized successfully!")
        
        # Test health check
        if client.health_check():
            print("✓ API connection successful")
            
            # Test getting orders
            print("\nTesting order retrieval...")
            result = client.get_orders_to_process(limit=5)
            if result['success']:
                print(f"Retrieved {result['total']} orders")
                
                # Show first order info if available
                if result['orders']:
                    first_order = result['orders'][0]
                    order_info = client.extract_order_info(first_order)
                    print(f"\nFirst order info:")
                    print(f"  Package ID: {order_info['package_id']}")
                    print(f"  Order Number: {order_info['order_number']}")
                    print(f"  Customer: {order_info['customer']['full_name']}")
                    print(f"  Total: {order_info['total_price']} {order_info['currency']}")
                    print(f"  Items: {len(order_info['items'])}")
        else:
            print("✗ API connection failed")
            
    except Exception as e:
        print(f"Error: {e}")

