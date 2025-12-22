#!/usr/bin/env python3
"""
Orders-Trendyol Excel Generator
Main application script for automated Excel AWB list generation.

This script fetches orders from Trendyol, processes them, and generates
Excel files with grouped order AWB lists.
"""

import sys
import argparse
import signal
from pathlib import Path
from datetime import datetime
import subprocess
import json

# Add current directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from logging_config import setup_logging, get_logger
from config import get_config
from api.order_processor import OrderProcessor
from api.trendyol_client import TrendyolClient


class ExcelGeneratorService:
    """Main Excel generator service class."""
    
    def __init__(self):
        """Initialize the service."""
        # Setup logging first
        setup_logging()
        self.logger = get_logger('main')
        
        # Load configuration
        try:
            self.config = get_config()
            self.logger.info("Configuration loaded successfully")
        except Exception as e:
            self.logger.critical(f"Failed to load configuration: {e}")
            sys.exit(1)
        
        # Initialize processor (after logging is setup)
        try:
            self.processor = OrderProcessor()
            self.logger.info("Order processor initialized")
        except Exception as e:
            self.logger.critical(f"Failed to initialize order processor: {e}")
            sys.exit(1)
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        self.shutdown_requested = False
    
    def _cleanup_output_files(self):
        """Clean up old output files only (before processing)."""
        try:
            self.logger.info("Cleaning up old output files...")
            
            # Clean output directory (keep only .DS_Store)
            output_dir = Path(self.config.output_dir)
            if output_dir.exists():
                for file in output_dir.iterdir():
                    if file.is_file() and file.name != '.DS_Store':
                        file.unlink()
                        self.logger.info(f"Deleted output file: {file.name}")
            
            self.logger.info("Output file cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Failed to cleanup output files: {e}")
            # Don't fail the entire process due to cleanup issues
    
    def _cleanup_input_files(self):
        """Clean up input files (after AWB processing is complete)."""
        try:
            self.logger.info("Cleaning up input files...")
            
            # Clean input directory (except README.txt)
            input_dir = Path(self.config.input_dir)
            if input_dir.exists():
                for file in input_dir.iterdir():
                    if file.is_file() and file.name != 'README.txt':
                        file.unlink()
                        self.logger.info(f"Deleted input file: {file.name}")
            
            self.logger.info("Input file cleanup completed")
            
        except Exception as e:
            self.logger.warning(f"Failed to cleanup input files: {e}")
            # Don't fail the entire process due to cleanup issues
    
    def delete_last_processed_orders(self) -> bool:
        """
        Delete orders that were processed in the last run from processed_orders.json.
        
        Returns:
            True if successful
        """
        try:
            # Get the last session ID from the processor
            last_session_id = self.processor.get_last_session_id()
            if not last_session_id:
                self.logger.warning("No last session found - nothing to delete")
                return True
            
            deleted_count = self.processor.delete_orders_by_session(last_session_id)
            
            if deleted_count > 0:
                self.logger.info(f"Deleted {deleted_count} orders from last session ({last_session_id})")
                return True
            else:
                self.logger.info("No orders found from last session to delete")
                return True
                
        except Exception as e:
            self.logger.error(f"Failed to delete last processed orders: {e}")
            return False
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}. Initiating graceful shutdown...")
        self.shutdown_requested = True
    
    def health_check(self) -> bool:
        """
        Perform comprehensive health check.
        
        Returns:
            True if all systems are healthy
        """
        self.logger.info("Performing system health check...")
        
        # Check configuration
        try:
            config_dict = self.config.to_dict()
            self.logger.info(f"Configuration OK - Environment: {config_dict['environment']}")
        except Exception as e:
            self.logger.error(f"Configuration health check failed: {e}")
            return False
        
        # Check Trendyol API
        try:
            trendyol_client = TrendyolClient()
            if not trendyol_client.health_check():
                self.logger.error("Trendyol API health check failed")
                return False
            self.logger.info("Trendyol API OK")
        except Exception as e:
            self.logger.error(f"Trendyol API health check error: {e}")
            return False
        
        # Check product mappings
        try:
            from api.product_translator_v2 import get_auto_translator
            from api.product_mapper import get_product_mapper
            
            translator = get_auto_translator()
            translator_stats = translator.get_stats()
            self.logger.info(f"Product Translation: {translator_stats['total_products']} products loaded")
            
            mapper = get_product_mapper(fail_on_missing=False)
            mapper_stats = mapper.get_stats()
            self.logger.info(f"Product Mapping: {mapper_stats['total_mapped_products']} products mapped")
            
            if translator_stats['total_products'] == 0:
                self.logger.warning("⚠️  No Romanian product translations available!")
                self.logger.warning("   Run: python api/trendyol_storefront_scraper.py")
            
            if mapper_stats['total_mapped_products'] == 0:
                self.logger.warning("⚠️  No product name mappings available!")
                self.logger.warning("   Create: data/product_name_mapping.json")
            
        except Exception as e:
            self.logger.error(f"Product mapping health check error: {e}")
            return False
        
        self.logger.info("✅ All systems healthy")
        return True
    
    def update_product_data(self) -> bool:
        """
        Update product data by running scraper and mapping update.
        
        Returns:
            True if successful
        """
        self.logger.info("🔄 Updating product data prerequisites...")
        
        try:
            # Step 1: Run the storefront scraper
            self.logger.info("📊 Running Trendyol storefront scraper...")
            scraper_script = Path(__file__).parent / "api" / "trendyol_storefront_scraper.py"
            
            result = subprocess.run([
                sys.executable, str(scraper_script)
            ], capture_output=True, text=True, cwd=Path(__file__).parent)
            
            if result.returncode != 0:
                self.logger.error(f"Storefront scraper failed: {result.stderr}")
                return False
            
            # Parse the output to get stats
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if "✅ Found" in line and "products" in line:
                    self.logger.info(f"  {line}")
                elif "💾 Saved product mapping to:" in line:
                    self.logger.info(f"  {line}")
            
            # Step 2: Run the mapping update
            self.logger.info("🔄 Updating product name mapping...")
            update_script = Path(__file__).parent / "update_mapping_razz.py"
            
            result = subprocess.run([
                sys.executable, str(update_script)
            ], capture_output=True, text=True, cwd=Path(__file__).parent)
            
            if result.returncode != 0:
                self.logger.error(f"Mapping update failed:")
                if result.stdout:
                    self.logger.error(f"Output: {result.stdout}")
                if result.stderr:
                    self.logger.error(f"Error: {result.stderr}")
                return False
            
            # Parse the output to get stats
            output_lines = result.stdout.strip().split('\n')
            for line in output_lines:
                if "Summary:" in line or "Total products" in line or "New products added" in line or "products updated" in line:
                    self.logger.info(f"  {line}")
            
            self.logger.info("✅ Product data updated successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to update product data: {e}")
            return False
    
    def _reorder_awbs(self, order_list_file: str):
        """Automatically reorder AWBs if PDF exists."""
        from pathlib import Path
        from split_and_reorder_awbs import split_and_reorder_pdf
        from PyPDF2 import PdfMerger
        import json
        
        input_dir = Path(__file__).parent / "input"
        output_dir = self.config.output_dir
        
        # Find PDFs in input/
        pdf_files = sorted(input_dir.glob("*.pdf"), key=lambda p: p.stat().st_mtime)
        if not pdf_files:
            self.logger.info("  ⚠️  No AWB PDFs found in input/ - skipping reorder")
            return True
        
        # Merge if multiple
        if len(pdf_files) > 1:
            self.logger.info(f"  📎 Merging {len(pdf_files)} AWB PDFs...")
            merger = PdfMerger()
            for pdf in pdf_files:
                merger.append(str(pdf))
            
            merged_path = input_dir / f"merged_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            merger.write(str(merged_path))
            merger.close()
            input_pdf = merged_path
        else:
            input_pdf = pdf_files[0]
            self.logger.info(f"  📄 Found AWB PDF: {input_pdf.name}")
        
        # The order_list_file is now directly the excel_order.json file
        excel_order_file = Path(order_list_file)
        
        if not excel_order_file.exists():
            self.logger.error(f"  ❌ Excel order file not found: {excel_order_file.name}")
            return False
        else:
            self.logger.info(f"  📋 Using Excel order: {excel_order_file.name}")
        
        # Load orders
        with open(excel_order_file, 'r', encoding='utf-8') as f:
            orders = json.load(f)
        
        # Reorder
        timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
        output_path = output_dir / f"awb_labels_reordered_{timestamp}.pdf"
        
        try:
            result = split_and_reorder_pdf(input_pdf, orders, output_path)
            
            if result['success']:
                if result['validation_passed']:
                    self.logger.info(f"  🏷️  Reordered AWBs: {output_path.name}")
                    self.logger.info(f"  ✅ AWB Validation PASSED: {result['matched_awbs']}/{result['total_orders']} AWBs matched")
                    return True
                else:
                    # AWB count mismatch - delete processed orders and fail
                    self.logger.error(f"  ❌ AWB Validation FAILED: {result['matched_awbs']}/{result['total_orders']} AWBs matched")
                    self.logger.error(f"  📛 Missing {result['missing_awbs']} AWB(s) - this indicates a problem!")
                    
                    # Show missing orders
                    if result.get('missing_orders'):
                        self.logger.error("  Missing AWBs for orders:")
                        for missing in result['missing_orders'][:5]:  # Show first 5
                            self.logger.error(f"    - {missing['customer']} (AWB: {missing['tracking']})")
                        if len(result['missing_orders']) > 5:
                            self.logger.error(f"    ... and {len(result['missing_orders']) - 5} more")
                    
                    # Delete processed orders from last session
                    self.logger.error("  🗑️  Deleting processed orders from last session...")
                    deleted_count = self.delete_last_processed_orders()
                    
                    # Clean up the partially created reordered file
                    if output_path.exists():
                        output_path.unlink()
                        self.logger.info(f"  🗑️  Cleaned up partial file: {output_path.name}")
                    
                    raise Exception(f"AWB validation failed: {result['matched_awbs']}/{result['total_orders']} AWBs matched. Processed orders have been deleted.")
            else:
                raise Exception("AWB reordering failed")
                
        except Exception as e:
            self.logger.error(f"  ❌ AWB reorder failed: {e}")
            return False
    
    def run_once(self, max_pages: int = 5, skip_prerequisites: bool = False) -> bool:
        """
        Run order processing once.
        Fetches ALL orders across multiple pages and processes only new ones.
        
        Args:
            max_pages: Maximum pages to fetch per status
            skip_prerequisites: Skip product data update (scraper + mapping)
            
        Returns:
            True if successful
        """
        self.logger.info("=" * 60)
        self.logger.info(f"Starting order processing run at {datetime.now()}")
        self.logger.info(f"Will fetch up to {max_pages} pages per status")
        self.logger.info("=" * 60)
        
        # Step 1: Update product data (scraper + mapping) - unless skipped
        if not skip_prerequisites:
            self.logger.info("🔧 Running prerequisites...")
            if not self.update_product_data():
                self.logger.error("❌ Failed to update product data - aborting processing")
                return False
        else:
            self.logger.info("⏭️ Skipping prerequisites (product data update)")
        
        # Cleanup old output files before processing (keep input files for AWB reordering)
        self._cleanup_output_files()
        
        try:
            result = self.processor.process_orders_batch(max_pages=max_pages)
            
            if result['success']:
                self.logger.info("Processing completed successfully!")
                self.logger.info(f"  Orders processed: {result.get('orders_processed', 0)}")
                self.logger.info(f"  Items processed: {result.get('items_processed', 0)}")
                self.logger.info(f"  Successful: {result.get('successful', 0)}")
                self.logger.info(f"  Failed: {result.get('failed', 0)}")
                
                if result.get('excel_file'):
                    self.logger.info(f"  📊 Excel file: {result['excel_file']}")
                
                # Process AWB reordering if order list is available
                awb_processed_successfully = True
                if result.get('order_list_file'):
                    self.logger.info(f"  📋 Order list (for AWB): {result['order_list_file']}")
                    
                    # Auto-reorder AWBs
                    awb_success = self._reorder_awbs(result['order_list_file'])
                    if not awb_success:
                        # AWB validation failed, processing should be considered failed
                        self.logger.error("🚫 Processing FAILED due to AWB validation failure")
                        awb_processed_successfully = False
                
                if result.get('failed_orders'):
                    self.logger.warning("Failed orders:")
                    for failed in result['failed_orders']:
                        self.logger.warning(f"  - {failed['order_number']}: {failed['error']}")
                
                # Clean up input files only if everything succeeded (including AWB processing)
                if awb_processed_successfully:
                    self._cleanup_input_files()
                    return True
                else:
                    return False
            else:
                self.logger.error(f"Processing failed: {result.get('error', 'Unknown error')}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during processing: {e}", exc_info=True)
            return False
        finally:
            # Print statistics
            stats = self.processor.get_stats()
            self.logger.info("=" * 60)
            self.logger.info("Session Statistics:")
            self.logger.info(f"  Session started: {stats['session_start']}")
            self.logger.info(f"  Successful: {stats['successful']}")
            self.logger.info(f"  Failed: {stats['failed']}")
            self.logger.info(f"  Success rate: {stats['success_rate']:.1f}%")
            self.logger.info(f"  Total processed ever: {stats['total_processed_ever']}")
            self.logger.info("=" * 60)
    
    def run_continuous(self, interval: int = 300):
        """
        Run order processing continuously.
        
        Args:
            interval: Interval between runs in seconds
        """
        import time
        
        self.logger.info("Starting continuous processing mode")
        self.logger.info(f"Polling interval: {interval} seconds")
        
        while not self.shutdown_requested:
            self.run_once()
            
            if self.shutdown_requested:
                break
            
            self.logger.info(f"Waiting {interval} seconds until next run...")
            for _ in range(interval):
                if self.shutdown_requested:
                    break
                time.sleep(1)
        
        self.logger.info("Continuous processing stopped")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Orders-Trendyol Excel Generator - Generate AWB lists from Trendyol orders'
    )
    
    parser.add_argument(
        '--health-check',
        action='store_true',
        help='Perform system health check and exit'
    )
    
    parser.add_argument(
        '--run-once',
        action='store_true',
        help='Process orders once and exit (default behavior)'
    )
    
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously with polling interval'
    )
    
    parser.add_argument(
        '--max-pages',
        type=int,
        default=5,
        help='Maximum pages to fetch per status (default: 5)'
    )
    
    parser.add_argument(
        '--interval',
        type=int,
        default=300,
        help='Polling interval in seconds for continuous mode (default: 300)'
    )
    
    parser.add_argument(
        '--delete-last-processed',
        action='store_true',
        help='Delete the orders that were processed in the last run'
    )
    
    parser.add_argument(
        '--skip-prerequisites',
        action='store_true',
        help='Skip the product data update prerequisites (scraper + mapping update)'
    )
    
    args = parser.parse_args()
    
    # Create service instance
    try:
        service = ExcelGeneratorService()
    except Exception as e:
        print(f"❌ Failed to initialize service: {e}")
        return 1
    
    # Delete last processed orders mode
    if args.delete_last_processed:
        print("\n🗑️  Deleting last processed orders...\n")
        success = service.delete_last_processed_orders()
        if success:
            print("\n✅ Last processed orders deleted successfully!\n")
            return 0
        else:
            print("\n❌ Failed to delete last processed orders!\n")
            return 1
    
    # Health check mode
    if args.health_check:
        print("\n🏥 Performing health check...\n")
        if service.health_check():
            print("\n✅ All systems healthy!\n")
            return 0
        else:
            print("\n❌ Health check failed!\n")
            return 1
    
    # Continuous mode
    if args.continuous:
        service.run_continuous(interval=args.interval)
        return 0
    
    # Default: run once
    success = service.run_once(max_pages=args.max_pages, skip_prerequisites=args.skip_prerequisites)
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())

