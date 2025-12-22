#!/usr/bin/env python3
"""
Logging configuration for Orders-Trendyol Excel Generator.
Provides comprehensive logging setup with file rotation and colored console output.
"""

import logging
import logging.handlers
import sys
from pathlib import Path
from datetime import datetime
from config import get_config


class ColoredFormatter(logging.Formatter):
    """Colored formatter for console output."""
    
    # ANSI color codes
    COLORS = {
        'DEBUG': '\033[36m',      # Cyan
        'INFO': '\033[32m',       # Green  
        'WARNING': '\033[33m',    # Yellow
        'ERROR': '\033[31m',      # Red
        'CRITICAL': '\033[35m',   # Magenta
    }
    RESET = '\033[0m'
    
    def format(self, record):
        """Format log record with colors."""
        # Create a copy to avoid modifying the original record
        log_record = logging.makeLogRecord(record.__dict__)
        
        # Add color to level name
        level_color = self.COLORS.get(log_record.levelname, '')
        log_record.levelname = f"{level_color}{log_record.levelname}{self.RESET}"
        
        # Format the message
        formatted = super().format(log_record)
        
        return formatted


class CustomFormatter(logging.Formatter):
    """Custom formatter with component identification."""
    
    def format(self, record):
        """Format record with component info."""
        # Add component info based on logger name
        component_map = {
            'trendyol': '🛒',
            'processor': '⚙️',
            'excel': '📊',
            'mapper': '🗺️',
            'config': '⚙️',
            'main': '🚀'
        }
        
        component = 'system'
        for key, icon in component_map.items():
            if key in record.name:
                component = f"{icon} {key.upper()}"
                break
        
        record.component = component
        return super().format(record)


class IntegrationLogger:
    """Centralized logging setup for the Excel generator."""
    
    def __init__(self):
        """Initialize logging system."""
        self.config = get_config()
        self.log_dir = self.config.log_dir
        self.log_level = getattr(logging, self.config.log_level.upper(), logging.INFO)
        
        # Ensure log directory exists
        self.log_dir.mkdir(exist_ok=True)
        
        # Setup loggers
        self._setup_root_logger()
        self._setup_file_handlers()
        self._setup_console_handler()
    
    def _setup_root_logger(self):
        """Setup root logger configuration."""
        # Get root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)
        
        # Clear existing handlers
        root_logger.handlers.clear()
    
    def _setup_file_handlers(self):
        """Setup file handlers for different log levels."""
        
        # Main application log with rotation
        main_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / 'excel_generator.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        main_handler.setLevel(logging.INFO)
        
        # Detailed formatter for file logs
        file_formatter = CustomFormatter(
            '%(asctime)s | %(component)-12s | %(levelname)-8s | %(name)-20s | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_handler.setFormatter(file_formatter)
        
        # Error log (errors and critical only)
        error_handler = logging.handlers.RotatingFileHandler(
            filename=self.log_dir / 'errors.log',
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # Debug log (everything, only if debug enabled)
        if self.log_level == logging.DEBUG:
            debug_handler = logging.handlers.RotatingFileHandler(
                filename=self.log_dir / 'debug.log',
                maxBytes=20 * 1024 * 1024,  # 20MB
                backupCount=2,
                encoding='utf-8'
            )
            debug_handler.setLevel(logging.DEBUG)
            
            debug_formatter = CustomFormatter(
                '%(asctime)s | %(component)-12s | %(levelname)-8s | %(name)-20s | %(filename)s:%(lineno)d | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            debug_handler.setFormatter(debug_formatter)
            
            logging.getLogger().addHandler(debug_handler)
        
        # Add handlers to root logger
        logging.getLogger().addHandler(main_handler)
        logging.getLogger().addHandler(error_handler)
    
    def _setup_console_handler(self):
        """Setup colored console handler."""
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(self.log_level)
        
        # Colored formatter for console
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)-8s | %(name)-15s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        logging.getLogger().addHandler(console_handler)
    
    def get_logger(self, name: str):
        """
        Get a logger instance for a specific component.
        
        Args:
            name: Logger name (e.g., 'trendyol', 'excel', 'processor')
            
        Returns:
            Logger instance
        """
        return logging.getLogger(f'excel_gen.{name}')


# Global logger instance
_logger_instance = None


def setup_logging():
    """
    Setup logging system (call once at application start).
    
    Returns:
        IntegrationLogger instance
    """
    global _logger_instance
    
    if _logger_instance is None:
        _logger_instance = IntegrationLogger()
    
    return _logger_instance


def get_logger(name: str):
    """
    Get a logger for a component.
    
    Args:
        name: Component name
        
    Returns:
        Logger instance
    """
    if _logger_instance is None:
        setup_logging()
    
    return _logger_instance.get_logger(name)


# Convenience functions for quick logging
def log_api_call(logger, method: str, url: str, status_code: int, duration: float):
    """Log API call details."""
    logger.info(f"{method} {url} -> {status_code} ({duration:.2f}s)")


def log_order_processing(logger, order_number: str, stage: str, status: str, details: str = ""):
    """Log order processing events."""
    message = f"Order {order_number} | {stage} | {status}"
    if details:
        message += f" | {details}"
    
    if status.lower() in ['success', 'completed', 'ok']:
        logger.info(message)
    elif status.lower() in ['warning', 'partial']:
        logger.warning(message)
    else:
        logger.error(message)


def log_system_event(logger, event: str, details: dict = None):
    """Log system events with structured data."""
    message = f"System Event: {event}"
    
    if details:
        detail_str = " | ".join([f"{k}={v}" for k, v in details.items()])
        message += f" | {detail_str}"
    
    logger.info(message)


# Error logging helpers
def log_exception(logger, operation: str, exception: Exception, context: dict = None):
    """Log exceptions with context."""
    message = f"Exception in {operation}: {type(exception).__name__}: {exception}"
    
    if context:
        context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
        message += f" | Context: {context_str}"
    
    logger.error(message, exc_info=True)


if __name__ == '__main__':
    # Test logging setup
    setup_logging()
    
    # Test different loggers
    main_logger = get_logger('main')
    trendyol_logger = get_logger('trendyol')
    excel_logger = get_logger('excel')
    
    # Test different log levels
    main_logger.info("Application started")
    trendyol_logger.info("Connected to Trendyol API")
    excel_logger.info("Excel generator ready")
    
    # Test warning and error
    main_logger.warning("This is a warning message")
    main_logger.error("This is an error message")
    
    # Test convenience functions
    log_api_call(trendyol_logger, "GET", "/orders", 200, 0.45)
    log_order_processing(main_logger, "TR123456", "Excel Generation", "Success", "Excel file created")
    log_system_event(main_logger, "Batch Processing", {"orders_processed": 5, "success_rate": "100%"})
    
    print("\n✓ Logging test completed. Check logs/ directory for output files.")

