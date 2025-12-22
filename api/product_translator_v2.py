#!/usr/bin/env python3
"""
Automatic Product Name Translation Service (V2)

Uses product codes to automatically fetch Romanian names from Trendyol storefront data.
No more manual mapping required!
"""

import json
from pathlib import Path
from typing import Dict, Optional
from logging_config import get_logger


class ProductTranslationError(Exception):
    """Exception raised when a product name cannot be translated."""
    pass


class AutomaticProductTranslator:
    """Automatically translates product names using storefront data."""
    
    def __init__(self, data_dir: Path = None):
        """
        Initialize the automatic translator.
        
        Args:
            data_dir: Directory containing the product mapping file
        """
        if data_dir is None:
            data_dir = Path(__file__).parent / 'data'
        
        self.logger = get_logger('auto_translator')
        self.data_dir = data_dir
        self.mapping_file = data_dir / 'trendyol_products_romanian.json'
        
        # Load product mapping
        self.product_mapping = self._load_product_mapping()
        
        self.logger.info(f"Automatic translator initialized with {len(self.product_mapping)} products")
    
    def _load_product_mapping(self) -> Dict[int, Dict]:
        """
        Load product mapping from storefront data.
        
        Returns:
            Dictionary mapping product codes to product info
        """
        try:
            if not self.mapping_file.exists():
                self.logger.warning(f"Product mapping file not found: {self.mapping_file}")
                self.logger.warning("Run trendyol_storefront_scraper.py to create it")
                return {}
            
            with open(self.mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Convert string keys back to integers
            mapping = {int(k): v for k, v in data.items()}
            
            self.logger.info(f"Loaded {len(mapping)} products from storefront data")
            return mapping
            
        except Exception as e:
            self.logger.error(f"Error loading product mapping: {e}")
            return {}
    
    def reload_mapping(self) -> None:
        """Reload product mapping from file."""
        self.product_mapping = self._load_product_mapping()
        self.logger.info("Product mapping reloaded")
    
    def translate_by_product_code(self, product_code: int, 
                                  english_name: str = None) -> str:
        """
        Translate product name using product code.
        
        Args:
            product_code: Product code from Trendyol Orders API
            english_name: English product name (for fallback/logging)
            
        Returns:
            Romanian product name
            
        Raises:
            ProductTranslationError: If product code not found in mapping
        """
        if not self.product_mapping:
            error_msg = (
                "Product mapping is empty! "
                "Run 'python trendyol_storefront_scraper.py' to fetch product names."
            )
            self.logger.error(error_msg)
            raise ProductTranslationError(error_msg)
        
        product_info = self.product_mapping.get(product_code)
        
        if not product_info:
            error_msg = (
                f"Product code {product_code} not found in mapping!\n"
                f"English name: {english_name}\n\n"
                f"This product might be new or the mapping is outdated.\n"
                f"Run 'python trendyol_storefront_scraper.py' to update."
            )
            self.logger.error(error_msg)
            raise ProductTranslationError(error_msg)
        
        romanian_name = product_info.get('name_romanian', '')
        
        if not romanian_name:
            error_msg = (
                f"Romanian name is empty for product code {product_code}!\n"
                f"English name: {english_name}"
            )
            self.logger.error(error_msg)
            raise ProductTranslationError(error_msg)
        
        self.logger.debug(f"Translated product {product_code}: '{english_name}' -> '{romanian_name}'")
        return romanian_name
    
    def get_product_info(self, product_code: int) -> Optional[Dict]:
        """
        Get full product information by product code.
        
        Args:
            product_code: Product code from Trendyol Orders API
            
        Returns:
            Product information dictionary or None
        """
        return self.product_mapping.get(product_code)
    
    def get_stats(self) -> Dict:
        """Get statistics about the product mapping."""
        total_products = len(self.product_mapping)
        products_with_romanian = sum(
            1 for p in self.product_mapping.values() 
            if p.get('name_romanian')
        )
        
        return {
            'total_products': total_products,
            'products_with_romanian_names': products_with_romanian,
            'mapping_file': str(self.mapping_file),
            'file_exists': self.mapping_file.exists(),
            'coverage_percentage': (products_with_romanian / total_products * 100) 
                                   if total_products > 0 else 0
        }


# Global instance
_translator_instance = None

def get_auto_translator() -> AutomaticProductTranslator:
    """Get global automatic translator instance."""
    global _translator_instance
    if _translator_instance is None:
        from pathlib import Path
        # Use api/data directory for translator (where trendyol_products_romanian.json is stored)
        api_data_dir = Path(__file__).parent / 'data'
        _translator_instance = AutomaticProductTranslator(data_dir=api_data_dir)
    return _translator_instance


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Automatic Product Translator Test")
    print("=" * 60)
    
    translator = AutomaticProductTranslator()
    
    # Print stats
    stats = translator.get_stats()
    print(f"\n📊 Statistics:")
    print(f"   Total products: {stats['total_products']}")
    print(f"   With Romanian names: {stats['products_with_romanian_names']}")
    print(f"   Coverage: {stats['coverage_percentage']:.1f}%")
    print(f"   Mapping file: {stats['mapping_file']}")
    print(f"   File exists: {stats['file_exists']}")
    
    if stats['total_products'] == 0:
        print("\n⚠️  No products found in mapping!")
        print("   Run: python trendyol_storefront_scraper.py")
    else:
        # Test translation with a sample product
        print(f"\n🧪 Testing translation...")
        
        # Get first product code
        sample_code = list(translator.product_mapping.keys())[0]
        sample_product = translator.product_mapping[sample_code]
        
        print(f"\n   Product Code: {sample_code}")
        print(f"   English: {sample_product['name_english']}")
        
        try:
            romanian = translator.translate_by_product_code(
                sample_code, 
                sample_product['name_english']
            )
            print(f"   Romanian: {romanian}")
            print("\n✅ Translation successful!")
        except ProductTranslationError as e:
            print(f"\n❌ Translation failed: {e}")

