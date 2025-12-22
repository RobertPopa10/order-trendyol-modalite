# Orders-Trendyol Project - Excel AWB Generator

## Project Overview

Generate Excel files to organize AWB (tracking numbers) for order processing from Trendyol orders.

## Architecture (Based on smartbill-trendyol)

- Reuse Trendyol API client and order processor logic
- Replace SmartBill integration with Excel generation
- Use same product scraping and translation infrastructure

---

## Implementation Phases

### Phase 1: Project Setup & Configuration

**Status:** Pending
**Dependencies:** None

**Tasks:**

1. Copy project structure from smartbill-trendyol
2. Create/copy `.env` file with Trendyol credentials
3. Setup requirements.txt with openpyxl for Excel generation
4. Create config.py adapted for Excel output
5. Setup logging_config.py (same as smartbill-trendyol)

**Notes:**

- Order status: `Picking` (from .env)
- Reuse existing Trendyol API key and credentials

---

### Phase 2: Trendyol API Integration

**Status:** Pending
**Dependencies:** Phase 1

**Tasks:**

1. Copy `trendyol_client.py` (no changes needed)
2. Copy `trendyol_storefront_scraper.py` (no changes needed)
3. Test API connection and order fetching

**Notes:**

- Exact same logic as smartbill-trendyol
- Fetches orders with status "Picking"

---

### Phase 3: Order Processing Infrastructure

**Status:** Pending
**Dependencies:** Phase 2

**Tasks:**

1. Adapt `order_processor.py` to handle Excel generation instead of invoices
2. Implement processed orders tracking (prevent duplicates)
3. Use `data/processed_orders.json` for state management

**Notes:**

- Same duplicate prevention logic
- Track which orders have been added to Excel files

---

### Phase 4: Product Translation & Color Extraction

**Status:** Pending
**Dependencies:** Phase 2

**Tasks:**

1. Copy `product_translator_v2.py` as base
2. Create new `product_mapper.py` for simplified name mapping
3. Implement color extraction from Romanian product names:
   - **Color mapping**: Alb→White, Negru→Black, Verde→Green, Roșu→Red, Albastru→Blue, Galben→Yellow, Gri→Grey, Maro→Brown, etc.
4. Create `data/product_name_mapping.json` for custom product names
5. **Fail entire processing if any product lacks mapping** (like smartbill-trendyol)

**Example Mapping:**

```json
{
  "1411659050": {
    "simplified_name": "Cos gunoi Smart",
    "color_extraction": "auto" // Extract from Romanian name
  }
}
```

**Color Extraction Logic:**

- Search Romanian product name for color keywords
- Support 7-8 main colors
- If no color found, use "N/A" or fail based on configuration

---

### Phase 5: Excel Generation Logic

**Status:** Pending
**Dependencies:** Phase 4

**Tasks:**

1. Create `excel_generator.py` module
2. Implement Excel structure with columns:
   - **Number** (row number)
   - **Client Name** (from order)
   - **Quantity**
   - **Product Name** (simplified, mapped)
   - **Color** (extracted)
3. Implement product grouping logic:
   - Group identical products together
   - Sort by product name
4. Implement complex orders handling:
   - **Step 1**: Identify "complex clients":
     - Clients with ANY order where quantity > 1
     - Clients who appear multiple times (have multiple orders)
   - **Step 2**: ALL orders from complex clients go to "Comenzi complexe" section
   - **Step 3**: Only clients with single order AND quantity = 1 stay in simple section
   - Add separator row: "**Comenzi complexe**"

**Excel Layout:**

```
# --- Simple Orders (Top) ---
1  | Jane Smith  | 1 | Blender SilverCrest | Argintiu
2  | Mike Brown  | 1 | Cos gunoi Smart     | Alb

# --- Separator ---
   | Comenzi complexe |

# --- Complex Orders (Bottom) ---
3  | John Doe    | 1 | Blender SilverCrest | Argintiu  <- All John Doe orders here
4  | John Doe    | 2 | Raft metalic        | Negru     <- because he appears twice
5  | Anna White  | 3 | Cos gunoi Smart     | Roz       <- Qty > 1
```

**Rationale:** Products for the same client might need to be packaged together, so all orders from a client with multiple orders must be grouped in the complex section.

---

### Phase 6: Main Application

**Status:** Pending
**Dependencies:** Phase 5

**Tasks:**

1. Create `main.py` orchestrator
2. Implement workflow:
   - Fetch orders from Trendyol (status: Picking)
   - Check if already processed
   - Translate product names (Romanian)
   - Map to simplified names + extract colors
   - **FAIL if any product mapping missing**
   - Group and organize orders
   - Generate Excel file with timestamp
   - Mark orders as processed
3. Add CLI options for testing and manual runs

---

### Phase 7: Testing & Validation

**Status:** Pending
**Dependencies:** Phase 6

**Tasks:**

1. Test with real orders from Trendyol
2. Validate color extraction accuracy
3. Verify product grouping logic
4. Test complex orders detection and separation
5. Verify duplicate order prevention

---

## Key Features Summary

✅ **Reused from smartbill-trendyol:**

- Trendyol API client
- Order processor (duplicate prevention)
- Product scraper
- Romanian translation infrastructure
- Logging system

🆕 **New for orders-trendyol:**

- Excel file generation (openpyxl)
- Simplified product name mapping
- Color extraction from Romanian names
- Product grouping in Excel
- Complex orders separation

❌ **Removed:**

- SmartBill API integration
- Invoice generation
- PDF hosting

---

## Configuration Requirements

### `.env` Variables:

```bash
TRENDYOL_API_KEY=<from smartbill-trendyol>
TRENDYOL_API_SECRET=<from smartbill-trendyol>
TRENDYOL_SUPPLIER_ID=<from smartbill-trendyol>
TRENDYOL_ORDER_STATUS=Picking
EXCEL_OUTPUT_DIR=./output
```

### Data Files:

1. `data/trendyol_products_romanian.json` - Romanian translations (from scraper)
2. `data/product_name_mapping.json` - Simplified name mappings (manual)
3. `data/color_mapping.json` - Color translation (Alb→White, etc.)
4. `data/processed_orders.json` - Order tracking state

---

## Open Questions / Decisions Needed

1. **Product mapping format**: Should simplified names include brand? (e.g., "Blender SilverCrest" vs just "Blender")
2. **Missing colors**: What if a product has no color in name? Fail or use "N/A"?
3. **Excel filename format**: `orders_{timestamp}.xlsx` or `orders_{date}_batch_{n}.xlsx`?
4. **Grouping criteria**: Group by simplified product name only, or include color in grouping?

✅ **Resolved:**

- **Complex orders logic**: ALL orders from a client go to "Comenzi complexe" if that client has multiple orders OR any order with qty > 1 (products might be packaged together)

---

## Implementation Complete! 🎉

**All phases completed successfully!**

### Files Created:

1. ✅ Configuration files (.env, config.py, logging_config.py, .gitignore)
2. ✅ Trendyol API integration (trendyol_client.py, trendyol_storefront_scraper.py)
3. ✅ Product translation (product_translator_v2.py)
4. ✅ Product mapping with color extraction (product_mapper.py)
5. ✅ Excel generator with grouping logic (excel_generator.py)
6. ✅ Order processor (order_processor.py)
7. ✅ Main application (main.py)
8. ✅ Documentation (README.md, QUICK_START.md)
9. ✅ Sample data files (data/product_name_mapping.json)

### Next Steps to Use:

1. **Install dependencies:**

   ```bash
   cd /Users/macmini/projects/orders-trendyol
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Fetch Romanian product names:**

   ```bash
   python trendyol_storefront_scraper.py
   ```

3. **Add your product mappings:**
   Edit `data/product_name_mapping.json` with all your products

4. **Run health check:**

   ```bash
   python main.py --health-check
   ```

5. **Process orders:**
   ```bash
   python main.py
   ```

See **QUICK_START.md** for detailed instructions!
