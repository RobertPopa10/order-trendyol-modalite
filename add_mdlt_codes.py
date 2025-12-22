#!/usr/bin/env python3
"""
Script to automatically add MDLT codes to scraped products
"""
import json
from pathlib import Path

def add_mdlt_codes():
    """Add MDLT codes to all products in trendyol_products_romanian.json"""
    
    scraped_file = Path("api/data/trendyol_products_romanian.json")
    
    if not scraped_file.exists():
        print(f"❌ File not found: {scraped_file}")
        return False
    
    # Load scraped products
    with open(scraped_file, 'r', encoding='utf-8') as f:
        products = json.load(f)
    
    print(f"📦 Found {len(products)} products")
    
    # Add MDLT codes sequentially
    mdlt_counter = 1
    updated_count = 0
    
    for item_number, product_data in products.items():
        # Skip if already has mdlt_code
        if product_data.get('mdlt_code'):
            print(f"  ℹ️  Product {item_number} already has code: {product_data['mdlt_code']}")
            continue
        
        # Add MDLT code
        mdlt_code = f"MDLT-{mdlt_counter:04d}"
        product_data['mdlt_code'] = mdlt_code
        
        name = product_data.get('name_romanian', 'Unknown')[:60]
        print(f"  ✅ Added {mdlt_code} to: {name}")
        
        mdlt_counter += 1
        updated_count += 1
    
    # Save updated products
    with open(scraped_file, 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    print(f"\n✅ Added MDLT codes to {updated_count} products")
    print(f"💾 Saved to: {scraped_file}")
    
    return True

if __name__ == "__main__":
    success = add_mdlt_codes()
    exit(0 if success else 1)
