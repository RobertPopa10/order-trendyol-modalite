#!/usr/bin/env python3
"""
Migration script to update product_name_mapping.json with RAZZ codes and proper structure.

This script:
1. Reads the current product_name_mapping.json
2. Loads the holy grail simplified_name_to_code_mapping.txt
3. Updates simplified names to match the holy grail
4. Adds razz_code from the holy grail
5. Extracts color from simplified names
6. Adds stock field (default 0)
7. Keeps the exact order of entries
"""

import json
import re
from pathlib import Path
from typing import Dict, Optional


def load_holy_grail_mapping(file_path: Path) -> Dict[str, str]:
    """Load the holy grail simplified_name -> RAZZ code mapping."""
    mapping = {}
    
    with open(file_path, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line or line.startswith('#'):
                continue
                
            if ' -> ' in line:
                name, code = line.split(' -> ', 1)
                name = name.strip()
                code = code.strip()
                mapping[name] = code
            else:
                print(f"Warning: Line {line_num} doesn't match expected format: {line}")
    
    print(f"Loaded {len(mapping)} entries from holy grail mapping")
    return mapping


def extract_color_from_simplified_name(simplified_name: str) -> str:
    """Extract color from simplified name (last word if it's a color)."""
    
    # Common colors that appear in your simplified names
    colors = [
        'Negru', 'Alb', 'Alba', 'Albastru', 'Verde', 'Rosu', 'Roz', 'Gri', 
        'Bej', 'Aurie', 'Argintiu', 'Multicolor', 'Mov', 'NEGRU', 'ALB',
        'ALBASTRU', 'VERDE', 'ROSU', 'ROZ', 'CLASIC'
    ]
    
    # Check if the simplified name ends with a color
    words = simplified_name.split()
    if len(words) > 1:
        last_word = words[-1]
        # Remove trailing punctuation
        last_word_clean = re.sub(r'[^\w]', '', last_word)
        
        if last_word_clean in colors:
            return last_word_clean
    
    # Check for colors anywhere in the name (for compound names)
    for color in colors:
        if color in simplified_name:
            return color
    
    return "N/A"


def find_best_match(current_simplified: str, holy_grail: Dict[str, str]) -> Optional[str]:
    """Find the best match for current simplified name in holy grail."""
    
    # Exact match first
    if current_simplified in holy_grail:
        return current_simplified
    
    # Try to find partial matches
    current_lower = current_simplified.lower()
    
    # Look for matches by removing common variations
    for holy_name in holy_grail.keys():
        holy_lower = holy_name.lower()
        
        # Check if it's a close match (same base product)
        current_words = set(current_lower.split())
        holy_words = set(holy_lower.split())
        
        # If most words match, it's probably the same product
        common_words = current_words.intersection(holy_words)
        if len(common_words) >= min(len(current_words), len(holy_words)) * 0.6:
            return holy_name
    
    return None


def migrate_product_mapping():
    """Main migration function."""
    
    # File paths
    current_mapping_file = Path('data/product_name_mapping.json')
    holy_grail_file = Path('data/simplified_name_to_code_mapping.txt')
    backup_file = Path('data/product_name_mapping_backup.json')
    
    # Load files
    print("Loading current product mapping...")
    with open(current_mapping_file, 'r', encoding='utf-8') as f:
        current_mapping = json.load(f)
    
    print("Loading holy grail mapping...")
    holy_grail = load_holy_grail_mapping(holy_grail_file)
    
    # Create backup
    print("Creating backup...")
    with open(backup_file, 'w', encoding='utf-8') as f:
        json.dump(current_mapping, f, ensure_ascii=False, indent=2)
    
    # Statistics
    stats = {
        'total_products': len(current_mapping),
        'exact_matches': 0,
        'partial_matches': 0,
        'no_matches': 0,
        'updated_names': 0,
        'colors_extracted': 0
    }
    
    # Process each product (keeping order)
    print("\nProcessing products...")
    
    for product_id, product_info in current_mapping.items():
        current_simplified = product_info.get('simplified_name', '')
        
        # Find match in holy grail
        matched_name = find_best_match(current_simplified, holy_grail)
        
        if matched_name:
            if matched_name == current_simplified:
                stats['exact_matches'] += 1
            else:
                stats['partial_matches'] += 1
                stats['updated_names'] += 1
                print(f"  Updated: '{current_simplified}' -> '{matched_name}'")
            
            # Update simplified name and add razz code
            product_info['simplified_name'] = matched_name
            product_info['razz_code'] = holy_grail[matched_name]
        else:
            stats['no_matches'] += 1
            print(f"  No match found for: '{current_simplified}' (Product ID: {product_id})")
            # Keep original name, no razz code
            product_info['razz_code'] = "MISSING"
        
        # Extract color from simplified name
        color = extract_color_from_simplified_name(product_info['simplified_name'])
        if color != "N/A":
            stats['colors_extracted'] += 1
        
        # Update the structure
        product_info['color'] = color
        product_info['stock'] = 0  # Default stock
        
        # Ensure order: simplified_name, original_romanian, color, razz_code, stock, variants
        ordered_info = {
            'simplified_name': product_info['simplified_name'],
            'original_romanian': product_info.get('original_romanian', ''),
            'color': product_info['color'],
            'razz_code': product_info['razz_code'],
            'stock': product_info['stock'],
            'variants': [product_info.get('original_romanian', '')] if product_info.get('original_romanian', '') else []
        }
        
        # Update in place to preserve order
        current_mapping[product_id] = ordered_info
    
    # Save updated mapping
    print("\nSaving updated mapping...")
    with open(current_mapping_file, 'w', encoding='utf-8') as f:
        json.dump(current_mapping, f, ensure_ascii=False, indent=2)
    
    # Print statistics
    print(f"\n{'='*60}")
    print("MIGRATION COMPLETE")
    print(f"{'='*60}")
    print(f"Total products processed: {stats['total_products']}")
    print(f"Exact matches: {stats['exact_matches']}")
    print(f"Partial matches (updated): {stats['partial_matches']}")
    print(f"No matches found: {stats['no_matches']}")
    print(f"Names updated: {stats['updated_names']}")
    print(f"Colors extracted: {stats['colors_extracted']}")
    print(f"\nBackup saved to: {backup_file}")
    print(f"Updated mapping saved to: {current_mapping_file}")
    
    if stats['no_matches'] > 0:
        print(f"\n⚠️  {stats['no_matches']} products need manual review (marked with 'MISSING' razz_code)")


if __name__ == "__main__":
    migrate_product_mapping()
