#!/usr/bin/env python3
"""
Script to update MDLT-based product_name_mapping.json with latest scraped data from trendyol_products_romanian.json

This script:
1. Updates Romanian names for existing Trendyol IDs (preserves MDLT codes, colors, stock, variants)
2. STOPS and requires manual intervention if new products are found
3. New products must be added to your MDLT-based mapping manually

NOTE: This script now uses the stockTVA/data/product_name_mapping.json as the source of truth.
"""

import json
import sys
from pathlib import Path
from config import get_config

def update_mdlt_based_mapping():
    """Update MDLT-based product name mapping with latest scraped data - PRESERVES MDLT CODES"""
    
    # Get configuration
    config = get_config()
    
    # File paths
    scraped_data_path = Path("api/data/trendyol_products_romanian.json")
    mapping_path = config.stocktva_mapping_path  # Use stockTVA mapping
    
    print(f"📍 Using mapping file: {mapping_path}")
    
    # Load existing MDLT-based mapping
    if mapping_path.exists():
        with open(mapping_path, 'r', encoding='utf-8') as f:
            existing_mapping = json.load(f)
        print(f"📋 Loaded existing MDLT-based mapping with {len(existing_mapping)} MDLT codes")
    else:
        print(f"❌ No existing MDLT-based mapping found at: {mapping_path}")
        print("   Please ensure stockTVA/data/product_name_mapping.json exists")
        return False
    
    # Load scraped data (Trendyol ID -> product info)
    if not scraped_data_path.exists():
        print(f"❌ Scraped data file not found: {scraped_data_path}")
        return False
    
    with open(scraped_data_path, 'r', encoding='utf-8') as f:
        scraped_data = json.load(f)
    
    print(f"🔄 Processing {len(scraped_data)} scraped products...")
    
    # Create reverse lookup: Trendyol ID -> MDLT code
    trendyol_to_mdlt = {}
    for mdlt_code, product_info in existing_mapping.items():
        trendyol_ids = product_info.get('trendyol_ids', [])
        for trendyol_id in trendyol_ids:
            trendyol_to_mdlt[str(trendyol_id)] = mdlt_code
    
    print(f"📋 Built reverse lookup for {len(trendyol_to_mdlt)} Trendyol IDs")
    
    # First, check if products missing MDLT codes are truly NEW (not in existing mapping)
    products_missing_mdlt = []
    
    for item_number, product_data in scraped_data.items():
        romanian_name = product_data.get('name_romanian', '')
        mdlt_code = product_data.get('mdlt_code', '')
        
        if not romanian_name:
            continue
            
        # Check if product is missing MDLT code AND is not in existing mapping
        if not mdlt_code:
            # Only require MDLT code if this is a truly NEW product
            if item_number not in trendyol_to_mdlt:
                products_missing_mdlt.append({
                    'item_number': item_number,
                    'name_romanian': romanian_name,
                    'name_english': product_data.get('name_english', ''),
                    'price': product_data.get('price', ''),
                    'category': product_data.get('category', '')
                })
            else:
                print(f"ℹ️  Product {item_number} exists in mapping but missing mdlt_code in scraped data (will update anyway)")
    
    # If any products are missing MDLT codes, stop and require manual intervention
    if products_missing_mdlt:
        print(f"\n🚨 ERROR: {len(products_missing_mdlt)} PRODUCTS MISSING MDLT CODES!")
        print("=" * 80)
        print("🚨 MANUAL ACTION REQUIRED:")
        print("   Products in trendyol_products_romanian.json are missing 'mdlt_code' fields!")
        print("   You must manually add MDLT codes to these products:")
        print("=" * 80)
        
        for i, product in enumerate(products_missing_mdlt[:10]):  # Show first 10
            print(f"   {i+1}. ID: {product['item_number']}")
            print(f"      Name: {product['name_romanian']}")
            print(f"      Category: {product.get('category', 'N/A')}")
            print(f"      → Add: \"mdlt_code\": \"MDLT-XXXX\"")
            print()
        
        if len(products_missing_mdlt) > 10:
            print(f"   ... and {len(products_missing_mdlt) - 10} more")
        
        print("=" * 80)
        print("   1. Edit api/data/trendyol_products_romanian.json")
        print("   2. Add 'mdlt_code' field to each product above")
        print("   3. Run this script again")
        print("=" * 80)
        
        return False
    
    # All products have MDLT codes, proceed with update
    updated_count = 0
    new_products = []
    
    for item_number, product_data in scraped_data.items():
        romanian_name = product_data.get('name_romanian', '')
        scraped_mdlt_code = product_data.get('mdlt_code', '')
        
        if not romanian_name:
            continue
            
        # Check if this Trendyol ID exists in our MDLT mapping
        if item_number in trendyol_to_mdlt:
            existing_mdlt_code = trendyol_to_mdlt[item_number]
            existing_entry = existing_mapping[existing_mdlt_code]
            
            # Update Romanian name if changed - PRESERVE ALL OTHER FIELDS
            if existing_entry.get('original_romanian', '') != romanian_name:
                print(f"🔄 Updating Romanian name for {existing_mdlt_code} (Trendyol ID: {item_number})")
                existing_entry['original_romanian'] = romanian_name
                
                # Update variants - ensure this Romanian name is in the variants list
                variants = existing_entry.get('variants', [])
                if romanian_name not in variants:
                    variants.append(romanian_name)
                    existing_entry['variants'] = variants
                
                updated_count += 1
        elif scraped_mdlt_code:
            # NEW PRODUCT FOUND with MDLT code - Add to mapping
            if scraped_mdlt_code not in existing_mapping:
                # Create new MDLT code entry
                existing_mapping[scraped_mdlt_code] = {
                    'simplified_name': romanian_name,  # Use Romanian name as simplified name initially
                    'color': 'N/A',
                    'original_romanian': romanian_name,
                    'stock': 0,
                    'trendyol_ids': [item_number],
                    'variants': [romanian_name]
                }
                print(f"✅ Added new product: {scraped_mdlt_code} - {romanian_name}")
                updated_count += 1
            else:
                # MDLT code exists, add this Trendyol ID to it
                existing_entry = existing_mapping[scraped_mdlt_code]
                if item_number not in existing_entry['trendyol_ids']:
                    existing_entry['trendyol_ids'].append(item_number)
                    if romanian_name not in existing_entry['variants']:
                        existing_entry['variants'].append(romanian_name)
                    print(f"✅ Added Trendyol ID {item_number} to existing {scraped_mdlt_code}")
                    updated_count += 1
        # If no scraped_razz_code and not in existing mapping, it was already caught above
    
    # Handle new products
    if new_products:
        print(f"\n🚨 FOUND {len(new_products)} NEW PRODUCTS!")
        print("=" * 80)
        print("🚨 MANUAL ACTION REQUIRED:")
        print("   1. Review the new products in 'data/new_products_need_mdlt_codes.json'")
        print("   2. Add them to your MDLT-based mapping with appropriate MDLT codes")
        print("   3. Then run this update script again")
        print("=" * 80)
        
        # Save new products to a file for review
        new_products_file = Path("data/new_products_need_mdlt_codes.json")
        with open(new_products_file, 'w', encoding='utf-8') as f:
            json.dump(new_products, f, ensure_ascii=False, indent=2)
        
        print(f"💾 Saved {len(new_products)} new products to: {new_products_file}")
        
        # Show first few new products
        print(f"\n📋 First few new products:")
        for i, product in enumerate(new_products[:5]):
            print(f"   {i+1}. {product['item_number']}: {product['name_romanian']}")
        
        if len(new_products) > 5:
            print(f"   ... and {len(new_products) - 5} more")
        
        return False  # Don't save mapping until new products are handled
    
    # Save updated mapping
    if updated_count > 0:
        print(f"\n💾 Saving updated mapping with {updated_count} changes...")
        with open(mapping_path, 'w', encoding='utf-8') as f:
            json.dump(existing_mapping, f, ensure_ascii=False, indent=2)
        print(f"✅ Successfully updated {updated_count} products")
    else:
        print("✅ No updates needed - all products are up to date")
    
    # Summary
    total_trendyol_ids = sum(len(product_info.get('trendyol_ids', [])) for product_info in existing_mapping.values())
    print(f"\n📊 Summary:")
    print(f"   Total MDLT codes: {len(existing_mapping)}")
    print(f"   Total Trendyol IDs: {total_trendyol_ids}")
    print(f"   Products updated: {updated_count}")
    print(f"   New products found: {len(new_products)}")
    
    return True

if __name__ == "__main__":
    success = update_mdlt_based_mapping()
    if not success:
        sys.exit(1)
