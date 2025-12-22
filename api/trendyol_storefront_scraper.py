#!/usr/bin/env python3
"""
Trendyol Storefront Product Name Scraper

Fetches product data from the public Trendyol storefront API to get Romanian product names.
This allows automatic translation without manual mapping.
"""

import cloudscraper
import json
import time
from pathlib import Path
from typing import Dict, List, Optional
import sys
sys.path.append(str(Path(__file__).parent.parent))
from logging_config import get_logger


class TrendyolStorefrontScraper:
    """Scrapes product names from Trendyol's public storefront."""
    
    def __init__(self, merchant_id: str = "1197502"):
        """
        Initialize the storefront scraper.
        
        Args:
            merchant_id: Your Trendyol merchant/seller ID
        """
        self.merchant_id = merchant_id
        self.logger = get_logger('storefront_scraper')
        
        # Trendyol's public search API endpoint
        self.base_url = "https://apigw.trendyol.com/discovery-sfint-search-service/api/search/products/"
        
        # Headers to mimic browser request
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'ro-RO,ro;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Origin': 'https://www.trendyol.com',
            'Referer': f'https://www.trendyol.com/ro/sr?mid={merchant_id}',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-site',
            'X-Request-Source': 'single-search-result'
        }
        
        # Create cloudscraper session to bypass Cloudflare
        self.session = cloudscraper.create_scraper(
            browser={
                'browser': 'chrome',
                'platform': 'darwin',
                'mobile': False
            }
        )
        self.session.headers.update(self.headers)
        
        # Set required cookies for Romania storefront
        self.session.cookies.set('storefrontId', '29', domain='.trendyol.com')
        self.session.cookies.set('language', 'ro', domain='.trendyol.com')
        self.session.cookies.set('countryCode', 'RO', domain='.trendyol.com')
    
    def fetch_all_products(self, max_retries: int = 3) -> List[Dict]:
        """
        Fetch all products from your Trendyol store.
        
        Args:
            max_retries: Maximum number of retry attempts per page
            
        Returns:
            List of product dictionaries with Romanian names
        """
        all_products = []
        page = 1
        page_size = 24
        
        self.logger.info(f"Starting to fetch products for merchant ID: {self.merchant_id}")
        
        while True:
            params = {
                'mid': self.merchant_id,
                'pathModel': 'sr',
                'channelId': '1',
                'culture': 'ro-RO',  # Romanian culture for Romanian names
                'storefrontId': '29',  # 29 = Romania storefront
                'pi': page,
                'pageSize': page_size
            }
            
            retry_count = 0
            success = False
            
            while retry_count < max_retries and not success:
                try:
                    self.logger.info(f"Fetching page {page}...")
                    
                    response = self.session.get(
                        self.base_url,
                        params=params,
                        timeout=30
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        
                        products = data.get('products', [])
                        if not products:
                            self.logger.info(f"No more products found. Total pages: {page - 1}")
                            return all_products
                        
                        # Extract relevant product info
                        for product in products:
                            product_info = {
                                'item_number': product.get('itemNumber'),
                                'content_id': product.get('contentId'),
                                'barcode': product.get('stock', {}).get('barcode') if 'stock' in product else None,
                                'name_romanian': product.get('name', ''),
                                'name_english': product.get('cleanUrlFragments', {}).get('name', ''),
                                'brand': product.get('brand', ''),
                                'price': product.get('price', {}).get('current', 0),
                                'category': product.get('category', {}).get('name', '')
                            }
                            all_products.append(product_info)
                        
                        self.logger.info(f"Page {page}: Found {len(products)} products (Total: {len(all_products)})")
                        
                        success = True
                        page += 1
                        
                        # Be respectful - don't hammer the server
                        time.sleep(1)
                        
                    elif response.status_code == 429:
                        # Rate limited - wait longer
                        wait_time = (retry_count + 1) * 5
                        self.logger.warning(f"Rate limited. Waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        retry_count += 1
                        
                    else:
                        self.logger.error(f"HTTP {response.status_code}: {response.text}")
                        retry_count += 1
                        time.sleep(2)
                        
                except Exception as e:
                    self.logger.error(f"Error fetching page {page}: {e}")
                    retry_count += 1
                    time.sleep(2)
            
            if not success:
                self.logger.error(f"Failed to fetch page {page} after {max_retries} attempts")
                break
        
        return all_products
    
    def build_product_mapping(self, products: List[Dict]) -> Dict[int, Dict]:
        """
        Build a mapping from productCode (itemNumber) to product info.
        
        Args:
            products: List of products from storefront
            
        Returns:
            Dictionary mapping productCode to product info
        """
        mapping = {}
        
        for product in products:
            item_number = product.get('item_number')
            if item_number:
                mapping[item_number] = product
        
        self.logger.info(f"Built mapping for {len(mapping)} products")
        return mapping
    
    def save_product_mapping(self, mapping: Dict[int, Dict], output_file: Path) -> None:
        """
        Save product mapping to JSON file, preserving existing RAZZ codes.
        
        Args:
            mapping: Product mapping dictionary
            output_file: Path to save the mapping
        """
        # Load existing data to preserve RAZZ codes
        existing_data = {}
        if output_file.exists():
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    existing_data = json.load(f)
                self.logger.info(f"Loaded existing data with {len(existing_data)} products")
            except Exception as e:
                self.logger.warning(f"Could not load existing file: {e}")
        
        # Convert int keys to strings for JSON
        json_mapping = {}
        for k, v in mapping.items():
            key_str = str(k)
            
            # If product exists, preserve MDLT code and other important fields
            if key_str in existing_data:
                existing_entry = existing_data[key_str]
                # Preserve existing MDLT code and other fields, only update basic info
                json_mapping[key_str] = {
                    **v,  # New scraped data
                    'mdlt_code': existing_entry.get('mdlt_code', v.get('mdlt_code')),  # Preserve MDLT code
                }
                # Preserve any other custom fields that might exist
                for field in ['mdlt_code', 'stock', 'variants', 'color', 'simplified_name', 'original_romanian']:
                    if field in existing_entry:
                        json_mapping[key_str][field] = existing_entry[field]
            else:
                # New product, use scraped data as-is
                json_mapping[key_str] = v
        
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(json_mapping, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Saved product mapping to: {output_file}")
    
    def get_romanian_name(self, product_code: int, mapping: Dict[int, Dict]) -> Optional[str]:
        """
        Get Romanian product name by product code.
        
        Args:
            product_code: Product code from Trendyol Orders API
            mapping: Product mapping dictionary
            
        Returns:
            Romanian product name or None if not found
        """
        product = mapping.get(product_code)
        if product:
            return product.get('name_romanian')
        return None


def update_product_database(output_dir: Path = None) -> Dict[int, Dict]:
    """
    Main function to update the product database from storefront.
    
    Args:
        output_dir: Directory to save output files
        
    Returns:
        Product mapping dictionary
    """
    if output_dir is None:
        output_dir = Path(__file__).parent / 'data'
    
    scraper = TrendyolStorefrontScraper()
    
    # Fetch all products
    print("🔄 Fetching products from Trendyol storefront...")
    products = scraper.fetch_all_products()
    
    if not products:
        print("❌ No products found!")
        return {}
    
    print(f"✅ Found {len(products)} products")
    
    # Build mapping
    print("🗂️  Building product mapping...")
    mapping = scraper.build_product_mapping(products)
    
    # Save to files
    products_file = output_dir / 'trendyol_products_romanian.json'
    scraper.save_product_mapping(mapping, products_file)
    
    print(f"💾 Saved product mapping to: {products_file}")
    print(f"\n📊 Summary:")
    print(f"   - Total products: {len(products)}")
    print(f"   - With item numbers: {len(mapping)}")
    
    # Show sample
    if products:
        sample = products[0]
        print(f"\n📝 Sample product:")
        print(f"   Item Number: {sample.get('item_number')}")
        print(f"   Romanian: {sample.get('name_romanian')}")
        print(f"   English: {sample.get('name_english')}")
        print(f"   Brand: {sample.get('brand')}")
    
    return mapping


if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    print("=" * 60)
    print("Trendyol Product Name Scraper")
    print("=" * 60)
    print()
    
    mapping = update_product_database()
    
    print()
    print("=" * 60)
    print("✅ Product database updated successfully!")
    print("=" * 60)

