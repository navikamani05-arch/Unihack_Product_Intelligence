import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Loader2, RefreshCw, ShieldCheck } from 'lucide-react';
import { api } from '../services/api';

interface ProductItem { id: number; sku?: string | null; name?: string | null; manufacturer?: string | null; category?: string | null; }
interface OutputField {
  id: number; field_key: string; display_name: string; raw_value?: string | null; normalized_value?: string | null; output_value?: string | null; unit?: string | null;
  field_status: string; validation_status: string; validation_explanation?: string | null; reference_dataset?: string | null;
  character_limit?: number | null; character_limit_status: string; confidence?: number | null; evidence: Array<Record<string, unknown>>;
  conflict_ids: number[]; review_state: string; review?: Record<string, unknown> | null;
}
interface CommerceOutput {
  id: number; product_id: number; enrichment_run_id: number; output_version: string; status: string; overall_confidence?: number | null;
  product: ProductItem; record: Record<string, unknown>; fields: OutputField[];
  validation: { overall_status: string; fields_total: number; fields_populated: number; fields_missing: number; fields_with_conflicts: number; fields_requiring_review: number; reference_data_available: boolean; reference_data_unavailable_fields: number; invalid_reference_fields: number; character_limit_checked: number; character_limit_unavailable: number; character_limit_violations: number; notes: string[] };
  sources: Array<Record<string, unknown>>; conflicts: Array<Record<string, unknown>>; reviews: Array<Record<string, unknown>>; ground_truth_accuracy: string;
}

const pretty = (value: unknown) => value == null || value === '' ? 'Not available' : String(value);
const percent = (value?: number | null) => value == null ? 'Not scored' : `${Math.round(value * 100)}%`;
const badge = (status: string) => status === 'READY' || status === 'PRESENT' || status === 'REFERENCE_APPROVED' || status === 'PASS'
  ? 'bg-emerald-100 text-emerald-800' : status === 'MISSING' || status === 'REFERENCE_INVALID' || status === 'FAIL' || status === 'CONFLICT'
    ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800';

export default function CommerceOutputView() {
  const [products, setProducts] = useState<ProductItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [output, setOutput] = useState<CommerceOutput | null>(null);
  const [loading, setLoading] = useState(true);
  const [working, setWorking] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedProduct = useMemo(() => products.find((product) => product.id === selectedId), [products, selectedId]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const response = await api.listEnrichmentProducts();
      const rows = response.data as ProductItem[];
      setProducts(rows);
      if (!selectedId && rows[0]) setSelectedId(rows[0].id);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Unable to load enriched products.');
    } finally { setLoading(false); }
  };

  const loadOutput = async (productId: number) => {
    try {
      const response = await api.getCommerceOutput(productId);
      setOutput(response.data as CommerceOutput);
      setError(null);
    } catch (requestError: any) {
      if (requestError?.response?.status === 404) setOutput(null);
      else setError(requestError?.response?.data?.detail || 'Unable to load Commerce Output.');
    }
  };

  useEffect(() => { void loadProducts(); }, []);
  useEffect(() => { if (selectedId) void loadOutput(selectedId); else setOutput(null); }, [selectedId]);

  const generate = async () => {
    if (!selectedId) return;
    setWorking(true); setError(null);
    try {
      const response = await api.generateCommerceOutput(selectedId);
      setOutput(response.data as CommerceOutput);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Commerce Output generation failed. Run Product Analyzer first.');
    } finally { setWorking(false); }
  };

  const download = async (format: 'json' | 'csv' | 'xlsx') => {
    if (!selectedId) return;
    try {
      const response = await api.exportCommerceOutput(selectedId, format);
      const url = URL.createObjectURL(new Blob([response.data]));
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = `commerce-output-${selectedId}.${format}`; anchor.click(); URL.revokeObjectURL(url);
    } catch (requestError: any) { setError(requestError?.response?.data?.detail || `Unable to download ${format.toUpperCase()} output.`); }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-gradient-to-r from-emerald-950 via-slate-900 to-indigo-950 p-7 text-white shadow-sm">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
          <div><div className="mb-2 flex items-center gap-2 text-emerald-200"><ShieldCheck className="h-5 w-5" /> Delivery layer</div><h1 className="text-3xl font-semibold tracking-tight">Commerce Output</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">Generate a stable, exportable catalog record from the latest source-backed enrichment result. Raw values, normalized values, evidence, provenance, validation, conflicts, confidence, and review state remain visible.</p></div>
          <button onClick={() => void loadProducts()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:bg-white/10"><RefreshCw className="h-4 w-4" /> Refresh products</button>
        </div>
      </section>
      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}
      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <label className="flex-1 text-sm font-medium text-slate-700">Enriched product<select value={selectedId ?? ''} onChange={(event) => setSelectedId(Number(event.target.value) || null)} disabled={loading || !products.length} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none"><option value="">{loading ? 'Loading…' : 'No enriched products available'}</option>{products.map((product) => <option key={product.id} value={product.id}>{product.sku || `Product #${product.id}`} — {product.name || 'Unnamed product'}</option>)}</select></label>
          <button onClick={() => void generate()} disabled={!selectedId || working} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">{working ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />}{working ? 'Generating…' : 'Generate Commerce Output'}</button>
        </div>
        {selectedProduct && <p className="mt-3 text-xs text-slate-500">Selected: {selectedProduct.manufacturer || 'Manufacturer not found in provided sources'} · {selectedProduct.category || 'Category not assigned'}</p>}
      </section>
      {!output && selectedId && <section className="rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-900">No Commerce Output snapshot is available yet. Generate it after running Product Analyzer; the delivery layer does not invent a product or expected catalog values.</section>}
      {output && <>
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {[["Status", output.status], ["Fields", `${output.validation.fields_populated}/${output.validation.fields_total} populated`], ["Conflicts", output.validation.fields_with_conflicts], ["Review", output.validation.fields_requiring_review], ["Confidence", percent(output.overall_confidence)]].map(([label, value]) => <div key={String(label)} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 text-xl font-semibold text-slate-900">{pretty(value)}</p></div>)}
        </section>
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start"><div><h2 className="text-lg font-semibold text-slate-900">Final catalog record</h2><p className="mt-1 text-sm text-slate-500">Output version {output.output_version}; ground-truth accuracy: <strong>Unavailable</strong>.</p></div><div className="flex flex-wrap gap-2"><button onClick={() => void download('json')} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><Download className="h-4 w-4" /> JSON</button><button onClick={() => void download('csv')} className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"><Download className="h-4 w-4" /> CSV</button><button onClick={() => void download('xlsx')} className="inline-flex items-center gap-2 rounded-lg border border-emerald-300 bg-emerald-50 px-3 py-2 text-sm font-semibold text-emerald-800 hover:bg-emerald-100"><FileSpreadsheet className="h-4 w-4" /> Excel</button></div></div><div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">{Object.entries(output.record).filter(([key]) => key !== 'attributes').map(([key, value]) => <div key={key} className="rounded-lg bg-slate-50 p-3"><p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 break-words text-sm font-medium text-slate-900">{pretty(value)}</p></div>)}</div></section>
        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-900">Field-level audit</h2><div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-3">Field</th><th className="px-3 py-3">Output</th><th className="px-3 py-3">Raw / normalized</th><th className="px-3 py-3">Validation</th><th className="px-3 py-3">Evidence</th></tr></thead><tbody>{output.fields.map((field) => <tr key={field.id} className="border-b border-slate-100 align-top"><td className="px-3 py-3"><p className="font-semibold text-slate-900">{field.display_name}</p><span className={`mt-1 inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ${badge(field.field_status)}`}>{field.field_status}</span></td><td className="px-3 py-3 font-medium text-slate-900">{pretty(field.output_value)}{field.unit ? ` ${field.unit}` : ''}<p className="mt-1 text-xs text-slate-500">Confidence: {percent(field.confidence)} · Review: {field.review_state}</p></td><td className="px-3 py-3 text-xs text-slate-600"><div>Raw: {pretty(field.raw_value)}</div><div>Normalized: {pretty(field.normalized_value)}</div></td><td className="max-w-xs px-3 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${badge(field.validation_status)}`}>{field.validation_status}</span><p className="mt-1 text-xs text-slate-500">{field.validation_explanation || 'No explanation available.'}</p><p className="mt-1 text-xs text-slate-500">Character limit: {field.character_limit_status}{field.character_limit ? ` (${field.character_limit})` : ''}</p></td><td className="px-3 py-3 text-xs text-slate-600">{field.evidence.length ? field.evidence.map((evidence, index) => <div key={`${field.id}-${index}`} className="mb-2 rounded bg-slate-50 p-2"><div>{pretty(evidence.source_type)} · {pretty(evidence.source_identifier || evidence.source_url)}</div><div>Page {pretty(evidence.page_number)} · Row {pretty(evidence.row_number)}</div>{evidence.quote && <div className="mt-1 italic">“{String(evidence.quote)}”</div>}</div>) : <span className="text-amber-700">No field-level provenance retained</span>}</td></tr>)}</tbody></table></div></section>
        <section className="grid gap-5 lg:grid-cols-2"><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900"><CheckCircle2 className="h-5 w-5 text-emerald-600" /> Validation state</h2><div className="mt-3 space-y-2 text-sm text-slate-600"><p>Reference data available: <strong>{output.validation.reference_data_available ? 'Yes' : 'No / partial'}</strong></p><p>Reference-unavailable fields: <strong>{output.validation.reference_data_unavailable_fields}</strong></p><p>Invalid reference fields: <strong>{output.validation.invalid_reference_fields}</strong></p><p>Official character limits checked: <strong>{output.validation.character_limit_checked}</strong></p><p>Character-limit violations: <strong>{output.validation.character_limit_violations}</strong></p>{output.validation.notes.map((note) => <p key={note} className="rounded bg-amber-50 p-2 text-amber-800">{note}</p>)}</div></div><div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900"><AlertTriangle className="h-5 w-5 text-amber-600" /> Conflicts and review</h2><div className="mt-3 space-y-2 text-sm">{output.conflicts.length ? output.conflicts.map((conflict, index) => <div key={`${String(conflict.id)}-${index}`} className="rounded-lg border border-rose-100 bg-rose-50 p-3 text-rose-900">{pretty(conflict.attribute_name)} · {pretty(conflict.severity)} · {pretty(conflict.status)}</div>) : <p className="text-slate-500">No persisted product conflicts were propagated.</p>}{output.reviews.length > 0 && <p className="mt-3 text-slate-600">{output.reviews.length} non-destructive review decision(s) are retained.</p>}</div></div></section>
      </>}
    </div>
  );
}
