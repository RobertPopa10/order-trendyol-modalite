# Orders-Trendyol Excel Generator

Automated Excel AWB list generator for Trendyol orders. Fetches orders, translates product names, and generates organized Excel files with grouped orders.

## ⚠️ Important: Shared Product Mapping

This project uses the **stockTVA** `product_name_mapping.json` as its source of truth. See:

- **Quick Reference**: `MAPPING_QUICK_REFERENCE.md`
- **Setup Guide**: `SHARED_MAPPING_SETUP.md`
- **Changes**: `SHARED_MAPPING_CHANGES.md`

## Features

- ✅ Fetches orders from Trendyol API (status: Picking)
- ✅ Translates product names from English to Romanian
- ✅ Maps products to simplified names with RAZZ codes
- ✅ Extracts colors from product names
- ✅ Groups identical products together
- ✅ Separates simple and complex orders
- ✅ Prevents duplicate order processing
- ✅ Generates formatted Excel files
- ✅ **Uses shared mapping from stockTVA** (no local stock management)

## Quick Start

### 1. Install Dependencies

```bash
cd /Users/macmini/projects/orders-trendyol
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Setup Product Data

**Product mappings are now managed by the stockTVA project.**

This project reads from: `../stockTVA/data/product_name_mapping.json`

To add new products:

1. Scrape product data: `python api/trendyol_storefront_scraper.py`
2. Update the mapping: `python update_mapping_razz.py`

See `SHARED_MAPPING_SETUP.md` for details.

### 3. Configure Environment

Ensure your `.env` file has the required Trendyol API settings. The product mapping path is automatically configured to use stockTVA.

### 4. Run Health Check

```bash
python main.py --health-check
```

This verifies:

- Trendyol API connection
- Configuration is correct
- Product translations are loaded
- Product mappings are available (from stockTVA)

### 5. Process Orders

**Run once (default):**

```bash
python main.py
```

**Process specific number of orders:**

```bash
python main.py --limit 50
```

**Run continuously:**

```bash
python main.py --continuous --interval 300
```

## Project Structure

```
orders-trendyol/
├── main.py                          # Main application entry point
├── config.py                        # Configuration management
├── logging_config.py                # Logging setup
├── trendyol_client.py              # Trendyol API client
├── trendyol_storefront_scraper.py  # Fetch Romanian product names
├── product_translator_v2.py         # Translate English → Romanian
├── product_mapper.py                # Map to simplified names + extract colors
├── excel_generator.py               # Generate Excel files
├── order_processor.py               # Main processing workflow
├── .env                             # Environment variables
├── requirements.txt                 # Python dependencies
├── data/
│   ├── trendyol_products_romanian.json  # Romanian translations (auto-generated)
│   ├── product_name_mapping.json        # Simplified names (manual)
│   └── processed_orders.json            # Processing state (auto-generated)
├── output/                          # Generated Excel files
└── logs/                            # Application logs
```

## Excel Output Format

The generated Excel file contains:

### Simple Orders (Top Section)

Orders from clients who have:

- Single order only
- Quantity = 1

```
Nr. | Client Name | Quantity | Product Name         | Color
1   | Jane Smith  | 1        | Blender SilverCrest  | Argintiu
2   | Mike Brown  | 1        | Cos gunoi Smart      | Alb
```

### Comenzi complexe (Bottom Section)

**ALL** orders from clients who have:

- Multiple orders, OR
- Any order with quantity > 1

```
Nr. | Client Name | Quantity | Product Name         | Color
3   | John Doe    | 1        | Blender SilverCrest  | Argintiu
4   | John Doe    | 2        | Raft metalic         | Negru
5   | Anna White  | 3        | Cos gunoi Smart      | Roz
```

**Rationale:** Products for the same client might be packaged together.

## Color Extraction

The system automatically extracts colors from Romanian product names:

**Supported Colors:**

- Alb, Negru, Verde, Roșu, Albastru, Galben, Gri, Maro
- Portocaliu, Roz, Violet, Argintiu, Auriu, Bej, Crem
- Transparent, Multicolor

Example:

```
Romanian: "Blender Professional 2200W Argintiu"
Extracted Color: "Argintiu"
```

## Configuration

### Environment Variables (.env)

```bash
# Trendyol API
TRENDYOL_API_KEY=your_api_key
TRENDYOL_API_SECRET=your_api_secret
TRENDYOL_SUPPLIER_ID=your_supplier_id
TRENDYOL_ORDER_STATUS=Picking

# Paths
PROJECT_PATH=/Users/macmini/projects/orders-trendyol
EXCEL_OUTPUT_DIR=./output

# Logging
LOG_LEVEL=INFO
```

## Usage Examples

### Test Individual Components

**Test Trendyol connection:**

```bash
python trendyol_client.py
```

**Test product translator:**

```bash
python product_translator_v2.py
```

**Test product mapper:**

```bash
python product_mapper.py
```

**Test Excel generator:**

```bash
python excel_generator.py
```

**Test order processor:**

```bash
python order_processor.py
```

### Common Tasks

**Update product translations:**

```bash
python trendyol_storefront_scraper.py
```

**Process orders once:**

```bash
python main.py --run-once
```

**Process only 10 orders (for testing):**

```bash
python main.py --limit 10
```

**Run in background (continuous mode):**

```bash
nohup python main.py --continuous > output.log 2>&1 &
```

## Error Handling

### Product Mapping Missing

**Error:**

```
ProductMappingError: Product code 1234567890 not found in name mapping!
```

**Solution:**
Add the product to `data/product_name_mapping.json`:

```json
{
  "1234567890": {
    "simplified_name": "Your Product Name",
    "notes": "Optional description"
  }
}
```

### Product Translation Missing

**Error:**

```
ProductTranslationError: Product code 1234567890 not found in mapping!
```

**Solution:**
Run the scraper to update product translations:

```bash
python trendyol_storefront_scraper.py
```

### Color Not Found

**Error:**

```
ColorExtractionError: Could not extract color from product name
```

**Solution:**

1. Check if the color exists in the Romanian name
2. Add the color to `product_mapper.py` COLOR_MAPPING if needed
3. Or update the product name to include a supported color

## Logs

Logs are stored in `logs/` directory:

- `excel_generator.log` - Main application log
- `errors.log` - Errors and critical issues only
- `debug.log` - Detailed debug information (if LOG_LEVEL=DEBUG)

## State Management

The system tracks processed orders in `data/processed_orders.json` to prevent duplicates.

**To reprocess orders:**

1. Delete or backup `data/processed_orders.json`
2. Run the application again

## Troubleshooting

### No orders found

- Check Trendyol API credentials in `.env`
- Verify order status is set to `Picking`
- Check if there are actual orders with that status in Trendyol

### Excel not generated

- Check logs in `logs/` directory
- Verify all products have mappings
- Ensure `output/` directory exists and is writable

### Health check fails

Run individual component tests to identify the issue:

```bash
python trendyol_client.py
python product_translator_v2.py
python product_mapper.py
```

## License

Internal use only.

## Support

Check the logs for detailed error messages. Most issues are related to:

1. Missing product mappings
2. Missing product translations
3. API credential issues
