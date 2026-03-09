#!/usr/bin/env python3
"""
Update product barcodes by extracting them from order history.
Since the product API doesn't return barcodes, we can get them from orders.
"""

import json
from pathlib import Path
import sys
from datetime import datetime, timedelta
sys.path.append(str(Path(__file__).parent))

from api.trendyol_client import TrendyolClient
from logging_config import get_logger
from config import get_config


def fetch_orders_and_extract_barcodes(client, logger, max_pages=10):
    """
    Fetch orders and extract product code -> barcode mappings.
    
    Args:
        client: TrendyolClient instance
        logger: Logger instance
        max_pages: Maximum pages to fetch per status
        
    Returns:
        Dictionary mapping productCode to barcode
    """
    barcode_mapping = {}
    
    # Fetch orders from multiple statuses to get more products
    statuses = ['Picking', 'Invoiced', 'Shipped', 'Delivered']
    
    for status in statuses:
        logger.info(f"Fetching {status} orders...")
        
        for page in range(max_pages):
            try:
                response = client.get_orders(status=status, size=100, page=page)
                orders = response.get('content', [])
                
                if not orders:
                    logger.info(f"No more {status} orders on page {page}")
                    break
                
                logger.info(f"{status} page {page}: Processing {len(orders)} orders")
                
                # Extract barcode from each order line
                for order in orders:
                    lines = order.get('lines', [])
                    for line in lines:
                        product_code = line.get('productCode')
                        barcode = line.get('barcode')
                        
                        if product_code and barcode:
                            # Store the mapping
                            if product_code not in barcode_mapping:
                                barcode_mapping[product_code] = barcode
                                logger.debug(f"Found barcode for product {product_code}: {barcode}")
                            elif barcode_mapping[product_code] != barcode:
                                # Log if different barcode found for same product
                                logger.warning(
                                    f"Different barcode for product {product_code}: "
                                    f"{barcode_mapping[product_code]} vs {barcode}"
                                )
                
                # Check if there are more pages
                total_pages = response.get('totalPages', 0)
                if page >= total_pages - 1:
                    logger.info(f"Reached last page for {status} orders")
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching {status} orders page {page}: {e}")
                break
    
    logger.info(f"Extracted barcodes for {len(barcode_mapping)} unique products")
    return barcode_mapping


def update_product_file_with_barcodes(barcode_mapping, product_file, logger):
    """
    Update the product JSON file with barcode data.
    
    Args:
        barcode_mapping: Dict mapping productCode to barcode
        product_file: Path to product JSON file
        logger: Logger instance
    """
    if not product_file.exists():
        logger.error(f"Product file not found: {product_file}")
        return False
    
    # Load existing product data
    with open(product_file, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    logger.info(f"Loaded {len(products)} products from file")
    
    # Create backup
    backup_file = product_file.with_suffix('.json.backup2')
    import shutil
    shutil.copy2(product_file, backup_file)
    logger.info(f"Created backup: {backup_file}")
    
    # Update products with barcodes
    updated_count = 0
    added_count = 0
    
    for product_code, barcode in barcode_mapping.items():
        product_code_str = str(product_code)  # Ensure string for JSON keys
        
        if product_code_str in products:
            # Update existing product - preserve all existing data, just update barcode
            old_barcode = products[product_code_str].get('barcode')
            if old_barcode != barcode:
                products[product_code_str]['barcode'] = barcode
                updated_count += 1
                if old_barcode:
                    logger.info(f"Updated barcode for product {product_code_str}: {old_barcode} -> {barcode}")
                else:
                    logger.info(f"Added barcode for product {product_code_str}: {barcode}")
        else:
            # Add new product entry with barcode
            products[product_code_str] = {
                'item_number': int(product_code_str),
                'barcode': barcode,
                'name_romanian': '',
                'name_english': '',
                'brand': '',
                'price': 0,
                'category': ''
            }
            added_count += 1
            logger.info(f"Added new product {product_code_str} with barcode {barcode}")
    
    # Save updated file
    with open(product_file, 'w', encoding='utf-8') as f:
        json.dump(products, f, indent=2, ensure_ascii=False)
    
    logger.info(f"Updated {updated_count} existing products")
    logger.info(f"Added {added_count} new products")
    logger.info(f"Saved to {product_file}")
    
    # Statistics
    products_with_barcodes = sum(1 for p in products.values() if p.get('barcode'))
    products_without_barcodes = len(products) - products_with_barcodes
    
    logger.info(f"\nStatistics:")
    logger.info(f"  Total products: {len(products)}")
    logger.info(f"  With barcodes: {products_with_barcodes}")
    logger.info(f"  Without barcodes: {products_without_barcodes}")
    
    return True


def main():
    """Main function."""
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger = get_logger('barcode_updater')
    
    try:
        print("Fetching barcode data from order history...\n")
        
        client = TrendyolClient()
        
        # Fetch orders and extract barcodes
        print("Step 1: Extracting barcodes from orders...")
        barcode_mapping = fetch_orders_and_extract_barcodes(client, logger, max_pages=10)
        
        if not barcode_mapping:
            print("\n✗ No barcodes found in order history!")
            return
        
        print(f"\n✓ Found barcodes for {len(barcode_mapping)} products\n")
        
        # Show sample barcodes
        print("Sample barcodes found:")
        for i, (product_code, barcode) in enumerate(list(barcode_mapping.items())[:5], 1):
            print(f"  {i}. Product {product_code}: {barcode}")
        print()
        
        # Update product file
        print("Step 2: Updating product file with barcodes...")
        product_file = Path(__file__).parent / 'api' / 'data' / 'trendyol_products_romanian.json'
        
        success = update_product_file_with_barcodes(barcode_mapping, product_file, logger)
        
        if success:
            print("\n✓ Successfully updated product file with barcodes!")
        else:
            print("\n✗ Failed to update product file")
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
