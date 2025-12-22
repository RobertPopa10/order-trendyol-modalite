#!/usr/bin/env python3
"""
Product Name Mapper

Maps Trendyol product names to simplified versions with RAZZ codes.
"""

import json
from pathlib import Path
from typing import Dict, Optional, Tuple
from logging_config import get_logger


class ProductMappingError(Exception):
    """Exception raised when a product mapping is not found."""
    pass


class ProductMapper:
    """Maps products to simplified names and RAZZ codes."""
    
    def __init__(self, data_dir: Path = None, fail_on_missing: bool = True, mapping_file: Path = None):
        """
        Initialize the product mapper.
        
        Args:
            data_dir: Directory containing mapping files (deprecated, use mapping_file)
            fail_on_missing: If True, fail when product mapping not found
            mapping_file: Explicit path to mapping file (overrides data_dir)
        """
        self.logger = get_logger('mapper')
        self.fail_on_missing = fail_on_missing
        
        # Determine mapping file path
        if mapping_file is not None:
            self.name_mapping_file = mapping_file
        elif data_dir is not None:
            self.name_mapping_file = data_dir / 'product_name_mapping.json'
        else:
            # Try to use stockTVA mapping by default
            try:
                from config import get_config
                config = get_config()
                self.name_mapping_file = config.stocktva_mapping_path
                self.logger.info(f"Using stockTVA mapping from: {self.name_mapping_file}")
            except Exception as e:
                self.logger.warning(f"Could not load config, using fallback path: {e}")
                self.name_mapping_file = Path(__file__).parent.parent / 'data' / 'product_name_mapping.json'
        
        # Load product name mappings
        self.name_mapping = self._load_name_mapping()
        
        self.logger.info(f"Product mapper initialized with {len(self.name_mapping)} product mappings")
    
    def _load_name_mapping(self) -> Dict[int, Dict]:
        """
        Load product name mappings from file.
        
        Returns:
            Dictionary mapping product codes to simplified names
        """
        try:
            if not self.name_mapping_file.exists():
                self.logger.warning(f"Product name mapping file not found: {self.name_mapping_file}")
                self.logger.warning("Ensure stockTVA/data/product_name_mapping.json exists or set STOCKTVA_MAPPING_PATH")
                return {}
            
            with open(self.name_mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Check if this is the new code-based format (RAZZ/MDLT) or old Trendyol ID format
            first_key = next(iter(data.keys())) if data else ""
            
            if first_key.startswith('RAZZ-') or first_key.startswith('MDLT-'):
                # New code-based format - create reverse mapping
                code_type = 'MDLT' if first_key.startswith('MDLT-') else 'RAZZ'
                self.logger.info(f"Loading {code_type}-based product mapping format")
                mapping = {}
                
                for product_code, product_info in data.items():
                    trendyol_ids = product_info.get('trendyol_ids', [])
                    
                    # Create mapping for each Trendyol ID
                    for trendyol_id in trendyol_ids:
                        mapping[int(trendyol_id)] = {
                            'simplified_name': product_info.get('simplified_name', ''),
                            'color': product_info.get('color', 'N/A'),
                            'razz_code': product_code,  # Keep field name for compatibility
                            'original_romanian': product_info.get('original_romanian', ''),
                            'stock': product_info.get('stock', 0),
                            'variants': product_info.get('variants', [])
                        }
                
                self.logger.info(f"Created reverse mapping for {len(mapping)} Trendyol IDs from {len(data)} {code_type} codes")
                return mapping
            
            else:
                # Old Trendyol ID format - convert string keys to integers
                self.logger.info("Loading legacy Trendyol ID-based product mapping format")
                mapping = {int(k): v for k, v in data.items()}
                self.logger.info(f"Loaded {len(mapping)} product name mappings")
                return mapping
            
        except Exception as e:
            self.logger.error(f"Error loading product name mapping: {e}")
            return {}
    
    
    def get_product_info(self, product_code: int, romanian_name: str = None) -> Tuple[str, str, str]:
        """
        Get product information from mapping.
        
        Args:
            product_code: Product code from Trendyol
            romanian_name: Romanian product name (for error messages)
            
        Returns:
            Tuple of (simplified_name, color, razz_code)
            
        Raises:
            ProductMappingError: If product code not found and fail_on_missing is True
        """
        if not self.name_mapping:
            error_msg = (
                "Product name mapping is empty! "
                "Ensure stockTVA/data/product_name_mapping.json exists or set STOCKTVA_MAPPING_PATH env variable."
            )
            self.logger.error(error_msg)
            raise ProductMappingError(error_msg)
        
        product_info = self.name_mapping.get(product_code)
        
        if not product_info:
            error_msg = (
                f"Product code {product_code} not found in name mapping!\n"
                f"Romanian name: {romanian_name}\n\n"
                f"Add this product to stockTVA/data/product_name_mapping.json (source file)"
            )
            self.logger.error(error_msg)
            
            if self.fail_on_missing:
                raise ProductMappingError(error_msg)
            else:
                # Return fallback values
                self.logger.warning(f"Using fallback values for product {product_code}")
                fallback_name = romanian_name or f"Product_{product_code}"
                return fallback_name, "N/A", "MISSING"
        
        simplified_name = product_info.get('simplified_name', '')
        color = product_info.get('color', 'N/A')
        razz_code = product_info.get('razz_code', 'MISSING')
        
        if not simplified_name:
            error_msg = f"Simplified name is empty for product code {product_code}!"
            self.logger.error(error_msg)
            
            if self.fail_on_missing:
                raise ProductMappingError(error_msg)
            else:
                simplified_name = romanian_name or f"Product_{product_code}"
        
        self.logger.debug(f"Mapped product {product_code}: '{romanian_name}' -> '{simplified_name}' ({razz_code})")
        return simplified_name, color, razz_code
    
    def map_product(self, product_code: int, romanian_name: str) -> Tuple[str, str, str]:
        """
        Map product to simplified name, color, and RAZZ code.
        
        Args:
            product_code: Product code from Trendyol
            romanian_name: Romanian product name
            
        Returns:
            Tuple of (simplified_name, color, razz_code)
            
        Raises:
            ProductMappingError: If product mapping not found
        """
        return self.get_product_info(product_code, romanian_name)
    
    def get_stats(self) -> Dict:
        """Get statistics about the product mapping."""
        return {
            'total_mapped_products': len(self.name_mapping),
            'mapping_file': str(self.name_mapping_file),
            'file_exists': self.name_mapping_file.exists(),
            'fail_on_missing': self.fail_on_missing
        }
    
    def create_sample_mapping_file(self) -> None:
        """Create a sample product name mapping file."""
        sample_mapping = {
            "1234567890": {
                "simplified_name": "Blender SilverCrest",
                "original_romanian": "Blender de bucătărie profesional 2 în 1 Razo, multifuncțional, 2,5 L, 15 viteze, 4500 W, zdrobire gheață, S",
                "color": "N/A",
                "razz_code": "RAZZ-0060",
                "stock": 0,
                "variants": ["Blender de bucătărie profesional 2 în 1 Razo, multifuncțional, 2,5 L, 15 viteze, 4500 W, zdrobire gheață, S"]
            },
            "0987654321": {
                "simplified_name": "Cos Smart Model Pliabil ROZ",
                "original_romanian": "Cos de gunoi smart cu senzor de miscare, pliabil, 8L - 17.5 L, Alb cu Roz",
                "color": "ROZ",
                "razz_code": "RAZZ-0065",
                "stock": 0,
                "variants": ["Cos de gunoi smart cu senzor de miscare, pliabil, 8L - 17.5 L, Alb cu Roz"]
            }
        }
        
        self.name_mapping_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.name_mapping_file, 'w', encoding='utf-8') as f:
            json.dump(sample_mapping, f, ensure_ascii=False, indent=2)
        
        self.logger.info(f"Created sample mapping file: {self.name_mapping_file}")
        print(f"✅ Created sample mapping file: {self.name_mapping_file}")
        print("\nEdit this file and add your product mappings!")


# Global instance
_mapper_instance = None

def get_product_mapper(fail_on_missing: bool = True) -> ProductMapper:
    """Get global product mapper instance."""
    global _mapper_instance
    if _mapper_instance is None:
        from config import get_config
        config = get_config()
        # Use stockTVA mapping as the source
        _mapper_instance = ProductMapper(mapping_file=config.stocktva_mapping_path, fail_on_missing=fail_on_missing)
    return _mapper_instance


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.INFO)
    
    print("Product Mapper and Color Extractor Test")
    print("=" * 60)
    
    mapper = ProductMapper(fail_on_missing=False)
    
    # Print stats
    stats = mapper.get_stats()
    print(f"\n📊 Statistics:")
    print(f"   Total mapped products: {stats['total_mapped_products']}")
    print(f"   Mapping file: {stats['mapping_file']}")
    print(f"   File exists: {stats['file_exists']}")
    
    if stats['total_mapped_products'] == 0:
        print("\n⚠️  No product mappings found!")
        print("   Creating sample mapping file...")
        mapper.create_sample_mapping_file()
    else:
        # Test product mapping
        print(f"\n🔍 Testing product mapping:")
        test_codes = [1374992710, 1395295371, 1411659050]  # Sample product codes
        
        for code in test_codes:
            try:
                simplified_name, color, razz_code = mapper.map_product(code, f"Test product {code}")
                print(f"   {code} -> '{simplified_name}' | {color} | {razz_code}")
            except ProductMappingError as e:
                print(f"   {code} -> ERROR: Product not found")
    
    print("\n" + "=" * 60)

