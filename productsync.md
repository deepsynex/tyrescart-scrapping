# Product Sync from Tyrescart GraphQL

## Goal
Add a third way for products to get into the `products` table, alongside admin CRUD and CSV import (`/visionadmin/api/products/import-csv`):

1. Pull every product from the Tyrescart GraphQL API.
2. Store the results in the browser's IndexedDB.
3. Compare them against our MySQL `products` table.
4. Show a full-screen review modal listing **New** and **Needs update** products.
5. Write to MySQL only when the admin clicks **Import**.

## Status
Built and tested locally (2026-10-27). **Not deployed** to dev or live.

## Decisions
- **Source**: `https://www.tyrescart.ae/graphql`, the default. Override it with `PRODUCT_SYNC_GRAPHQL_URL` in `.env`. An optional `PRODUCT_SYNC_GRAPHQL_TOKEN` is sent as a Bearer header. The browser never calls Tyrescart directly.
- **Price includes VAT**: Tyrescart's `final_price` excludes the 5% UAE VAT, and our catalog stores `ceil(final_price × 1.05)`. That rule matches 7,269 of 7,276 existing products. The sync converts prices the same way, and `PRODUCT_SYNC_PRICE_MULTIPLIER` (default `1.05`) changes the rate.
- **Images**: left blank. `image.url` is shown as a preview in the modal but is **not** written to `image_path`.
- **Status**: products are created with the remote status; every product in the feed is Enabled, so they become `active`.
- **Match key**: `sku`, normalized with `strip().upper()`, the same as `Product.create`.
- **Display name**: our `display_name` holds the full product name, so it is compared with and updated from Tyrescart's `name`. Tyrescart's own `display_name` is only the pattern ("Pilot Sport 4S") and is stored in `attributes_json.display_name`, as the original CSV import did.
- **Slug**: set from `url_key` on create only and never changed on update, so existing URLs keep working.
- **Meta title and meta description**: they differ on 7,274 products because the local copies were rewritten for SEO ("Buy … Online"). Their field toggles start unticked, so the sync doesn't overwrite them unless an admin opts in.

## Source API
- Endpoint: `https://www.tyrescart.ae/graphql` (public, no token). `https://www.tyrescart.com/graphql` returns the same data.
- 9,167 products, which is 10 pages at `pageSize: 1000`. All products checked so far are Enabled.
- Schema introspection is disabled, so every field below was confirmed by querying it directly.

## GraphQL query
```graphql
query Products($filter: ProductAttributeFilterInput, $page: Int!, $size: Int!) {
  products(filter: $filter, pageSize: $size, currentPage: $page) {
    total_count
    page_info { current_page total_pages }
    items {
      status name sku url_key attribute_set_id visibility
      brand item_code pattern tyre_marking parts_category oem_tyres
      tyre_size width height rim load_index country ev runflat
      year warranty_period tyre_type tyres_category
      price_per_item price_included_text tabby_payment
      price_range { minimum_price { regular_price { value currency } final_price { value currency } } }
      categories { id name url_path level }
      short_description { html }
      description { html }
      meta_title meta_keyword meta_description
      stock_status
      image { url }
    }
  }
}
```
Variables: `{"filter": {}, "page": N, "size": 1000}`. The sync loops `page` from 1 to `page_info.total_pages`.

## Option labels (one extra request per sync)
Dropdown attributes return **option IDs**, not names; for example, `brand: 1353` means Michelin. Before fetching products, the server calls this query once and builds an ID-to-label map for each attribute:
```graphql
{ customAttributeMetadataV2(attributes: [
    {attribute_code: "brand", entity_type: "catalog_product"}, ... ]) {
  items { code label frontend_input options { label value } } } }
```
Every SELECT/MULTISELECT/BOOLEAN value is converted to its label before it is stored in IndexedDB. Multi-select values such as `oem_tyres` are comma-separated IDs, and each ID is converted separately.

## Source attributes
Fill rates are from the first 1,000 products.

| Magento label | GraphQL field | Type | Example (resolved) | Filled |
|---|---|---|---|---|
| Enable Product | `status` | select (1 Enabled, 2 Disabled) | Enabled | 1000 |
| Product Name | `name` | text | Sailun 265/70 R18 116T Turismo SV57 2026 | 1000 |
| SKU | `sku` | text | TCKL-26190 | 1000 |
| URL Key | `url_key` | text | sailun-265-70-r18-116t-turismo-sv57-2026 | 1000 |
| Attribute Set | `attribute_set_id` | raw ID, no label available | 9 (999), 14 (1) | 1000 |
| Visibility | `visibility` | select | Catalog, Search | 1000 |
| Brand | `brand` | select | Sailun | 1000 |
| Item Code | `item_code` | text | 161R0102657018TRISMA-2026 | 995 |
| Pattern | `pattern` | select | Turismo SV57 | 1000 |
| Tyre Marking | `tyre_marking` | select | *, MO, AO, MO1, MOE | 198 |
| Parts Category | `parts_category` | select | Tyres | 1000 |
| OEM Tyres | `oem_tyres` | multiselect | BMW | 2 |
| Tyre Size | `tyre_size` | select | 265/70 R18 | 1000 |
| Width / Height / Rim | `width` / `height` / `rim` | select | 265 / 70 / 18 | 1000 / 999 / 1000 |
| Load/Speed Index | `load_index` | text | 116T | 1000 |
| Origin | `country` | select | China | 734 |
| EV Tyre | `ev` | select (181 = EV) | EV | 50 |
| RunFlat | `runflat` | select (172 = RunFlat) | RunFlat | 49 |
| Year | `year` | select | 2026 | 1000 |
| Warranty Period | `warranty_period` | select | 3 Years Warranty | 1000 |
| Tyre Type | `tyre_type` | select | Car / SUV / Bike / Truck Van | 1000 |
| Tyres Category | `tyres_category` | select | Budget / Quality / Premium | 999 |
| Price | `price_range.minimum_price.regular_price` | money | 435 AED | 1000 |
| Final price | `price_range.minimum_price.final_price` | money | 435 AED | 1000 |
| Price Per Item | `price_per_item` | money | 435 | 1000 |
| Price Included Text | `price_included_text` | select | Fitted Price | 1000 |
| Tabby Payment | `tabby_payment` | boolean | Yes / No | 543 Yes |
| Categories | `categories` | list | Tyres > Brand > Sailun, Tyres > Tyre Size > … | 1000 |
| Short Description | `short_description.html` | HTML | `<p>…</p>` | 1000 |
| Description | `description.html` | HTML | Page Builder `<div data-content-type="html">…</div>` | 1000 |
| Meta Title | `meta_title` | text | | 1000 |
| Meta Keywords | `meta_keyword` | text | | 1000 |
| Meta Description | `meta_description` | text | | 1000 |

### Not available from the API
- **Tax Class** (`tax_class_id`): the attribute exists (`0` None, `2` Taxable Goods), but GraphQL won't return it per product. It can only be synced if Tyrescart exposes it in Magento; until then a default is set on import.
- **Promotion** (`promotion`): no such attribute in the catalog.
- **Dynamic Price** (`price_type`): the attribute exists, but it isn't queryable on products (it applies to bundle products only).
- `price` (legacy) returns the same value as `price_range.regular_price`, so it is not queried separately.

### Data notes
- `categories` sometimes disagrees with the product. For example, TCKL-26190 is a 265/70 R18 tyre but is in the "235/65 R17" size category. Use `tyre_size`/`width`/`height`/`rim` for size, and use only the Brand branch of `categories`.
- `description` is wrapped in Magento Page Builder markup. Remove the outer `<div data-content-type=…>` wrapper before storing it.
- Tyrescart sometimes resets connections or slows down after repeated full-catalog pulls. The server retries each GraphQL call 3 times (after 2s, 5s and 10s) before reporting an error.

## How it works
```
[Sync from Tyrescart]  (products page header)
  -> GET  /visionadmin/api/products/sync/fetch?page=1..10   server calls GraphQL; option IDs -> labels; price × VAT
  -> IndexedDB ProductSyncDB.remote_products (keyPath sku)
  -> POST /visionadmin/api/products/sync/compare            1,000 items per call; read-only
  -> IndexedDB ProductSyncDB.sync_meta {diff, fields, fetchedAt}
  -> Full-screen review: New / Needs update tabs, search, field toggles, checkboxes
[Import selected]
  -> POST /visionadmin/api/products/sync/import             50 rows per call: {sku} or {sku, fields}
       server re-fetches those SKUs from Tyrescart, re-diffs against the DB,
       then Product.create / Product.update (EAV + Elasticsearch reindex)
  -> imported rows leave the lists; the remaining review stays in IndexedDB
```
- The browser only chooses **which SKUs and which fields** to import. Values are always re-fetched from Tyrescart on the server, so a stale or edited IndexedDB copy can't be written to the database.
- An update writes only the selected fields that still differ at import time. Everything else on the product is untouched.
- Reloading the page resumes the last review from IndexedDB without downloading again. **Fetch again** starts a fresh pull, and **Discard sync** clears it.
- A full sync takes about 45 seconds: 10 pages of about 4–5 seconds each, then a compare of about 2 seconds.

## Field mapping
| Tyrescart field | Stored in | Notes |
|---|---|---|
| `name` | `display_name`, `name` (`{"en"}`) | compared against `display_name` |
| `status` | `status` | Enabled → `active` |
| `final_price` | `price` | `ceil(value × 1.05)`, see Decisions |
| `stock_status` | `stock_status` (+ `stock_qty`) | out of stock sets qty to 0; back in stock with qty ≤ 0 sets 10 |
| `item_code` | `item_code` | the SKU is used when it's blank on create, as the CSV import does |
| `brand` | `brand_id` | brand looked up by slug, created if missing |
| `pattern` | `tire_pattern` + attr `pattern` | |
| `tyre_size` | `tire_size_label` + attrs `tyre_size`, `tire_size` | |
| `width` / `height` / `rim` | attrs | |
| `load_index` | attrs `load_index`, `load_speed_index`; `tire_load_index` + `tire_speed_rating` | "104Y" → 104 + Y; "125/122S" kept as is |
| `tyre_marking` | attr `tyre_marking` | |
| `oem_tyres` | `oem_brand` + attr `oem_tyres` | labels comma-separated (BMW, Mercedes-Benz…) |
| `parts_category` | `parts_category`; picks the attribute set on create | |
| `tyres_category` | `tyres_category` | |
| `tyre_type` | `vehicle_type` + attr `tyre_type` | Car → car, SUV → suv, Truck Van → van |
| `country` | `country_of_origin` + attrs `country`, `origin` | |
| `ev` / `runflat` | `ev_rated` / `run_flat` | |
| `year` | `year` | |
| `warranty_period` | `warranty_months` + attr `warranty_period` | "5 Years Warranty" → 60 |
| `price_per_item` | attr `price_per_item` | raw Tyrescart value |
| `price_included_text` | `price_included` (`{"en"}`) | |
| `tabby_payment` | `pay_later_eligible` | |
| `visibility` | `visibility` | "Catalog, Search" → `visible` |
| `short_description` / `description` | `short_desc` / `description` (`{"en"}`) | compared as text, tags ignored |
| `meta_title` / `meta_description` | `meta_title` / `meta_desc` (`{"en"}`) | off by default |
| `meta_keyword` | attrs `meta_keywords`, `meta_keyword` | |
| `categories` | `product_categories` (new products only) | Tyres + Brand leaf + Tyre Size from `tyre_size`, via `CategoryImporter` |
| `url_key` | `slug` | create only |
| — | attrs `tax_class` = Taxable Goods, `promotion` = None | not available from the API |

## Files
- `app/services/product_sync.py`: GraphQL client, label resolution, normalize, compare, import
- `app/api.py`: the 3 `/visionadmin/api/products/sync/*` routes (behind the VisionAdmin auth guard; POSTs require `X-CSRF-Token`)
- `static/visionadmin/product_sync.js`: Alpine component plus the IndexedDB store
- `static/visionadmin/product_sync.css`: modal styles, scoped under `.psync`
- `templates/visionadmin/partials/product_sync_modal.html`: the full-screen modal
- `templates/visionadmin/products.html`: the button, the script/style tags, and a product-list refresh after import

## Known limitations
- Existing products don't get new categories on update. Only new products are assigned categories.
- New products don't get the local "Cars" category, which most existing products carry, because Tyrescart doesn't return it.
- `attribute_set_id` from Tyrescart (9 or 14) has no label. New products get their set from `parts_category` (Tyres → our Tyres set).
- Products that exist locally but not on Tyrescart aren't reported.

