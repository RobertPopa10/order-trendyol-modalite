#!/usr/bin/env python3
"""
Split and Reorder AWBs

Takes a single large PDF with multiple AWB labels and reorders them to match Excel.
"""

import re
from pathlib import Path
from typing import List, Dict
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter, PdfMerger
import json

from config import get_config
from logging_config import get_logger


def extract_tracking_from_page(page_text):
    """
    Extract tracking number from page text using multiple patterns.
    """
    # Get logger for this function
    logger = get_logger('awb_split_reorder')
    
    # Clean and normalize text first
    cleaned_text = ' '.join(page_text.split())
    
    # Log the full page text to see what we're working with
    logger.debug(f"Full page text for AWB extraction: {cleaned_text}")
    
    # Multiple regex patterns to catch different AWB formats
    # Order from most specific to least specific
    patterns = [
        r'REFERENCE[:\s]*\(FAN\)(\d{10,11})',  # REFERENCE: (FAN)number - most specific first
        r'REFERENCE[:\s]*(\d{10,11})',         # REFERENCE: number
        r'AWB[:\s]*(\d{10,11})',              # AWB: followed by number
        r'\(FAN\)(\d{10,11})',                # (FAN)number
        r'\b(\d{10,11})\b',                   # Any 10-11 digit number with word boundaries
    ]
    
    # Try each pattern
    for pattern in patterns:
        matches = re.findall(pattern, cleaned_text, re.IGNORECASE)
        for match in matches:
            # Extract just the numeric part if it's a tuple
            number = match if isinstance(match, str) else match
            # Validate it's a proper AWB number (10-11 digits, reasonable range)
            if len(number) >= 10 and number.isdigit():
                # Additional validation: AWB numbers are typically in a reasonable range
                # and don't start with 0 or 1 (too low) or 9 (too high for most couriers)
                first_digit = number[0]
                if first_digit in '23456789':  # Reasonable AWB prefixes
                    logger.debug(f"Pattern '{pattern}' found AWB: {number}")
                    return number
    
    logger.debug(f"No AWB found in text. Full text was: {cleaned_text}")
    return None


def split_and_reorder_pdf(input_pdf: Path, orders_list: List[Dict], output_path: Path) -> Dict:
    """
    Split a multi-page PDF and reorder pages to match orders.
    
    Args:
        input_pdf: Path to the large PDF with all labels
        orders_list: List of orders (from orders_list JSON)
        output_path: Where to save the reordered PDF
        
    Returns:
        Dict with validation results: {
            'success': bool,
            'total_orders': int,
            'matched_awbs': int,
            'missing_awbs': int,
            'validation_passed': bool,
            'error': str (if any)
        }
    """
    # Initialize logger at function level
    logger = get_logger('awb_split_reorder')
    
    # Load ignored orders configuration
    config = get_config()
    ignored_orders = config.ignored_orders
    if ignored_orders:
        logger.info(f"Ignoring {len(ignored_orders)} orders: {ignored_orders}")
    
    try:
        logger.info(f"Reading PDF: {input_pdf}")
        reader = PdfReader(str(input_pdf))
        total_pages = len(reader.pages)
        logger.info(f"Found {total_pages} pages in PDF")
    except Exception as e:
        error_msg = f"Failed to read PDF {input_pdf}: {e}"
        logger.error(error_msg)
        return {
            'success': False,
            'error': error_msg,
            'total_orders': 0,
            'matched_awbs': 0,
            'missing_awbs': 0,
            'validation_passed': False
        }
    
    try:
        # Extract tracking number from each page
        page_tracking_map = {}  # page_num -> tracking_number
        tracking_page_map = {}  # tracking_number -> page_num
        
        for page_num in range(total_pages):
            # Extract text from the page first
            page_text = reader.pages[page_num].extract_text()
            tracking = extract_tracking_from_page(page_text)
            if tracking:
                page_tracking_map[page_num] = tracking
                tracking_page_map[tracking] = page_num
                logger.debug(f"Page {page_num + 1}: Found tracking {tracking}")
                # Special logging for the problematic AWB
                if tracking == "4185395850":
                    logger.info(f"✅ FOUND Irimia Cosmina AWB 4185395850 on page {page_num+1}")
            elif "Irimia" in page_text or "4185395850" in page_text:
                logger.warning(f"❌ Page {page_num+1} contains 'Irimia' or '4185395850' but AWB not extracted!")
                logger.warning(f"Page preview: {page_text[:500]}...")
        
        logger.info(f"Extracted tracking numbers from {len(page_tracking_map)} pages")
        
        # Log all found tracking numbers for debugging
        logger.debug(f"All found tracking numbers: {sorted(tracking_page_map.keys())}")
        
        # Deduplicate orders by tracking number (keep first occurrence for order)
        # Also filter out ignored orders from AWB processing
        seen_tracking = {}
        unique_orders = []
        ignored_count = 0
        
        for idx, order in enumerate(orders_list):
            order_number = str(order.get('order_number', ''))
            tracking = str(order.get('cargo_tracking_number', ''))
            
            # Skip ignored orders for AWB processing (but they remain in Excel)
            if order_number in ignored_orders:
                ignored_count += 1
                logger.info(f"Skipping ignored order #{order_number} for AWB processing")
                continue
            
            if tracking and tracking not in seen_tracking:
                seen_tracking[tracking] = True
                unique_orders.append({
                    'idx': idx,
                    'tracking': tracking,
                    'customer': order.get('customer_name', 'Unknown'),
                    'order_number': order.get('order_number', 'Unknown')
                })
        
        logger.info(f"Unique orders by AWB: {len(unique_orders)} (from {len(orders_list)} items)")
        if ignored_count > 0:
            logger.info(f"Ignored {ignored_count} orders from AWB processing")
        
        # Debug: Show what AWBs we're looking for
        order_awbs = [order['tracking'] for order in unique_orders]
        pdf_awbs = sorted(tracking_page_map.keys())
        logger.debug(f"Looking for AWBs: {sorted(order_awbs)}")
        logger.debug(f"Found in PDF AWBs: {pdf_awbs}")
        
        # Build order -> page mapping
        matched_pages = []
        missing_orders = []
        
        for order in unique_orders:
            tracking = order['tracking']
            if tracking in tracking_page_map:
                page_num = tracking_page_map[tracking]
                matched_pages.append({
                    'order_idx': order['idx'],
                    'page_num': page_num,
                    'tracking': tracking,
                    'customer': order['customer']
                })
                logger.debug(f"✓ {order['customer']} (#{order['order_number']}) -> Page {page_num + 1}")
            else:
                missing_orders.append(order)
                logger.warning(f"✗ {order['customer']} (#{order['order_number']}) - AWB {tracking} not found")
        
        # Create reordered PDF
        writer = PdfWriter()
        
        for match in matched_pages:
            writer.add_page(reader.pages[match['page_num']])
        
        # Save
        with open(output_path, 'wb') as f:
            writer.write(f)
        
        # Summary
        logger.info("=" * 60)
        logger.info("✅ AWB Reorder Complete!")
        logger.info(f"  Output: {output_path.name}")
        logger.info(f"  Total items: {len(orders_list)} | Unique orders: {len(unique_orders)}")
        if ignored_count > 0:
            logger.info(f"  Ignored orders: {ignored_count}")
        logger.info(f"  Matched: {len(matched_pages)} AWBs")
        if missing_orders:
            logger.warning(f"  Missing: {len(missing_orders)} AWBs")
        logger.info("=" * 60)
        
        if missing_orders:
            logger.warning(f"\n⚠️  {len(missing_orders)} orders missing from PDF:")
            for missing in missing_orders[:10]:  # Show first 10
                logger.warning(f"  - {missing['customer']} (AWB: {missing['tracking']})")
            if len(missing_orders) > 10:
                logger.warning(f"  ... and {len(missing_orders) - 10} more")
        
        # Validation: Check if all AWBs are present
        validation_passed = len(missing_orders) == 0
        
        return {
            'success': True,
            'output_path': output_path,
            'total_orders': len(unique_orders),
            'matched_awbs': len(matched_pages),
            'missing_awbs': len(missing_orders),
            'validation_passed': validation_passed,
            'missing_orders': missing_orders
        }
    
    except Exception as e:
        error_msg = f"Failed to process AWB reordering: {e}"
        try:
            logger.error(error_msg)
        except:
            print(f"ERROR: {error_msg}")  # Fallback if logger fails
        return {
            'success': False,
            'error': error_msg,
            'total_orders': 0,
            'matched_awbs': 0,
            'missing_awbs': 0,
            'validation_passed': False
        }


def main():
    """Main function."""
    config = get_config()
    logger = get_logger('main')
    
    input_dir = Path(__file__).parent / "input"
    output_dir = config.output_dir
    
    # Find ALL PDFs in input/
    pdf_files = sorted(input_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
    if not pdf_files:
        print(f"❌ No PDF files found in {input_dir}")
        print(f"   Put your AWB PDFs in: {input_dir}")
        return
    
    # Merge if multiple PDFs
    if len(pdf_files) > 1:
        logger.info(f"Found {len(pdf_files)} PDFs, merging...")
        merger = PdfMerger()
        for pdf in pdf_files:
            logger.info(f"  + {pdf.name}")
            merger.append(str(pdf))
        
        merged_path = input_dir / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        merger.write(str(merged_path))
        merger.close()
        
        input_pdf = merged_path
        logger.info(f"Merged to: {merged_path.name}")
    else:
        input_pdf = pdf_files[0]
        logger.info(f"Using: {input_pdf.name}")
    
    # Find latest orders list
    order_lists = sorted(output_dir.glob("orders_list_*.json"), reverse=True)
    if not order_lists:
        print("❌ No orders list found. Run 'python main.py' first.")
        return
    
    orders_file = order_lists[0]
    logger.info(f"Using orders: {orders_file.name}")
    
    # Load orders
    with open(orders_file, 'r', encoding='utf-8') as f:
        orders = json.load(f)
    
    logger.info(f"Loaded {len(orders)} orders")
    
    # Output
    timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
    output_path = output_dir / f"awb_labels_reordered_{timestamp}.pdf"
    
    # Process
    result = split_and_reorder_pdf(input_pdf, orders, output_path)
    
    if result['success'] and result['validation_passed']:
        print(f"\n✅ Reordered AWBs: {result['output_path']}")
        print(f"✅ Validation PASSED: {result['matched_awbs']}/{result['total_orders']} AWBs matched")
    else:
        print(f"\n❌ AWB Validation FAILED: {result['matched_awbs']}/{result['total_orders']} AWBs matched")
        print(f"Missing {result['missing_awbs']} AWB(s)")
        exit(1)


if __name__ == "__main__":
    main()

