"""
Orders-Trendyol Excel Generator Configuration Module

Handles environment variables and API configuration.
"""
import os
import base64
import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    """Configuration class for Orders-Trendyol Excel Generator."""
    
    def __init__(self):
        self.validate_config()
    
    @property
    def environment(self):
        """Environment (development/production)."""
        return os.getenv('ENVIRONMENT', 'development')
    
    @property 
    def project_path(self):
        """Project root path."""
        return Path(os.getenv('PROJECT_PATH', os.getcwd()))
    
    @property
    def log_dir(self):
        """Log directory path."""
        log_dir = self.project_path / 'logs'
        log_dir.mkdir(exist_ok=True)
        return log_dir
    
    @property
    def data_dir(self):
        """Data directory path.""" 
        data_dir = self.project_path / 'data'
        data_dir.mkdir(exist_ok=True)
        return data_dir
    
    @property
    def stocktva_mapping_path(self):
        """Path to the stockTVA product_name_mapping.json (shared, read-only)."""
        # Default path: assumes stockTVA is a sibling directory
        default_path = self.project_path.parent / 'stockTVA' / 'data' / 'product_name_mapping.json'
        stocktva_path = os.getenv('STOCKTVA_MAPPING_PATH', str(default_path))
        return Path(stocktva_path)
    
    @property
    def input_dir(self):
        """Input directory path for AWB PDFs."""
        input_dir = self.project_path / 'input'
        input_dir.mkdir(exist_ok=True)
        return input_dir
    
    @property
    def output_dir(self):
        """Excel output directory path."""
        output_path = os.getenv('EXCEL_OUTPUT_DIR', './output')
        output_dir = Path(output_path) if output_path.startswith('/') else self.project_path / output_path
        output_dir.mkdir(exist_ok=True)
        return output_dir
    
    @property
    def log_level(self):
        """Log level."""
        return os.getenv('LOG_LEVEL', 'INFO')
    
    @property
    def trendyol_order_status(self):
        """Trendyol order status to process."""
        return os.getenv('TRENDYOL_ORDER_STATUS', 'Picking')
    
    # Trendyol Configuration
    @property
    def trendyol_api_key(self):
        """Trendyol API key."""
        return os.getenv('TRENDYOL_API_KEY')
    
    @property
    def trendyol_api_secret(self):
        """Trendyol API secret."""
        return os.getenv('TRENDYOL_API_SECRET')
    
    @property
    def trendyol_supplier_id(self):
        """Trendyol supplier ID."""
        return os.getenv('TRENDYOL_SUPPLIER_ID')
    
    @property
    def trendyol_endpoint(self):
        """Trendyol API endpoint."""
        return os.getenv('TRENDYOL_ENDPOINT', 'https://api.trendyol.com')
    
    @property
    def trendyol_user_agent(self):
        """Trendyol User-Agent header."""
        return f"{self.trendyol_supplier_id} - SelfIntegration"
    
    @property
    def trendyol_auth_header(self):
        """Trendyol Basic Auth header."""
        credentials = f"{self.trendyol_api_key}:{self.trendyol_api_secret}"
        encoded = base64.b64encode(credentials.encode()).decode()
        return f"Basic {encoded}"
    
    @property
    def trendyol_update_status(self):
        """Whether to update Trendyol order status (true/false)."""
        return os.getenv('TRENDYOL_UPDATE_STATUS', 'false').lower() == 'true'
    
    @property
    def ignored_orders(self) -> List[str]:
        """List of order numbers to ignore during AWB processing."""
        ignored_orders_file = self.data_dir / 'ignored_orders.json'
        
        if not ignored_orders_file.exists():
            return []
        
        try:
            with open(ignored_orders_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data.get('ignored_orders', [])
        except (json.JSONDecodeError, IOError) as e:
            # Log warning but don't fail - return empty list
            return []
    
    # Processing Configuration
    @property
    def polling_interval(self):
        """Polling interval in seconds."""
        return int(os.getenv('POLLING_INTERVAL', '300'))
    
    def validate_config(self):
        """Validate that all required configuration is present."""
        required_trendyol = [
            'TRENDYOL_API_KEY',
            'TRENDYOL_API_SECRET', 
            'TRENDYOL_SUPPLIER_ID'
        ]
        
        missing = []
        
        for key in required_trendyol:
            if not os.getenv(key):
                missing.append(key)
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    def to_dict(self) -> Dict[str, Any]:
        """Export configuration as dictionary."""
        return {
            'environment': self.environment,
            'trendyol_endpoint': self.trendyol_endpoint,
            'supplier_id': self.trendyol_supplier_id,
            'polling_interval': self.polling_interval,
            'log_level': self.log_level,
            'order_status': self.trendyol_order_status,
            'output_dir': str(self.output_dir)
        }


# Global configuration instance
_config_instance = None

def get_config() -> Config:
    """Get the global configuration instance."""
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config()
    
    return _config_instance


if __name__ == '__main__':
    # Test configuration
    try:
        cfg = get_config()
        print("✅ Configuration loaded successfully!")
        print(f"Environment: {cfg.environment}")
        print(f"Trendyol Supplier ID: {cfg.trendyol_supplier_id}")
        print(f"Order Status: {cfg.trendyol_order_status}")
        print(f"Output Directory: {cfg.output_dir}")
        print(f"Log Level: {cfg.log_level}")
    except Exception as e:
        print(f"❌ Configuration error: {e}")

