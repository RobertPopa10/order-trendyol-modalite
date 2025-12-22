#!/usr/bin/env python3
"""
Order Processing Module for Orders-Trendyol Excel Generator.

This module handles the main workflow:
1. Fetch orders from Trendyol (status: Picking)
2. Translate product names to Romanian
3. Map to simplified names and extract colors
4. Generate Excel files with order AWBs
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from config import get_config
from logging_config import get_logger, log_order_processing, log_system_event, log_exception
from api.trendyol_client import TrendyolClient
from api.product_translator_v2 import ProductTranslationError, get_auto_translator
from api.product_mapper import ProductMappingError, get_product_mapper
from api.excel_generator import ExcelGenerator


class OrderProcessor:
    """Main order processing workflow coordinator."""
    
    def __init__(self):
        """Initialize the order processor."""
        self.config = get_config()
        self.logger = get_logger('processor')
        
        # Initialize API clients and services
        self.trendyol = TrendyolClient()
        self.translator = get_auto_translator()
        # Allow color extraction to return "N/A" for products without colors
        self.mapper = get_product_mapper(fail_on_missing=False)
        self.excel_generator = ExcelGenerator()
        
        # Setup state tracking
        self.state_file = self.config.data_dir / 'processed_orders.json'
        self.processed_orders = self._load_processed_orders()
        
        # Processing statistics
        self.stats = {
            'session_start': datetime.now(),
            'orders_processed': 0,
            'successful': 0,
            'failed': 0,
            'errors': [],
        }
        
        # Generate unique session ID for this run
        self.current_session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        self.logger.info("Order processor initialized")
    
    def _load_processed_orders(self) -> Dict:
        """Load processed orders from state file."""
        try:
            if self.state_file.exists():
                with open(self.state_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.warning(f"Could not load processed orders state: {e}")
            return {}
    
    def _save_processed_orders(self):
        """Save processed orders to state file."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(exist_ok=True)
            
            with open(self.state_file, 'w') as f:
                json.dump(self.processed_orders, f, indent=2, default=str)
            
        except Exception as e:
            self.logger.error(f"Could not save processed orders state: {e}")
    
    def _is_order_processed(self, package_id: str) -> bool:
        """Check if an order has already been processed."""
        package_id_str = str(package_id)
        return package_id_str in self.processed_orders
    
    def _mark_order_processed(self, package_id: str, status: str, details: Dict):
        """Mark an order as processed."""
        package_id_str = str(package_id)
        self.processed_orders[package_id_str] = {
            'status': status,
            'processed_at': datetime.now().isoformat(),
            'session_id': self.current_session_id,
            'details': details
        }
        self._save_processed_orders()
    
    
    def _process_order_item(self, order_info: Dict, item: Dict) -> Dict:
        """
        Process a single order item (translate + map + extract color).
        
        Args:
            order_info: Full order information dictionary
            item: Order item dictionary
            
        Returns:
            Processed item with simplified name and color
            
        Raises:
            ProductTranslationError: If translation fails
            ProductMappingError: If mapping fails
        """
        product_code = item.get('product_code')
        english_name = item.get('product_name')
        
        # Step 1: Translate to Romanian
        romanian_name = self.translator.translate_by_product_code(product_code, english_name)
        
        # Step 2: Map to simplified name, color, and RAZZ code
        simplified_name, color, razz_code = self.mapper.map_product(product_code, romanian_name)
        
        # Step 4: Build processed item
        processed_item = {
            'customer_name': order_info['customer']['full_name'],
            'quantity': item.get('quantity', 1),
            'product_name': simplified_name,
            'color': color,
            'product_code': product_code,
            'razz_code': razz_code,
            'romanian_name': romanian_name,
            'order_number': order_info['order_number'],
            'package_id': order_info['package_id'],
            'cargo_tracking_number': order_info.get('cargo_tracking_number')
        }
        
        return processed_item
    
    def process_single_order(self, order_data: Dict) -> List[Dict]:
        """
        Process a single Trendyol order.
        
        Args:
            order_data: Raw order data from Trendyol API
            
        Returns:
            List of processed order items
            
        Raises:
            Various exceptions if processing fails
        """
        # Extract order information
        order_info = self.trendyol.extract_order_info(order_data)
        package_id = order_info['package_id']
        order_number = order_info['order_number']
        
        self.logger.info(f"Processing order {order_number} (Package ID: {package_id})")
        
        # Check if already processed
        if self._is_order_processed(package_id):
            self.logger.info(f"Order {order_number} already processed, skipping")
            return []
        
        processed_items = []
        
        # Process each item in the order
        for item in order_info['items']:
            try:
                processed_item = self._process_order_item(order_info, item)
                processed_items.append(processed_item)
                
                self.logger.info(
                    f"  ✓ Item: {processed_item['product_name']} {processed_item['color']} "
                    f"(Qty: {processed_item['quantity']}) for {processed_item['customer_name']}"
                )
                
            except (ProductTranslationError, ProductMappingError) as e:
                # Fatal error - cannot process this order
                self.logger.error(f"Failed to process item in order {order_number}: {e}")
                raise
        
        # Mark order as processed
        self._mark_order_processed(
            package_id,
            'processed',
            {
                'order_number': order_number,
                'customer': order_info['customer']['full_name'],
                'items_count': len(processed_items)
            }
        )
        
        log_order_processing(
            self.logger,
            order_number,
            'Processing',
            'Success',
            f"{len(processed_items)} items processed"
        )
        
        return processed_items
    
    def process_orders_batch(self, max_pages: int = 5) -> Dict:
        """
        Process a batch of orders from Trendyol.
        Fetches ALL orders across multiple pages and only processes new ones.
        
        Args:
            max_pages: Maximum number of pages to fetch per status
            
        Returns:
            Dictionary with processing results
        """
        self.logger.info(f"Starting batch processing (max {max_pages} pages per status)")
        
        try:
            # Fetch orders from Trendyol
            result = self.trendyol.get_orders_to_process(max_pages=max_pages)
            
            if not result['success']:
                return {
                    'success': False,
                    'error': result.get('error'),
                    'orders_processed': 0
                }
            
            orders = result['orders']
            
            if not orders:
                self.logger.info("No orders to process")
                return {
                    'success': True,
                    'orders_processed': 0,
                    'message': 'No orders available'
                }
            
            self.logger.info(f"Found {len(orders)} orders to process")
            
            # Process all orders
            all_processed_items = []
            failed_orders = []
            
            for order_data in orders:
                try:
                    processed_items = self.process_single_order(order_data)
                    all_processed_items.extend(processed_items)
                    self.stats['successful'] += 1
                    
                except Exception as e:
                    order_number = order_data.get('orderNumber', 'UNKNOWN')
                    self.logger.error(f"Failed to process order {order_number}: {e}")
                    failed_orders.append({
                        'order_number': order_number,
                        'error': str(e)
                    })
                    self.stats['failed'] += 1
                    self.stats['errors'].append(str(e))
            
            # If we have processed items, generate Excel and AWB labels
            if all_processed_items:
                timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
                
                excel_path = self.excel_generator.generate_from_orders(
                    all_processed_items,
                    f"orders_{timestamp}.xlsx"
                )
                
                log_system_event(
                    self.logger,
                    'Excel Generated',
                    {
                        'file': excel_path.name,
                        'orders': len(all_processed_items),
                        'successful': self.stats['successful'],
                        'failed': self.stats['failed']
                    }
                )
                
                # Note: orders_list JSON removed - only excel_order.json is needed
                # Get excel_order.json path for AWB reordering
                excel_order_path = excel_path.parent / excel_path.name.replace('.xlsx', '_excel_order.json')
                
                return {
                    'success': True,
                    'orders_processed': len(orders),
                    'items_processed': len(all_processed_items),
                    'successful': self.stats['successful'],
                    'failed': self.stats['failed'],
                    'excel_file': str(excel_path),
                    'order_list_file': str(excel_order_path),  # Now points to excel_order.json
                    'failed_orders': failed_orders
                }
            else:
                return {
                    'success': True if not failed_orders else False,
                    'orders_processed': len(orders),
                    'items_processed': 0,
                    'message': 'No items to process' if not failed_orders else 'All orders failed',
                    'failed_orders': failed_orders
                }
                
        except Exception as e:
            log_exception(self.logger, 'Batch Processing', e)
            return {
                'success': False,
                'error': str(e),
                'orders_processed': 0
            }
    
    def get_stats(self) -> Dict:
        """Get processing statistics."""
        return {
            'session_start': self.stats['session_start'].isoformat(),
            'orders_processed': self.stats['orders_processed'],
            'successful': self.stats['successful'],
            'failed': self.stats['failed'],
            'success_rate': (self.stats['successful'] / max(1, self.stats['orders_processed'])) * 100,
            'total_processed_ever': len(self.processed_orders)
        }
    
    def get_last_session_id(self) -> str:
        """Get the most recent session ID from processed orders."""
        try:
            if not os.path.exists(self.state_file):
                return ""
            
            with open(self.state_file, 'r', encoding='utf-8') as f:
                processed_orders = json.load(f)
            
            # Find all unique session IDs and get the most recent one
            session_ids = set()
            for order in processed_orders.values():
                if 'session_id' in order:
                    session_ids.add(order['session_id'])
            
            if not session_ids:
                return ""
            
            # Return the most recent session ID (lexicographically largest for our format)
            return max(session_ids)
            
        except Exception as e:
            self.logger.error(f"Error getting last session ID: {e}")
            return ""
    
    def delete_orders_by_session(self, session_id: str) -> int:
        """
        Delete all orders processed in a specific session.
        
        Args:
            session_id: The session ID to delete orders for
            
        Returns:
            Number of orders deleted
        """
        try:
            orders_to_delete = []
            
            # Find orders from the specified session
            for package_id, order_data in self.processed_orders.items():
                if order_data.get('session_id') == session_id:
                    orders_to_delete.append(package_id)
            
            # Delete the orders
            for package_id in orders_to_delete:
                del self.processed_orders[package_id]
            
            # Save the updated processed orders
            if orders_to_delete:
                self._save_processed_orders()
                self.logger.info(f"Deleted {len(orders_to_delete)} orders from session {session_id}")
            
            return len(orders_to_delete)
            
        except Exception as e:
            self.logger.error(f"Failed to delete orders from session {session_id}: {e}")
            return 0


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Order Processor Test")
    print("=" * 60)
    
    try:
        processor = OrderProcessor()
        print("✅ Order processor initialized successfully")
        
        # Test processing
        print("\n🔄 Testing order processing...")
        result = processor.process_orders_batch(limit=5)
        
        if result['success']:
            print(f"\n✅ Processing successful!")
            print(f"   Orders processed: {result.get('orders_processed', 0)}")
            print(f"   Items processed: {result.get('items_processed', 0)}")
            print(f"   Successful: {result.get('successful', 0)}")
            print(f"   Failed: {result.get('failed', 0)}")
            if result.get('excel_file'):
                print(f"   Excel file: {result['excel_file']}")
        else:
            print(f"\n❌ Processing failed: {result.get('error', 'Unknown error')}")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
    
    print("=" * 60)

