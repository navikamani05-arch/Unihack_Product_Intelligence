import { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, FileSearch, Globe2, Link2, Loader2, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';
import { api } from '../services/api';

interface ProductListItem {
  id: number;
  sku?: string | null;
  name?: string | null;
  manufacturer?: string | null;
  category?: string | null;
  status?: string | null;
}

interface Evidence {
  evidence_chunk_id?: string | null;
  source_type?: string | null;
  source_identifier?: string | null;
  source_url?: string | null;
  page_number?: number | null;
  row_number?: number | null;
  quote?: string | null;
  authority?: string;
}

interface Attribute {
  attribute_id: number;
  name: string;
  raw_value?: string | null;
  normalized_value?: string | null;
  unit?: string | null;
  confidence?: number | null;
  validation_status: string;
  validation_explanation?: string | null;
  evidence: Evidence[];
}

interface DiscoverySource {
  id: number;
  canonical_url: string;
  title?: string | null;
  source_type: string;
  status: string;
  verification_status: string;
  identity_score: number;
  authority_score: number;
  freshness_score: number;
  evidence_score: number;
  ranking_score: number;
  explanation?: string | null;
}

interface DiscoveryEvidence {
  id: number;
  source_id: number;
  source_url: string;
  source_title?: string | null;
  source_type: string;
  attribute_name?: string | null;
  raw_value?: string | null;
  normalized_value?: string | null;
  quote: string;
  page_number?: number | null;
  evidence_quality: number;
}

interface DiscoveryDetail {
  run: { id: number; status: string; provider_status: string; accepted_count: number; rejected_count: number; summary: Record<string, unknown> };
  queries: string[];
  sources: DiscoverySource[];
  evidence: DiscoveryEvidence[];
}

interface DiscoveryProviderStatus {
  configured: boolean;
  provider?: string | null;
  message: string;
}

interface EnrichmentResult {
  run: {
    id: number;
    status: string;
    stage: string;
    product_status?: string | null;
    overall_confidence?: number | null;
    category?: string | null;
    category_path: string[];
    category_confidence?: number | null;
    product_understanding: Record<string, unknown>;
    schema_snapshot: Array<{ name: string; required?: boolean; origin?: string }>;
    missing_attributes: string[];
    progress_log: Array<{ stage: string; status: string; message: string; timestamp: string }>;
    source_count: number;
    evidence_count: number;
    attribute_count: number;
    conflict_count: number;
  };
  product: ProductListItem;
  attributes: Attribute[];
  evidence: Evidence[];
  conflicts: Array<{ id: number; attribute_name: string; severity?: string | null; status?: string | null; suggested_value?: string | null; suggestion_reason?: string | null }>;
  review_decisions: Array<{ id: number; decision: string; attribute_id?: number | null; value?: string | null; reason?: string | null }>;
}

const stageLabel = (stage: string) => stage.replaceAll('_', ' ');
const confidence = (value?: number | null) => value == null ? 'Not scored' : `${Math.round(value * 100)}%`;

export default function ProductAnalyzerView() {
  const [products, setProducts] = useState<ProductListItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [result, setResult] = useState<EnrichmentResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reviewAttribute, setReviewAttribute] = useState<number | null>(null);
  const [reviewReason, setReviewReason] = useState('');
  const [reviewValue, setReviewValue] = useState('');
  const [providerStatus, setProviderStatus] = useState<DiscoveryProviderStatus | null>(null);
  const [discovery, setDiscovery] = useState<DiscoveryDetail | null>(null);
  const [discoveryUrls, setDiscoveryUrls] = useState('');
  const [discovering, setDiscovering] = useState(false);

  const selectedProduct = useMemo(() => products.find((product) => product.id === selectedId), [products, selectedId]);

  const loadProducts = async () => {
    setLoading(true);
    try {
      const response = await api.listEnrichmentProducts();
      const rows = response.data as ProductListItem[];
      setProducts(rows);
      if (!selectedId && rows[0]) setSelectedId(rows[0].id);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Unable to load existing products for analysis.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void loadProducts();
    api.getDiscoveryProviderStatus()
      .then((response) => setProviderStatus(response.data as DiscoveryProviderStatus))
      .catch(() => setProviderStatus({ configured: false, message: 'External search provider status could not be loaded.' }));
  }, []);

  const loadResult = async (productId: number) => {
    try {
      const response = await api.getEnrichment(productId);
      setResult(response.data as EnrichmentResult);
    } catch (requestError: any) {
      if (requestError?.response?.status !== 404) setError(requestError?.response?.data?.detail || 'Unable to load enrichment details.');
    }
  };

  const loadDiscovery = async (productId: number) => {
    try {
      const response = await api.getProductDiscovery(productId);
      setDiscovery(response.data as DiscoveryDetail);
    } catch (requestError: any) {
      if (requestError?.response?.status !== 404) setError(requestError?.response?.data?.detail || 'Unable to load controlled discovery details.');
      else setDiscovery(null);
    }
  };

  useEffect(() => {
    if (selectedId) {
      void loadResult(selectedId);
      void loadDiscovery(selectedId);
    } else {
      setResult(null);
      setDiscovery(null);
    }
  }, [selectedId]);

  const analyze = async (mode: 'SOURCE_ONLY' | 'DISCOVERY_ENABLED' = 'SOURCE_ONLY') => {
    if (!selectedId) return;
    setAnalyzing(true);
    setError(null);
    try {
      await api.analyzeProduct(selectedId, false, mode);
      await Promise.all([loadResult(selectedId), loadDiscovery(selectedId)]);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Product enrichment could not complete.');
    } finally {
      setAnalyzing(false);
    }
  };

  const runDiscovery = async () => {
    if (!selectedId) return;
    setDiscovering(true);
    setError(null);
    try {
      const urls = discoveryUrls.split(/\\n|,/).map((value) => value.trim()).filter(Boolean);
      await api.runProductDiscovery(selectedId, urls);
      await loadDiscovery(selectedId);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Controlled discovery could not complete.');
    } finally {
      setDiscovering(false);
    }
  };

  const submitReview = async (action: 'APPROVE' | 'EDIT' | 'REJECT' | 'MARK_UNRESOLVED') => {
    if (!selectedId) return;
    try {
      await api.reviewEnrichment(selectedId, { action, attribute_id: reviewAttribute || undefined, value: reviewValue || undefined, reason: reviewReason || undefined });
      setReviewReason('');
      setReviewValue('');
      setReviewAttribute(null);
      await loadResult(selectedId);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Unable to save the review decision.');
    }
  };

  const download = async (format: 'json' | 'csv') => {
    if (!selectedId) return;
    const response = await api.exportEnrichment(selectedId, format);
    const url = URL.createObjectURL(new Blob([response.data]));
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = `enrichment-${selectedId}.${format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl border border-slate-200 bg-gradient-to-r from-slate-950 via-slate-900 to-indigo-950 p-7 text-white shadow-sm">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-200"><Sparkles className="h-5 w-5" /> AI understanding with governed evidence</div>
            <h1 className="text-3xl font-semibold tracking-tight">Product Analyzer</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">Analyze an existing source-backed product through transparent understanding, category, evidence, reference validation, conflict, and review stages. AI helps structure the record; evidence, rules, and people govern what can ship.</p>
          </div>
          <button onClick={() => void loadProducts()} className="inline-flex items-center justify-center gap-2 rounded-lg border border-slate-600 px-4 py-2 text-sm font-medium hover:bg-white/10"><RefreshCw className="h-4 w-4" /> Refresh products</button>
        </div>
      </section>

      {error && <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-800">{error}</div>}

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end">
          <label className="flex-1 text-sm font-medium text-slate-700">Existing product
            <select value={selectedId ?? ''} onChange={(event) => setSelectedId(Number(event.target.value) || null)} disabled={loading || !products.length} className="mt-2 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm focus:border-indigo-500 focus:outline-none">
              {!products.length && <option value="">No extracted products available</option>}
              {products.map((product) => <option key={product.id} value={product.id}>{product.sku || `Product #${product.id}`} — {product.name || 'Unnamed product'}</option>)}
            </select>
          </label>
          <div className="flex flex-wrap gap-2">
            <button onClick={() => void analyze('SOURCE_ONLY')} disabled={!selectedId || analyzing} className="inline-flex items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700 disabled:cursor-not-allowed disabled:bg-slate-300">
              {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileSearch className="h-4 w-4" />}{analyzing ? 'Analyzing…' : 'Source Only'}
            </button>
            <button onClick={() => void analyze('DISCOVERY_ENABLED')} disabled={!selectedId || analyzing} className="inline-flex items-center justify-center gap-2 rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-800 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100">
              <Globe2 className="h-4 w-4" /> Discovery Enabled
            </button>
          </div>
        </div>
        {!loading && !products.length && <p className="mt-4 rounded-lg bg-amber-50 p-3 text-sm text-amber-800">No extracted products are available yet. Use the existing Ingestion workflow and Extract Product Intelligence first; the Analyzer never invents a product record.</p>}
        {selectedProduct && <p className="mt-3 text-xs text-slate-500">Selected: {selectedProduct.manufacturer || 'Manufacturer not found in provided sources'} · {selectedProduct.category || 'Category not assigned'}</p>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col justify-between gap-4 lg:flex-row lg:items-start">
          <div>
            <h2 className="flex items-center gap-2 text-lg font-semibold text-slate-900"><Globe2 className="h-5 w-5 text-indigo-600" /> Controlled information discovery</h2>
            <p className="mt-1 max-w-3xl text-sm text-slate-500">Discovery ranks candidates, verifies identity before accepting evidence, and records rejected or unavailable outcomes. It never fabricates a source or URL.</p>
          </div>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${providerStatus?.configured ? 'bg-emerald-100 text-emerald-800' : 'bg-amber-100 text-amber-800'}`}>{providerStatus?.configured ? `Provider: ${providerStatus.provider || 'configured'}` : 'External provider not configured'}</span>
        </div>
        <p className="mt-3 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">{providerStatus?.message || 'Checking configured discovery provider…'}</p>
        <div className="mt-4 grid gap-3 lg:grid-cols-[1fr_auto]">
          <label className="text-sm font-medium text-slate-700">User-provided URLs (one per line or comma-separated)
            <textarea value={discoveryUrls} onChange={(event) => setDiscoveryUrls(event.target.value)} placeholder="https://example.com/product-page" className="mt-2 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm font-normal focus:border-indigo-500 focus:outline-none" />
          </label>
          <button onClick={() => void runDiscovery()} disabled={!selectedId || discovering} className="self-end inline-flex items-center justify-center gap-2 rounded-lg border border-indigo-300 bg-indigo-50 px-4 py-2.5 text-sm font-semibold text-indigo-800 hover:bg-indigo-100 disabled:cursor-not-allowed disabled:bg-slate-100"><Link2 className="h-4 w-4" />{discovering ? 'Checking…' : 'Run controlled discovery'}</button>
        </div>
        {discovery && <div className="mt-5 grid gap-5 xl:grid-cols-2">
          <div><h3 className="text-sm font-semibold text-slate-800">Ranked candidate sources</h3><div className="mt-3 space-y-2">{discovery.sources.length ? discovery.sources.map((source) => <div key={source.id} className="rounded-lg border border-slate-200 p-3"><div className="flex flex-wrap items-center justify-between gap-2"><a href={source.canonical_url} target="_blank" rel="noreferrer" className="max-w-md truncate text-sm font-medium text-indigo-700 hover:underline">{source.title || source.canonical_url}</a><span className={`rounded px-2 py-0.5 text-xs font-semibold ${source.status === 'accepted' ? 'bg-emerald-100 text-emerald-800' : source.status === 'rejected' ? 'bg-rose-100 text-rose-800' : 'bg-amber-100 text-amber-800'}`}>{source.status}</span></div><p className="mt-1 text-xs text-slate-500">Identity {Math.round(source.identity_score * 100)}% · Authority {Math.round(source.authority_score * 100)}% · Freshness {Math.round(source.freshness_score * 100)}% · Rank {Math.round(source.ranking_score * 100)}%</p><p className="mt-1 text-xs text-slate-600">{source.explanation || source.verification_status}</p></div>) : <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No candidate source has been accepted or rejected for this product yet.</p>}</div></div>
          <div><h3 className="text-sm font-semibold text-slate-800">Evidence chain</h3><div className="mt-3 space-y-2">{discovery.evidence.length ? discovery.evidence.map((item) => <div key={item.id} className="rounded-lg border border-slate-200 p-3"><p className="text-sm font-medium text-slate-800">{item.attribute_name || 'Product identity evidence'}{item.raw_value ? `: ${item.raw_value}` : ''}</p><p className="mt-1 text-xs leading-5 text-slate-600">“{item.quote}”</p><p className="mt-1 text-xs text-slate-500">{item.source_type} · {item.source_title || item.source_url}{item.page_number ? ` · Page ${item.page_number}` : ''} · Evidence quality {Math.round(item.evidence_quality * 100)}%</p></div>) : <p className="rounded-lg bg-slate-50 p-3 text-sm text-slate-500">No verified discovery evidence is available. Candidate pages must pass safe fetch and identity verification first.</p>}</div></div>
        </div>}
      </section>

      {result && <>
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          {[
            ['Product status', result.run.product_status || 'NEEDS_REVIEW'],
            ['Overall confidence', confidence(result.run.overall_confidence)],
            ['Evidence records', String(result.run.evidence_count)],
            ['Attributes', String(result.run.attribute_count)],
            ['Conflicts', String(result.run.conflict_count)],
          ].map(([label, value]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className="mt-2 break-words text-lg font-semibold text-slate-900">{value}</p></div>)}
        </section>

        <section className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Live pipeline stages</h2>
          <div className="mt-4 grid gap-3 lg:grid-cols-2">
            {result.run.progress_log.map((stage) => <div key={`${stage.stage}-${stage.timestamp}`} className="flex gap-3 rounded-lg border border-slate-100 p-3"><CheckCircle2 className={`mt-0.5 h-5 w-5 ${stage.status === 'warning' ? 'text-amber-500' : stage.status === 'failed' ? 'text-rose-500' : 'text-emerald-500'}`} /><div><p className="text-sm font-semibold capitalize text-slate-800">{stageLabel(stage.stage)}</p><p className="mt-1 text-xs leading-5 text-slate-500">{stage.message}</p></div></div>)}
          </div>
        </section>

        <section className="grid gap-6 xl:grid-cols-3">
          <div className="xl:col-span-2 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold text-slate-900">Enriched attributes</h2><p className="mt-1 text-sm text-slate-500">Raw source values remain intact; normalized values are displayed only when supported by existing rules or official reference data.</p></div><div className="flex gap-2"><button onClick={() => void download('json')} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium"><Download className="h-3.5 w-3.5" /> JSON</button><button onClick={() => void download('csv')} className="inline-flex items-center gap-1 rounded-lg border border-slate-300 px-3 py-2 text-xs font-medium"><Download className="h-3.5 w-3.5" /> CSV</button></div></div>
            <div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="border-b border-slate-200 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-2">Attribute</th><th className="px-3 py-2">Value</th><th className="px-3 py-2">Confidence</th><th className="px-3 py-2">Validation</th><th className="px-3 py-2">Evidence</th></tr></thead><tbody>{result.attributes.map((attribute) => <tr key={attribute.attribute_id} className="border-b border-slate-100 align-top"><td className="px-3 py-3 font-medium text-slate-800">{attribute.name}</td><td className="px-3 py-3 text-slate-700">{attribute.normalized_value || attribute.raw_value || <span className="text-amber-700">Missing</span>}{attribute.unit ? ` ${attribute.unit}` : ''}</td><td className="px-3 py-3 text-slate-700">{confidence(attribute.confidence)}</td><td className="px-3 py-3"><span className={`rounded-full px-2 py-1 text-xs font-medium ${attribute.validation_status === 'INVALID_REFERENCE_DATA' ? 'bg-rose-100 text-rose-700' : attribute.validation_status === 'SOURCE_BACKED' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>{attribute.validation_status.replaceAll('_', ' ')}</span>{attribute.validation_explanation && <p className="mt-1 text-xs text-slate-500">{attribute.validation_explanation}</p>}</td><td className="px-3 py-3 text-xs text-slate-600">{attribute.evidence.map((evidence, index) => <div key={`${evidence.evidence_chunk_id || index}`} className="mb-1">{evidence.source_type || 'Source'} · {evidence.source_identifier || evidence.source_url || 'Source reference'}{evidence.page_number ? ` · Page ${evidence.page_number}` : ''}{evidence.row_number ? ` · Row ${evidence.row_number}` : ''}</div>)}{!attribute.evidence.length && 'No linked evidence'}</td></tr>)}</tbody></table></div>
          </div>
          <aside className="space-y-5">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-900">Category & schema</h2><p className="mt-3 text-sm text-slate-700">{result.run.category || 'Category needs review'}</p><p className="mt-1 text-xs text-slate-500">Confidence: {confidence(result.run.category_confidence)} · {result.run.category_path.join(' › ') || 'No category path'}</p><div className="mt-4 space-y-2">{result.run.schema_snapshot.map((attribute) => <div key={attribute.name} className="rounded bg-slate-50 px-3 py-2 text-xs text-slate-600">{attribute.name}{attribute.required ? ' · required' : ''}<span className="float-right text-slate-400">{attribute.origin || 'core'}</span></div>)}</div></div>
            <div className="rounded-xl border border-amber-200 bg-amber-50 p-5"><h2 className="flex items-center gap-2 text-lg font-semibold text-amber-900"><ShieldAlert className="h-5 w-5" /> Missing / review items</h2><div className="mt-3 space-y-2 text-sm text-amber-900">{result.run.missing_attributes.length ? result.run.missing_attributes.map((item) => <p key={item}>• {item}</p>) : <p>No required attributes are currently marked missing.</p>}</div></div>
          </aside>
        </section>

        <section className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-900">Conflicts requiring review</h2><div className="mt-4 space-y-3">{result.conflicts.length ? result.conflicts.map((conflict) => <div key={conflict.id} className="rounded-lg border border-rose-100 bg-rose-50 p-3"><div className="flex items-center justify-between gap-2"><p className="font-medium text-rose-900">{conflict.attribute_name}</p><span className="rounded bg-rose-200 px-2 py-0.5 text-xs font-semibold text-rose-800">{conflict.severity || 'REVIEW'}</span></div><p className="mt-1 text-xs text-rose-800">{conflict.suggestion_reason || 'Conflicting source-backed values are preserved for human review.'}</p></div>) : <p className="text-sm text-slate-500">No persisted conflicts are linked to this product.</p>}</div></div>
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"><h2 className="text-lg font-semibold text-slate-900">Human review</h2><p className="mt-1 text-sm text-slate-500">Review decisions are recorded separately and never overwrite extracted source values or evidence.</p><select value={reviewAttribute ?? ''} onChange={(event) => setReviewAttribute(Number(event.target.value) || null)} className="mt-4 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm"><option value="">Product-level review</option>{result.attributes.map((attribute) => <option key={attribute.attribute_id} value={attribute.attribute_id}>{attribute.name}</option>)}</select><input value={reviewValue} onChange={(event) => setReviewValue(event.target.value)} placeholder="Optional reviewer value for Edit" className="mt-3 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /><textarea value={reviewReason} onChange={(event) => setReviewReason(event.target.value)} placeholder="Optional reviewer reasoning" className="mt-3 min-h-20 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm" /><div className="mt-3 flex flex-wrap gap-2"><button onClick={() => void submitReview('APPROVE')} className="rounded-lg bg-emerald-600 px-3 py-2 text-xs font-semibold text-white">Approve</button><button onClick={() => void submitReview('EDIT')} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white">Record edit</button><button onClick={() => void submitReview('REJECT')} className="rounded-lg bg-rose-600 px-3 py-2 text-xs font-semibold text-white">Reject</button><button onClick={() => void submitReview('MARK_UNRESOLVED')} className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700">Unresolved</button></div></div>
        </section>
      </>}
    </div>
  );
}
