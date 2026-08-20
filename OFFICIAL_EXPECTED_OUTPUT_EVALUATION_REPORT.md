# Official Expected-Output Evaluation Report

## Scope and source control

This report uses **only** the attached file:

`Unihack_ExpectedOutput-DeliveryFormat.csv`

No other CSV was used to profile the official expected-output schema or to compute the ground-truth results.

> The file is legitimately usable as an expected-output/reference dataset for the products and fields it contains. It is not a complete 1,000-product ground-truth set: it contains two expected product rows, so the reported ground-truth metrics apply only to those two rows.

## File profile

| Property | Verified result |
|---|---:|
| File name | `Unihack_ExpectedOutput-DeliveryFormat.csv` |
| Row count | 2 product rows |
| Column count | 252 |
| Non-empty columns | 79 |
| Completely empty columns | 173 |
| Pandas data type | `string` for the inspected columns; the file was loaded with string-preserving parsing |
| Identifier column selected | `Mfg_Part_Num` |
| LOV comparison | Not available from the supplied file/application reference data |
| UOM comparison | Available for paired `ATTRIBUTE_UOM` columns, subject to generated attribute/unit availability |
| Character-limit comparison | Not available because no verified official limits were supplied in the file/application reference data |

### Observed sample values

The two observed product identifiers are `PDSH4816AF` and `WDTS7024RZ`. Both rows have `Product Name = Dishwasher`. The `Part_Desc` values are `PDSH4816AF Dishwasher SS - Display Only` and `WDTS7024RZ Dishwasher SS - Display Only`. The file also contains source/reference URLs, manufacturer/brand-related fields, delivery fields, and paired attribute-label/value/UOM slots.

All columns, row-level non-empty counts, unique counts, data types, maximum string lengths, and sample values are preserved in the attached machine-readable profile.

## Column-role classification

The implementation classifies columns only when the header and existing application schema provide a defensible basis. A column remains `UNKNOWN` when its purpose cannot be established from those sources.

| Comparison status | Count | Meaning |
|---|---:|---|
| `SUPPORTED` | 6 | Directly comparable to an existing canonical Commerce Output/ProductRecord field |
| `PARTIALLY_SUPPORTED` | 100 | Paired dynamic attribute value/UOM slots can be compared when the generated record exposes the corresponding attribute/unit |
| `UNSUPPORTED` | 86 | The role is observable, but the application does not currently generate a comparable canonical field |
| `UNKNOWN` | 60 | No defensible semantic mapping was established |

### Directly supported columns

| Official column | Existing field | Role |
|---|---|---|
| `Mfg_Part_Num` | `sku` | Product identifier |
| `MANUFACTURER_PART_NUMBER` | `sku` | Alternate direct identifier comparison |
| `Product Name` | `name` | Product information |
| `MANUFACTURER_NAME` | `manufacturer` | Product information |
| `BRAND_NAME` | `brand` | Brand |
| `Part_Desc` | `description` | Description |

### Partially supported columns

The 100 partially supported columns are `ATTRIBUTE_VALUE 1` through `ATTRIBUTE_VALUE 50` and `ATTRIBUTE_UOM 1` through `ATTRIBUTE_UOM 50`. Values are compared only through their paired attribute labels and only when the generated Commerce Output exposes the corresponding dynamic attribute or unit.

### Recognized but unsupported columns

These include source/reference URLs (`MFR URL`, `Ref URL 1`–`Ref URL 5`), classification fields (`Dept`, `Class`, `Fine`, `Classpath`), alternate identifiers (`PART_NUMBER`, `SKU - MY_PART_NUMBER`, `ALTERNATE_PART_NUMBER`, `UPC`, `EAN`, `GTIN`, `UNSPSC`), source/reference brand and manufacturer aliases, description variants, feature slots, media/document delivery fields, commerce/delivery fields, and other fields not currently emitted by Commerce Output. The complete column list is included in the attached profile and is surfaced by the Evaluation UI.

### Unknown columns

The 60 unknown columns include `TRADE_NAME`, `With`, `Standard/Approvals`, `Prop 65`, `Application`, `Includes`, `Warranty`, `Warranty Information`, `Catalog`, and the 50 `ATTRIBUTE_LABEL` columns. Their observed values are retained and displayed, but the system does not assign an unverified canonical meaning. Attribute-label columns describe the paired dynamic slots structurally, but they are not themselves compared as generated product values.

## Ground-truth comparison results

The official file was registered through the Evaluation section and compared against the current generated product output using the canonical identifier `Mfg_Part_Num`.

| Metric | Verified result |
|---|---:|
| Total expected products | 2 |
| Products matched by identifier | 2 |
| Products missing from generated output | 0 |
| Unexpected generated products | 1,026 |
| Expected non-empty comparable cells | 42 |
| Comparable cells evaluated | 42 |
| Exact matches | 4 |
| Normalized matches | 0 |
| Partial matches | 0 |
| Missing generated values | 34 |
| Incorrect generated values | 4 |
| Overall field match rate | **9.5%** (`exact + normalized` / evaluated) |
| Overall missing-value rate | **81.0%** |
| Outcome classification coverage | 100.0% of comparable non-empty expected cells received an outcome |
| Mismatch records retained | 38 |

The top-level `ground_truth_accuracy` exposed by the application is **9.5%**, and is explicitly labeled as ground-truth evaluation. It is not a confidence score, trust score, rule-based quality score, or source-authority score.

The 1,026 unexpected products are generated records in the current application database whose identifiers are not among the two identifiers in this official file. This is expected when comparing a two-row expected-output file with a database containing a larger catalog; it should not be interpreted as a 1,000-row accuracy result.

### Field-level exact-match results

| Compared field | Expected non-empty | Exact matches | Normalized matches | Missing | Incorrect | Exact-match rate |
|---|---:|---:|---:|---:|---:|---:|
| `description` | 2 | 2 | 0 | 0 | 0 | 100.0% |
| `manufacturer` | 2 | 0 | 0 | 0 | 2 | 0.0% |
| `brand` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `sku` | 2 | 2 | 0 | 0 | 0 | 100.0% |
| `name` | 2 | 0 | 0 | 0 | 2 | 0.0% |
| `Series` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `Number of Wash Cycles` | 1 | 0 | 0 | 1 | 0 | 0.0% |
| `Voltage Rating` | 4 | 0 | 0 | 4 | 0 | 0.0% |
| `Amperage Rating` | 4 | 0 | 0 | 4 | 0 | 0.0% |
| `Mounting Type` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `Size` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `Depth With Door Open` | 4 | 0 | 0 | 4 | 0 | 0.0% |
| `Minimum Height` | 3 | 0 | 0 | 3 | 0 | 0.0% |
| `Maximum Height` | 1 | 0 | 0 | 1 | 0 | 0.0% |
| `Sound Level` | 4 | 0 | 0 | 4 | 0 | 0.0% |
| `Material` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `Additional Information` | 2 | 0 | 0 | 2 | 0 | 0.0% |
| `Color` | 1 | 0 | 0 | 1 | 0 | 0.0% |

The complete mismatch list is retained in the API response and attached machine-readable evaluation output. No expected value was replaced or fabricated.

## Application changes

### Backend

- Added `official_ground_truth_service.py` for file profiling, defensible role classification, identifier selection, exact/normalized/partial comparison, missing-value accounting, mismatch retention, and aggregate metrics.
- Extended `evaluation_schema.py` with typed official-file profile, column mapping, field metric, and aggregate ground-truth responses.
- Extended `evaluation_service.py` to register the official file, expose the schema profile, run the official comparison, and make the official aggregate comparator authoritative for public ground-truth accuracy and evaluated-field counts.
- Added Evaluation API routes for official-file schema profiling and ground-truth summary access while retaining existing rule-based evaluation and legacy routes.
- No new product/source tables were introduced. Existing expected-dataset and evaluation persistence is reused.

### Frontend

- Added Evaluation API wrappers in `frontend/src/services/api.ts`.
- Extended `EvaluationView.tsx` with the official expected-output schema/profile section, supported/partially-supported/unsupported/unknown counts, expected/matched/missing/unexpected product counts, field-level rates, missing-value rates, mismatch details, and explicit labels separating ground-truth metrics from rule-based quality metrics.

### Tests and verification

- Added regression coverage for the official schema profile, canonical identifier selection, supported/partial/unsupported/unknown classification, dynamic attributes, exact/normalized comparison, aggregate product counts, mismatch outcomes, and public ground-truth accuracy semantics.
- Complete backend suite: **140 passed** in 24.50 seconds.
- Frontend production build: **passed**; Vite transformed 1,415 modules and generated the production bundle in 2.95 seconds.

## Limitations and interpretation

The file is a valid official expected-output/reference dataset for its two rows and the supported fields described above. It is not sufficient to claim accuracy for the full 1,000-product input catalog. The supplied file does not establish official LOV definitions or character limits, so those comparisons remain unavailable. UOM columns are structurally available for comparison, but actual UOM compliance still depends on the generated record exposing a corresponding unit.

The rule-based quality score remains a separate metric and is not conflated with the ground-truth match rate. Unknown and unsupported delivery-format columns are preserved and reported rather than silently counted as incorrect or treated as comparable.
