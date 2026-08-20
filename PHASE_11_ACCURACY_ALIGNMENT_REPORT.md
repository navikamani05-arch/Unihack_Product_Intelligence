# Phase 11 — AI Accuracy Improvement & Official Output Alignment

**Project:** AI Product Intelligence & Trust Engine  
**Official reference file:** `Unihack_ExpectedOutput-DeliveryFormat.csv`  
**Evaluation date:** 2026-08-19  
**Author:** Manus AI

## Executive Summary

The official expected-output evaluation was rerun using only the supplied `Unihack_ExpectedOutput-DeliveryFormat.csv`. The result improved from a verified **9.5% field match rate** to **14.3%** without fabricating product attributes or hardcoding either official product.

The improvement came from generalized product-name normalization. The pipeline now derives a canonical product type such as `Dishwasher` from a source-backed description such as `PDSH4816AF Dishwasher SS - Display Only`, while retaining the full original description and its provenance in the `Part_Desc` field. The evaluator also now distinguishes **source data unavailable** from a genuine **pipeline missing** condition.

The principal limitation remains the official input data. The raw input file contains only six columns, and the two official rows provide an identifier, description, distributor/manufacturer-source text, and placeholder brand values. The 34 expected dynamic attribute values that remain missing are not present in the supplied source evidence. The manufacturer values in the official expected output also disagree factually with the source input. The system therefore reports these cases transparently rather than inventing values.

## Verified Before and After Metrics

| Metric | BEFORE verified result | AFTER verified result | Interpretation |
|---|---:|---:|---|
| Expected products | 2 | 2 | Official rows for `PDSH4816AF` and `WDTS7024RZ` |
| Products matched | 2 | 2 | Both official identifiers were found in generated output |
| Products missing from output | 0 | 0 | No official product row was absent |
| Unexpected products | Not recorded in the original Phase 11 baseline | 1,026 | Existing catalog database contains additional generated products; these are reported, not compared as expected rows |
| Comparable cells | 42 | 42 | Same defensible comparison denominator |
| Exact matches | 4 | 6 | Both normalized product names now match exactly |
| Normalized matches | 0 | 0 | No additional normalized-only matches were recorded |
| Partial matches | 0 | 0 | No partial matches were recorded |
| Missing generated values | 34 | 34 | All are classified as source-data-unavailable; pipeline-missing is zero |
| Incorrect generated values | 4 | 2 | The two remaining incorrect values are source-vs-expected manufacturer discrepancies |
| Field match rate | **9.5%** | **14.3%** | `6 / 42` comparable cells match after the generalized change |
| Source-data-unavailable outcomes | Not available | 34 | Newly reported availability classification |
| Pipeline-missing outcomes | Not available | 0 | No expected field had source evidence but lacked a generated value |
| Overall evaluation coverage | Not recorded in the original baseline | 100.0% | Both expected products were evaluated |

The official evaluation response used for the AFTER result is saved in [`phase11_after_metrics.json`](phase11_after_metrics.json). The browser smoke-test observations are saved in [`phase11_browser_smoke_findings.md`](phase11_browser_smoke_findings.md).

## Official Source and Expected-Output Facts

The official expected-output file contains **2 rows and 252 columns**. Its canonical identifier is `Mfg_Part_Num`. The supported comparison set contains 42 non-empty expected cells across the two official products. The raw input file used to create the generated records is `Unihack_SampleDataset-Input.csv`; its relevant official rows contain only the following six columns:

| Source column | Observed status in the official rows | Use in the evaluation |
|---|---|---|
| `Mfg_Part_Num` | Populated with the official identifiers | Supports SKU/product matching |
| `Part_Desc` | Populated with full descriptions | Supports description and generalized product-name derivation |
| `E1_Brand` | Placeholder (`-- Unbranded --`) | Correctly excluded as non-evidence |
| `Unilog_Brand` | Placeholder (`-- No Unilog Brand --`) | Correctly excluded as non-evidence |
| `DIB_Brand` | Placeholder (`-- No DIB Brand --`) | Correctly excluded as non-evidence |
| `Part_Manuf` | `Appliance Dealers Cooperative (APPDE)` | Source-backed manufacturer/distributor text; it does not equal the official expected manufacturer values |

The expected output contains additional manufacturer, brand, product-name, and dynamic attribute fields. A value appearing only in the expected-output file is not treated as source evidence for extraction.

## Complete Mismatch Diagnosis

The table below consolidates the official comparison rows into canonical delivery fields. Dynamic `ATTRIBUTE_VALUE` and `ATTRIBUTE_UOM` cells are shown as one field where the official file defines a label/value/UOM triplet. This avoids double-counting the same attribute in the diagnosis while preserving the evaluator's actual 42-cell denominator.

| Product ID | Field | Expected value | Generated value | Evidence available? | Source/provenance | Reason for mismatch or match | Recommended fix |
|---|---|---|---|---|---|---|---|
| `PDSH4816AF` | SKU / Product ID | `PDSH4816AF` | `PDSH4816AF` | Yes | CSV `Unihack_SampleDataset-Input.csv`, `Mfg_Part_Num`, row 1 | Exact source-backed identifier match | None |
| `PDSH4816AF` | Part description | `PDSH4816AF Dishwasher SS - Display Only` | Same full description | Yes | CSV `Part_Desc`, row 1 | Exact match | None |
| `PDSH4816AF` | Manufacturer | `Rheem Manufacturing` | `Appliance Dealers Cooperative (APPDE)` | Yes, but different fact | CSV `Part_Manuf`, row 1 | The source contains a different manufacturer/distributor value; the expected value is not in the source | Correct the upstream source or supply manufacturer evidence; do not overwrite the source-backed value |
| `PDSH4816AF` | Brand | `FRIGIDAIRE®` | Missing | No usable evidence | Brand columns are placeholders in CSV row 1 | Placeholder values are intentionally filtered and cannot support a brand | Supply a non-placeholder brand source |
| `PDSH4816AF` | Product Name | `Dishwasher` | `Dishwasher` after normalization | Yes | Derived from CSV `Part_Desc`, row 1; raw description retained separately | Generalized title normalization strips the leading part number and merchandising suffix | None |
| `PDSH4816AF` | Series | `Gallery` | Missing | No | No series field or descriptive series evidence in the six-column source | Expected value is absent from source | Supply a richer product source |
| `PDSH4816AF` | Number of Wash Cycles | `5` | Missing | No | No dynamic attribute evidence in CSV row 1 | Expected value is absent from source | Supply labeled attribute evidence |
| `PDSH4816AF` | Voltage Rating | `120 V` | Missing | No | No voltage field in CSV row 1 | Expected value and UOM are absent from source | Supply voltage evidence |
| `PDSH4816AF` | Amperage Rating | `15 A` | Missing | No | No amperage field in CSV row 1 | Expected value and UOM are absent from source | Supply amperage evidence |
| `PDSH4816AF` | Mounting Type | `Leg` | Missing | No | No mounting field in CSV row 1 | Expected value is absent from source | Supply mounting evidence |
| `PDSH4816AF` | Size | `24 in W x 24-1/4 in D` | Missing | No | No size/dimension field in CSV row 1 | Expected value is absent from source | Supply dimension evidence |
| `PDSH4816AF` | Depth With Door Open | `50-1/4 in` | Missing | No | No depth field in CSV row 1 | Expected value and UOM are absent from source | Supply dimension evidence |
| `PDSH4816AF` | Minimum Height | `8-1/2 in Upper Rack, 11-1/4 in Lower Rack` | Missing | No | No minimum-height field in CSV row 1 | Expected value is absent from source | Supply labeled height evidence |
| `PDSH4816AF` | Maximum Height | `10-3/8 in Upper Rack, 13-1/4 in Lower Rack` | Missing | No | No maximum-height field in CSV row 1 | Expected value is absent from source | Supply labeled height evidence |
| `PDSH4816AF` | Sound Level | `47 dBA` | Missing | No | No sound-level field in CSV row 1 | Expected value and UOM are absent from source | Supply sound-level evidence |
| `PDSH4816AF` | Material | `Stainless Steel` | Missing | No | No material field in CSV row 1 | Expected value is absent from source | Supply material evidence |
| `PDSH4816AF` | Additional Information | `240 kW-hr Annual Energy, 1 to 12 hr Delay Start Hours` | Missing | No | No additional-information field in CSV row 1 | Expected value is absent from source | Supply labeled product-information evidence |
| `PDSH4816AF` | Color | Expected field is non-empty in the official comparison set | Missing | No | No color field in CSV row 1 | Expected value is absent from source | Supply color evidence |
| `WDTS7024RZ` | SKU / Product ID | `WDTS7024RZ` | `WDTS7024RZ` | Yes | CSV `Unihack_SampleDataset-Input.csv`, `Mfg_Part_Num`, row 66 | Exact source-backed identifier match | None |
| `WDTS7024RZ` | Part description | `WDTS7024RZ Dishwasher SS - Display Only` | Same full description | Yes | CSV `Part_Desc`, row 66 | Exact match | None |
| `WDTS7024RZ` | Manufacturer | `Whirlpool Corporation` | `Appliance Dealers Cooperative (APPDE)` | Yes, but different fact | CSV `Part_Manuf`, row 66 | The source contains a different manufacturer/distributor value; the expected value is not in the source | Correct the upstream source or supply manufacturer evidence; do not overwrite the source-backed value |
| `WDTS7024RZ` | Brand | `Whirlpool®` | Missing | No usable evidence | Brand columns are placeholders in CSV row 66 | Placeholder values are intentionally filtered and cannot support a brand | Supply a non-placeholder brand source |
| `WDTS7024RZ` | Product Name | `Dishwasher` | `Dishwasher` after normalization | Yes | Derived from CSV `Part_Desc`, row 66; raw description retained separately | Generalized title normalization strips the leading part number and merchandising suffix | None |
| `WDTS7024RZ` | Series | `Eco Series` | Missing | No | No series field or descriptive series evidence in the six-column source | Expected value is absent from source | Supply a richer product source |
| `WDTS7024RZ` | Number of Wash Cycles | Expected field is populated in the official file | Missing | No | No wash-cycle field in CSV row 66 | Expected value is absent from source | Supply labeled attribute evidence |
| `WDTS7024RZ` | Voltage Rating | `120 V` | Missing | No | No voltage field in CSV row 66 | Expected value and UOM are absent from source | Supply voltage evidence |
| `WDTS7024RZ` | Amperage Rating | `10 A` | Missing | No | No amperage field in CSV row 66 | Expected value and UOM are absent from source | Supply amperage evidence |
| `WDTS7024RZ` | Mounting Type | `Built-in` | Missing | No | No mounting field in CSV row 66 | Expected value is absent from source | Supply mounting evidence |
| `WDTS7024RZ` | Size | `33-7/16 in H x 23-7/8 in W x 22-5/8 in D` | Missing | No | No size/dimension field in CSV row 66 | Expected value is absent from source | Supply dimension evidence |
| `WDTS7024RZ` | Depth With Door Open | `50-3/16 in` | Missing | No | No depth field in CSV row 66 | Expected value and UOM are absent from source | Supply dimension evidence |
| `WDTS7024RZ` | Minimum Height | `33-7/16 in` | Missing | No | No minimum-height field in CSV row 66 | Expected value and UOM are absent from source | Supply labeled height evidence |
| `WDTS7024RZ` | Maximum Height | Expected field is present in the official comparison set | Missing | No | No maximum-height field in CSV row 66 | Expected value is absent from source | Supply labeled height evidence |
| `WDTS7024RZ` | Sound Level | `41 dBA` | Missing | No | No sound-level field in CSV row 66 | Expected value and UOM are absent from source | Supply sound-level evidence |
| `WDTS7024RZ` | Material | `Stainless Steel` | Missing | No | No material field in CSV row 66 | Expected value is absent from source | Supply material evidence |
| `WDTS7024RZ` | Additional Information | `Folding Tines, Leak Detection System, Moisture Repellent Silverware Basket, Normal Cycle, Quick Wash Cycle, Sani Rinse Option, Sensor Cycle, Triple Wash Spray` | Missing | No | No additional-information field in CSV row 66 | Expected value is absent from source | Supply labeled product-information evidence |
| `WDTS7024RZ` | Color | `Stainless Steel` | Missing | No | No color field in CSV row 66 | Expected value is absent from source | Supply color evidence |

The exact per-cell evaluator trace, including official field names and paired dynamic attribute columns, is saved in [`phase11_comparison_rows.json`](phase11_comparison_rows.json) and [`phase11_official_trace.txt`](phase11_official_trace.txt).

## Root-Cause Analysis

### Source-data limitations

The dominant cause of the missing values is **absence of source evidence**, not extraction failure. The raw input CSV has only six columns. It does not contain Series, wash cycles, voltage, amperage, mounting type, size, depth, height, sound level, material, additional information, or color. The expected values for those fields appear in the official delivery file but not in the source input. The system must not use expected-output values as extraction evidence, so these fields remain missing by design.

The brand columns contain explicit placeholders. Filtering those placeholders is correct anti-hallucination behavior; promoting them to `FRIGIDAIRE®` or `Whirlpool®` would fabricate values. Similarly, `Part_Manuf` contains `Appliance Dealers Cooperative (APPDE)`, while the expected output contains `Rheem Manufacturing` and `Whirlpool Corporation`. This is a factual source/expected-data discrepancy, not a normalization defect.

### Generalized pipeline gap corrected

The source descriptions contained a merchandising-style identifier and suffix around a useful canonical product type. The pipeline previously used the full description as the `Product Name` value. A new dependency-light normalizer now removes a leading identifier-like token and trailing display/finish qualifiers only when the remaining text is meaningful. It is generalized and does not contain either official SKU or any expected value. The full raw description remains available in `Part_Desc`, raw values, evidence, and provenance snapshots.

The Commerce Output and enrichment output paths now apply the same generalized title behavior. Brand alias promotion and reference validation were broadened for supported, non-placeholder source aliases, but the official two rows still contain only placeholders; therefore no brand improvement is claimed for this evaluation.

The official comparator now reports `source_data_unavailable` and `pipeline_missing`. In the verified run, all 34 missing cells were source-data-unavailable and **zero** were pipeline-missing. This makes the evaluation more honest without changing the comparable-cell denominator or inventing accuracy.

## Implemented Changes

| File | Change |
|---|---|
| `backend/app/services/text_normalization.py` | Added a dependency-light generalized product-name normalizer for identifier prefixes and merchandising suffixes. |
| `backend/app/services/enrichment/output_builder.py` | Applied normalized product-name generation and generalized non-placeholder brand-alias promotion while retaining raw source values and provenance. |
| `backend/app/services/commerce_output_service.py` | Applied the same normalized title and brand-alias resolution to persisted Commerce Output fields and evidence snapshots. |
| `backend/app/services/official_ground_truth_service.py` | Added source-availability classification and broadened supported brand-alias handling without changing official comparison semantics. |
| `backend/app/services/reference_data_service.py` | Recognized supported brand aliases while preserving placeholder filtering and evidence-backed validation. |
| `backend/app/schemas/evaluation_schema.py` | Added backward-compatible API fields for source-data-unavailable and pipeline-missing counts. |
| `frontend/src/pages/EvaluationView.tsx` | Added source-data-unavailable and pipeline-missing summary cards, field-level availability counts, and mismatch availability labels. |
| `backend/tests/test_phase11_accuracy.py` | Added regression tests for product-name normalization, brand-alias promotion, and source-unavailable reporting. |
| `phase11_after_metrics.json` | Saved the real official post-change evaluation response. |
| `phase11_browser_smoke_findings.md` | Saved browser verification observations. |

No product-specific rule was added. No official expected value was inserted into the extraction pipeline. No database schema change was required for these Phase 11 changes.

## Verification Results

The complete backend suite passed:

> **143 passed** in 21.73 seconds.

The frontend production build passed with Vite:

> **Build successful** — 1,415 modules transformed; production assets emitted under `frontend/dist/`.

The browser smoke test passed at the live preview URL. The Evaluation page loaded, the official schema displayed 2 expected products and 252 columns, the ground-truth card displayed **14.3%**, and the new summary displayed **34 source-data-unavailable** and **0 pipeline-missing** outcomes. No browser runtime error was observed.

## Remaining Mismatches and Honest Limitations

The remaining two incorrect cells are manufacturer mismatches. The source-backed value is `Appliance Dealers Cooperative (APPDE)` for both official rows, while the official expected values are `Rheem Manufacturing` and `Whirlpool Corporation`. The application retains and reports the source value rather than silently replacing it.

The remaining 34 missing cells cannot be improved from the six-column raw input alone. The pipeline cannot extract information that is absent from source evidence, and the expected-output file is used only for evaluation, not as an extraction source. A richer input catalog, manufacturer specification sheet, product webpage, or other authoritative source would be required to improve those fields.

The evaluator reports 1,026 unexpected products because the local database includes prior catalog-processing output beyond the two official expected rows. The official product matching and comparable-cell metrics remain scoped to the two expected identifiers. A clean evaluation database or an explicit generated-output subset would be required if the submission needs an unexpected-product count of zero.

No claim is made for Unilog LOV compliance, official UOM compliance, character-limit compliance, or ground-truth values outside the columns and mappings defensibly established from the supplied official file.

## Conclusion

Phase 11 is implemented and verified. The measured field match rate increased from **9.5% to 14.3%**, exact matches increased from **4 to 6**, and incorrect values decreased from **4 to 2**. The improvement is generalized, source-backed, provenance-preserving, and honest about unavailable source data. The application does not fabricate the 34 absent attributes or overwrite the two manufacturer discrepancies.

## References

[1]: `OFFICIAL_EXPECTED_OUTPUT_EVALUATION_REPORT.md` "Official expected-output schema and ground-truth evaluation report"
[2]: `phase11_after_metrics.json` "Verified Phase 11 official evaluation response"
[3]: `phase11_official_trace.txt` "Official product evidence and comparison trace"
[4]: `phase11_browser_smoke_findings.md` "Phase 11 browser smoke-test findings"
[5]: `backend/data/evaluation/Unihack_SampleDataset-Input.csv` "Raw input catalog used for source-backed evaluation"
