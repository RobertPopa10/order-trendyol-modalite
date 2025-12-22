#!/usr/bin/env python3
"""
AWB PDF Reorder Tool

Takes manually downloaded AWB PDFs from Trendyol and reorders them
to match the Excel order list.
"""

import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
from PyPDF2 import PdfReader, PdfMerger, PdfWriter
import json

from config import get_config
from logging_config import get_logger


class AWBReorder:
    """Reorders AWB PDFs to match Excel order."""
    
    def __init__(self):
        """Initialize AWB reorder tool."""
        self.config = get_config()
        self.logger = get_logger('awb_reorder')
        self.output_dir = self.config.output_dir
        
        # Input folder for downloaded PDFs (relative to project root)
        self.input_dir = Path(__file__).parent / "input"
        self.input_dir.mkdir(exist_ok=True)
        
        self.logger.info(f"AWB Reorder initialized")
        self.logger.info(f"  Input folder: {self.input_dir}")
        self.logger.info(f"  Output folder: {self.output_dir}")
    
    def extract_identifiers_from_pdf(self, pdf_path: Path) -> Dict[str, str]:
        """
        Extract tracking number and package ID from PDF.
        
        Args:
            pdf_path: Path to PDF file
            
        Returns:
            Dict with extracted identifiers
        """
        identifiers = {
            'tracking_number': None,
            'package_id': None,
            'filename': pdf_path.name
        }
        
        try:
            # Try to extract from filename first
            # Common patterns: packageId_trackingNum.pdf, trackingNum.pdf, etc.
            filename = pdf_path.stem
            
            # Pattern 1: package_id_tracking.pdf or similar
            match = re.search(r'(\d{10})', filename)
            if match:
                # 10-digit number is likely package ID
                identifiers['package_id'] = match.group(1)
            
            # Pattern 2: tracking number (usually 10 digits starting with 4)
            match = re.search(r'(41\d{8})', filename)
            if match:
                identifiers['tracking_number'] = match.group(1)
            
            # If not in filename, try to extract from PDF text
            if not identifiers['tracking_number'] or not identifiers['package_id']:
                reader = PdfReader(str(pdf_path))
                text = ""
                for page in reader.pages[:2]:  # Check first 2 pages
                    text += page.extract_text()
                
                # Look for tracking number in text
                if not identifiers['tracking_number']:
                    match = re.search(r'(41\d{8,10})', text)
                    if match:
                        identifiers['tracking_number'] = match.group(1)
                
                # Look for package ID
                if not identifiers['package_id']:
                    match = re.search(r'Package.*?(\d{10})', text, re.IGNORECASE)
                    if match:
                        identifiers['package_id'] = match.group(1)
                    else:
                        # Try any 10-digit number
                        match = re.search(r'(\d{10})', text)
                        if match:
                            identifiers['package_id'] = match.group(1)
            
            self.logger.debug(f"Extracted from {pdf_path.name}: {identifiers}")
            
        except Exception as e:
            self.logger.warning(f"Failed to extract identifiers from {pdf_path.name}: {e}")
        
        return identifiers
    
    def match_pdf_to_order(self, pdf_identifiers: Dict, orders: List[Dict]) -> Optional[int]:
        """
        Match a PDF to an order in the list.
        
        Args:
            pdf_identifiers: Extracted identifiers from PDF
            orders: List of order dictionaries
            
        Returns:
            Index of matching order, or None
        """
        tracking = pdf_identifiers.get('tracking_number')
        package_id = pdf_identifiers.get('package_id')
        
        for idx, order in enumerate(orders):
            order_tracking = str(order.get('cargo_tracking_number', ''))
            order_package = str(order.get('package_id', ''))
            
            # Match by tracking number (preferred)
            if tracking and order_tracking and tracking == order_tracking:
                return idx
            
            # Match by package ID
            if package_id and order_package and package_id == order_package:
                return idx
        
        return None
    
    def reorder_pdfs(self, orders: List[Dict], input_folder: Path = None, output_filename: str = None) -> Path:
        """
        Reorder downloaded PDFs to match order list.
        
        Args:
            orders: List of order dictionaries (same order as Excel)
            input_folder: Folder containing downloaded PDFs (default: awb_downloads/)
            output_filename: Output filename (optional)
            
        Returns:
            Path to reordered PDF
        """
        # Load ignored orders configuration
        ignored_orders = self.config.ignored_orders
        if ignored_orders:
            self.logger.info(f"Ignoring {len(ignored_orders)} orders: {ignored_orders}")
        
        # Filter out ignored orders from processing
        filtered_orders = []
        ignored_count = 0
        
        for order in orders:
            order_number = str(order.get('order_number', ''))
            if order_number in ignored_orders:
                ignored_count += 1
                self.logger.info(f"Skipping ignored order #{order_number} for AWB processing")
                continue
            filtered_orders.append(order)
        
        if ignored_count > 0:
            self.logger.info(f"Filtered out {ignored_count} ignored orders. Processing {len(filtered_orders)} orders.")
        
        orders = filtered_orders  # Use filtered orders for the rest of the processing
        
        if input_folder is None:
            input_folder = self.input_dir
        else:
            input_folder = Path(input_folder)
        
        if not input_folder.exists():
            raise ValueError(f"Input folder does not exist: {input_folder}")
        
        # Find all PDFs in input folder
        pdf_files = list(input_folder.glob("*.pdf"))
        
        if not pdf_files:
            raise ValueError(f"No PDF files found in {input_folder}")
        
        self.logger.info(f"Found {len(pdf_files)} PDF files in {input_folder}")
        self.logger.info(f"Need to match {len(orders)} orders")
        
        # Extract identifiers from each PDF
        pdf_data = []
        for pdf_path in pdf_files:
            identifiers = self.extract_identifiers_from_pdf(pdf_path)
            pdf_data.append({
                'path': pdf_path,
                'identifiers': identifiers
            })
        
        # Match PDFs to orders
        order_pdf_map = {}  # order_index -> pdf_path
        unmatched_pdfs = []
        
        for pdf in pdf_data:
            matched_idx = self.match_pdf_to_order(pdf['identifiers'], orders)
            if matched_idx is not None:
                order_pdf_map[matched_idx] = pdf['path']
                self.logger.info(f"  ✓ Matched {pdf['path'].name} to order #{matched_idx + 1}")
            else:
                unmatched_pdfs.append(pdf['path'])
                self.logger.warning(f"  ✗ Could not match {pdf['path'].name}")
        
        if not order_pdf_map:
            raise ValueError("No PDFs could be matched to orders")
        
        # Create merged PDF in order
        pdf_merger = PdfMerger()
        matched_count = 0
        missing_count = 0
        
        for idx, order in enumerate(orders):
            if idx in order_pdf_map:
                pdf_path = order_pdf_map[idx]
                try:
                    pdf_merger.append(str(pdf_path))
                    matched_count += 1
                    self.logger.debug(f"Added order #{idx + 1}: {pdf_path.name}")
                except Exception as e:
                    self.logger.error(f"Failed to add {pdf_path.name}: {e}")
            else:
                missing_count += 1
                customer = order.get('customer_name', 'Unknown')
                tracking = order.get('cargo_tracking_number', 'N/A')
                self.logger.warning(f"Missing PDF for order #{idx + 1}: {customer} (AWB: {tracking})")
        
        # Generate output filename
        if not output_filename:
            timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
            output_filename = f"awb_labels_reordered_{timestamp}.pdf"
        
        if not output_filename.endswith('.pdf'):
            output_filename += '.pdf'
        
        output_path = self.output_dir / output_filename
        
        # Save merged PDF
        with open(output_path, 'wb') as f:
            pdf_merger.write(f)
        
        pdf_merger.close()
        
        # Log summary
        self.logger.info("=" * 60)
        self.logger.info(f"AWB PDF Reordering Complete!")
        self.logger.info(f"  Output: {output_path}")
        self.logger.info(f"  Matched: {matched_count}/{len(orders)}")
        self.logger.info(f"  Missing: {missing_count}")
        if unmatched_pdfs:
            self.logger.info(f"  Unmatched PDFs: {len(unmatched_pdfs)}")
            for pdf in unmatched_pdfs:
                self.logger.info(f"    - {pdf.name}")
        self.logger.info("=" * 60)
        
        return output_path


def main():
    """CLI interface for AWB reordering."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Reorder AWB PDFs to match Excel order list'
    )
    parser.add_argument(
        '--orders-file',
        help='Path to processed_orders.json (default: data/processed_orders.json)',
        default='data/processed_orders.json'
    )
    parser.add_argument(
        '--input-folder',
        help='Folder with downloaded PDFs (default: input/)',
        default=None
    )
    parser.add_argument(
        '--output',
        help='Output filename (default: auto-generated)',
        default=None
    )
    
    args = parser.parse_args()
    
    try:
        # Load orders from processed_orders.json
        with open(args.orders_file, 'r', encoding='utf-8') as f:
            processed_data = json.load(f)
        
        # Convert dict to list maintaining order
        if isinstance(processed_data, dict):
            # It's a dict of package_id -> order_data
            # We need to get the order from most recent Excel generation
            print("❌ Error: Need to load orders from Excel processing run")
            print("   Run: python main.py first to process orders")
            return
        else:
            orders = processed_data
        
        reorder = AWBReorder()
        output_path = reorder.reorder_pdfs(
            orders,
            input_folder=args.input_folder,
            output_filename=args.output
        )
        
        print(f"\n✅ Success! Reordered AWB labels saved to:")
        print(f"   {output_path}")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

