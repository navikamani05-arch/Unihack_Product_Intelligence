import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  HelpCircle,
  Database,
  Download,
  FileCheck2,
  FileSearch,
  Gauge,
  Layers3,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  BadgeCheck,
  XCircle,
} from 'lucide-react';
import { api } from '../services/api';

type AnyRecord = Record<string, any>;

const toneClasses: AnyRecord = {
  AVAILABLE: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  READY: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  COMPLETED: 'bg-emerald-50 text-emerald-700 border-emerald-200',
  PROVIDER_NOT_CONFIGURED: 'bg-amber-50 text-amber-700 border-amber-200',
  UNAVAILABLE: 'bg-slate-100 text-slate-600 border-slate-200',
  REFERENCE_DATA_UNAVAILABLE: 'bg-amber-50 text-amber-700 border-amber-200',
  REVIEW_REQUIRED: 'bg-amber-50 text-amber-700 border-amber-200',
  FAILED: 'bg-rose-50 text-rose-700 border-rose-200',
};

const displayValue = (value: any) => {
  if (value === null || value === undefined || value === '') return 'Not available';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
};

const formatMetric = (value: any) => {
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toLocaleString() : value.toFixed(1);
  return value;
};

const StatusPill: React.FC<{ status?: string; label?: string }> = ({ status = 'UNAVAILABLE', label }) => (
  <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide ${toneClasses[status] || toneClasses.UNAVAILABLE}`}>
    {label || status.replaceAll('_', ' ')}
  </span>
);

const SectionHeader: React.FC<{ eyebrow: string; title: string; description?: string; icon?: React.ReactNode }> = ({ eyebrow, title, description, icon }) => (
  <div className="mb-4 flex items-start justify-between gap-4">
    <div>
      <div className="mb-1 flex items-center gap-2 text-[11px] font-bold uppercase tracking-[0.18em] text-indigo-600">
        {icon}
        {eyebrow}
      </div>
      <h2 className="text-xl font-semibold tracking-tight text-slate-900">{title}</h2>
      {description && <p className="mt-1 max-w-3xl text-sm leading-6 text-slate-500">{description}</p>}
    </div>
  </div>
);

const MetricCard: React.FC<{ label: string; value: any; explanation?: string; status?: string; icon: React.ReactNode }> = ({ label, value, explanation, status, icon }) => (
  <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
    <div className="flex items-start justify-between gap-3">
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{label}</p>
        <p className="mt-3 text-3xl font-semibold tracking-tight text-slate-950">{formatMetric(value)}</p>
      </div>
      <div className="rounded-xl bg-indigo-50 p-3 text-indigo-600">{icon}</div>
    </div>
    {status && status !== 'AVAILABLE' && <div className="mt-3"><StatusPill status={status} /></div>}
    {explanation && <p className="mt-3 text-xs leading-5 text-slate-500">{explanation}</p>}
  </div>
);

const EmptyState: React.FC<{ title: string; description: string }> = ({ title, description }) => (
  <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-center">
    <HelpCircle className="mx-auto mb-2 h-6 w-6 text-slate-400" />
    <p className="font-medium text-slate-700">{title}</p>
    <p className="mt-1 text-sm text-slate-500">{description}</p>
  </div>
);

export const Dashboard: React.FC<{ onNavigate?: (tab: string) => void }> = ({ onNavigate }) => {
  const [overview, setOverview] = useState<AnyRecord | null>(null);
  const [products, setProducts] = useState<AnyRecord[]>([]);
  const [detail, setDetail] = useState<AnyRecord | null>(null);
  const [search, setSearch] = useState('');
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const workflow = ['Raw Product Data', 'Product Understanding', 'Evidence Discovery', 'Validation', 'Enrichment', 'Human Review', 'Commerce-Ready Output', 'Catalog Scale'];

  const loadOverview = async () => {
    try {
      setLoading(true);
      setError(null);
      const [overviewResponse, productsResponse] = await Promise.all([
        api.getDashboardOverview(),
        api.getDashboardProducts({ page: 1, page_size: 25 }),
      ]);
      const nextOverview = overviewResponse.data;
      const nextProducts = productsResponse.data?.items || [];
      setOverview(nextOverview);
      setProducts(nextProducts);
      const demoId = nextOverview?.demo_product_id || nextProducts[0]?.id;
      if (demoId) await loadProduct(demoId);
    } catch (requestError) {
      setError('The evaluator dashboard could not load persisted intelligence data. Verify that the backend is running.');
    } finally {
      setLoading(false);
    }
  };

  const loadProduct = async (productId: number) => {
    try {
      setDetailLoading(true);
      const response = await api.getDashboardProduct(productId);
      setDetail(response.data);
    } catch (requestError) {
      setError('The selected product detail could not be loaded.');
    } finally {
      setDetailLoading(false);
    }
  };

  useEffect(() => {
    loadOverview();
  }, []);

  useEffect(() => {
    const timer = window.setTimeout(async () => {
      try {
        const response = await api.getDashboardProducts({ page: 1, page_size: 25, search: search || undefined });
        setProducts(response.data?.items || []);
      } catch (requestError) {
        // The primary dashboard remains usable if a search request fails.
      }
    }, 250);
    return () => window.clearTimeout(timer);
  }, [search]);

  const metricCards = useMemo(() => (overview?.metrics || []).map((metric: AnyRecord, index: number) => ({
    ...metric,
    icon: [<Database className="h-5 w-5" />, <CheckCircle2 className="h-5 w-5" />, <BadgeCheck className="h-5 w-5" />, <FileCheck2 className="h-5 w-5" />, <AlertTriangle className="h-5 w-5" />, <Gauge className="h-5 w-5" />, <Download className="h-5 w-5" />, <ShieldCheck className="h-5 w-5" />][index] || <Layers3 className="h-5 w-5" />,
  })), [overview]);

  const selectedProduct = detail?.product || {};
  const rawInput = detail?.raw_input?.input_snapshot || {};
  const afterRecord = detail?.before_after?.after || {};
  const output = detail?.commerce_output || {};
  const outputRecord = output.record || output.record_snapshot?.record || {};
  const outputValidation = output.validation || output.validation_summary || output.record_snapshot?.validation || {};

  if (loading) {
    return <div className="flex min-h-[70vh] items-center justify-center"><div className="flex items-center gap-3 text-sm text-slate-500"><RefreshCw className="h-4 w-4 animate-spin" />Loading evaluator dashboard...</div></div>;
  }

  return (
    <div className="space-y-8 pb-10">
      <section className="overflow-hidden rounded-3xl bg-slate-950 px-6 py-8 text-white shadow-xl sm:px-10">
        <div className="grid gap-8 lg:grid-cols-[1.35fr_0.65fr] lg:items-end">
          <div>
            <div className="mb-4 flex flex-wrap items-center gap-2">
              <span className="rounded-full border border-indigo-400/40 bg-indigo-400/10 px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em] text-indigo-200">Evaluator view</span>
              <span className="rounded-full border border-white/15 px-3 py-1 text-[11px] font-semibold text-slate-300">Phase 1–11 intelligence pipeline</span>
            </div>
            <h1 className="max-w-3xl text-3xl font-semibold tracking-tight sm:text-4xl">AI-Powered Product Intelligence for Commerce</h1>
            <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-300">{overview?.subtitle || 'Turn sparse product data into evidence-backed, reviewable, commerce-ready output without silently inventing values.'}</p>
            <div className="mt-6 flex flex-wrap gap-3 text-xs text-slate-300">
              <span className="inline-flex items-center gap-2"><ShieldCheck className="h-4 w-4 text-emerald-300" />Evidence-first</span>
              <span className="inline-flex items-center gap-2"><Sparkles className="h-4 w-4 text-indigo-300" />Human-review aware</span>
              <span className="inline-flex items-center gap-2"><FileSearch className="h-4 w-4 text-amber-300" />Ground truth honest</span>
              <span className="inline-flex items-center gap-2"><Database className="h-4 w-4 text-emerald-300" />Real supplied data</span>
              <span className="inline-flex items-center gap-2"><AlertTriangle className="h-4 w-4 text-amber-300" />Official data unavailable where not imported</span>
            </div>
            <div className="mt-6 flex flex-wrap gap-3">
              <button type="button" onClick={() => document.getElementById('demo-catalog')?.scrollIntoView({ behavior: 'smooth' })} className="inline-flex items-center gap-2 rounded-lg bg-indigo-500 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400"><Sparkles className="h-4 w-4" />Start Quick Demo</button>
              <button type="button" onClick={() => onNavigate?.('catalog')} className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-4 py-2.5 text-sm font-semibold text-slate-200 hover:bg-white/10"><Layers3 className="h-4 w-4" />Show Catalog Scale</button>
            </div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/[0.06] p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400">Selected catalog batch</p>
            {overview?.latest_batch ? <>
              <p className="mt-2 truncate text-lg font-semibold">{overview.latest_batch.dataset_name || overview.latest_batch.filename}</p>
              <div className="mt-4 grid grid-cols-2 gap-4 text-sm"><div><p className="text-slate-400">Rows</p><p className="mt-1 font-semibold">{overview.latest_batch.total_items?.toLocaleString?.() || overview.latest_batch.total_items || 0}</p></div><div><p className="text-slate-400">Status</p><p className="mt-1"><StatusPill status={overview.latest_batch.status} /></p></div></div>
            </> : <p className="mt-2 text-sm text-slate-400">No catalog batch has been persisted yet.</p>}
          </div>
        </div>
      </section>

      {error && <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-sm text-rose-700"><XCircle className="mt-0.5 h-5 w-5 shrink-0" />{error}</div>}

      <section className="rounded-2xl border border-indigo-100 bg-indigo-50/60 p-5 shadow-sm">
        <SectionHeader eyebrow="End-to-end workflow" title="From raw product data to governed commerce delivery" description="The same traceable workflow powers both the single-product demo and the large-catalog path." icon={<ArrowRight className="h-4 w-4" />} />
        <div className="grid gap-2 sm:grid-cols-2 md:grid-cols-4 xl:grid-cols-8">{workflow.map((stage, index) => <div key={stage} className="relative rounded-xl border border-indigo-100 bg-white p-3"><span className="text-[10px] font-bold uppercase tracking-wide text-indigo-500">0{index + 1}</span><p className="mt-2 text-xs font-semibold leading-5 text-slate-800">{stage}</p>{index < workflow.length - 1 && <ChevronRight className="absolute -right-3 top-1/2 hidden h-4 w-4 -translate-y-1/2 text-indigo-300 xl:block" />}</div>)}</div>
      </section>

      <section>
        <SectionHeader eyebrow="System snapshot" title="What the engine processed" description="These cards are computed from persisted catalog, enrichment, conflict, evidence, and Commerce Output records. They are not fabricated evaluation results." icon={<Gauge className="h-4 w-4" />} />
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">{metricCards.map((metric: AnyRecord) => <MetricCard key={metric.key} {...metric} />)}</div>
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <SectionHeader eyebrow="Pipeline trace" title="From raw catalog to governed delivery" description="Each stage reflects a persisted handoff. Review is a deliberate outcome, not a hidden failure." icon={<ArrowRight className="h-4 w-4" />} />
        <div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6">{(overview?.pipeline || []).map((stage: AnyRecord, index: number) => <div key={stage.key} className="relative rounded-xl border border-slate-200 bg-slate-50 p-4"><div className="flex items-center justify-between"><span className="text-xs font-bold text-indigo-600">0{index + 1}</span><ChevronRight className="h-4 w-4 text-slate-300" /></div><p className="mt-4 text-sm font-semibold text-slate-800">{stage.label}</p><p className="mt-2 text-2xl font-semibold text-slate-950">{formatMetric(stage.count)}</p><p className="mt-2 text-xs leading-5 text-slate-500">{stage.explanation}</p></div>)}</div>
      </section>

      <section id="demo-catalog" className="scroll-mt-6 grid gap-6 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <SectionHeader eyebrow="Demo catalog" title="Select a persisted product" description="Use a real source-backed product to demonstrate explainability end to end." icon={<Search className="h-4 w-4" />} />
          <div className="relative"><Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search SKU, name, manufacturer" className="w-full rounded-xl border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm outline-none transition focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100" /></div>
          <div className="mt-4 max-h-[420px] space-y-2 overflow-y-auto pr-1">{products.length ? products.map((product: AnyRecord) => <button key={product.id} onClick={() => loadProduct(product.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedProduct.id === product.id ? 'border-indigo-400 bg-indigo-50' : 'border-slate-200 bg-white hover:border-indigo-200 hover:bg-slate-50'}`}><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="truncate text-sm font-semibold text-slate-900">{product.name || 'Unnamed product'}</p><p className="mt-1 truncate text-xs text-slate-500">{product.sku || 'Product ID not found'}{product.manufacturer ? ` · ${product.manufacturer}` : ''}</p></div><StatusPill status={product.enrichment_status || product.status || 'UNAVAILABLE'} label={product.enrichment_status || product.status || 'NO RUN'} /></div><div className="mt-3 flex flex-wrap gap-2 text-[11px] text-slate-500"><span>{product.evidence_count || 0} evidence</span><span>·</span><span>{product.conflict_count || 0} conflicts</span><span>·</span><span>{product.source_types?.join(', ') || 'No source type'}</span></div></button>) : <EmptyState title="No persisted products" description="Upload and process a catalog or ingest a source before selecting a demo product." />}</div>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
          <SectionHeader eyebrow="Product showcase" title={selectedProduct.name || 'Source-backed product detail'} description="Raw input, normalized intelligence, evidence, conflicts, review, and final delivery remain connected." icon={<Sparkles className="h-4 w-4" />} />
          {detailLoading ? <div className="flex min-h-[300px] items-center justify-center text-sm text-slate-500"><RefreshCw className="mr-2 h-4 w-4 animate-spin" />Loading product intelligence...</div> : detail ? <div className="space-y-5">
            <div className="flex flex-wrap items-start justify-between gap-4 rounded-xl bg-slate-950 p-5 text-white"><div><p className="text-xs uppercase tracking-wide text-slate-400">{selectedProduct.sku || 'SKU / Product ID not found'}</p><h3 className="mt-2 text-2xl font-semibold">{selectedProduct.name || 'Unnamed product'}</h3><p className="mt-2 text-sm text-slate-300">{selectedProduct.manufacturer || 'Manufacturer not found'}{selectedProduct.category ? ` · ${selectedProduct.category}` : ''}</p></div><div className="text-right"><StatusPill status={detail.enrichment?.product_status || selectedProduct.status || 'UNAVAILABLE'} /><p className="mt-2 text-xs text-slate-400">Confidence {detail.enrichment?.overall_confidence ?? '—'}</p></div></div>
                        <div className="mb-4 flex flex-wrap gap-2"><button type="button" onClick={() => onNavigate?.('product-analyzer')} className="inline-flex items-center gap-2 rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white transition hover:bg-indigo-700"><Sparkles className="h-4 w-4" />Understand in Product Analyzer</button><button type="button" onClick={() => onNavigate?.('export')} className="inline-flex items-center gap-2 rounded-lg border border-indigo-200 bg-white px-3 py-2 text-xs font-semibold text-indigo-700 transition hover:bg-indigo-50"><Download className="h-4 w-4" />Open Commerce Output</button></div><div className="grid gap-4 md:grid-cols-2"><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Before → after</p>
<div className="mt-3 space-y-2 text-sm"><div><span className="font-medium text-slate-500">Raw row:</span> <span className="text-slate-800">{Object.entries(rawInput).slice(0, 3).map(([key, value]) => `${key}: ${displayValue(value)}`).join(' · ') || 'Not available'}</span></div><div><span className="font-medium text-slate-500">Canonical:</span> <span className="text-slate-800">{Object.entries(afterRecord).slice(0, 3).map(([key, value]) => `${key}: ${displayValue(value)}`).join(' · ') || 'Not available'}</span></div></div></div><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Governance state</p><div className="mt-3 flex flex-wrap gap-2"><StatusPill status={detail.availability?.evidence === 'AVAILABLE' ? 'AVAILABLE' : 'UNAVAILABLE'} label={`${detail.evidence?.length || 0} evidence`} /><StatusPill status={detail.conflicts?.length ? 'REVIEW_REQUIRED' : 'AVAILABLE'} label={`${detail.conflicts?.length || 0} conflicts`} /><StatusPill status={detail.reviews?.length ? 'REVIEW_REQUIRED' : 'AVAILABLE'} label={`${detail.reviews?.length || 0} reviews`} /></div><p className="mt-3 text-xs text-slate-500">Ground-truth accuracy: unavailable unless an official expected-output dataset has been supplied.</p></div></div>

            <div><p className="mb-2 text-xs font-bold uppercase tracking-wide text-slate-500">Extracted attributes and provenance</p>{detail.attributes?.length ? <div className="overflow-x-auto rounded-xl border border-slate-200"><table className="min-w-full text-left text-xs"><thead className="bg-slate-50 text-[10px] uppercase tracking-wide text-slate-500"><tr><th className="px-3 py-3">Field</th><th className="px-3 py-3">Raw</th><th className="px-3 py-3">Normalized</th><th className="px-3 py-3">Confidence</th><th className="px-3 py-3">Provenance</th></tr></thead><tbody className="divide-y divide-slate-100">{detail.attributes.slice(0, 12).map((attribute: AnyRecord) => <tr key={attribute.id}><td className="px-3 py-3 font-semibold text-slate-800">{attribute.attribute_name}</td><td className="max-w-[150px] px-3 py-3 text-slate-600">{displayValue(attribute.raw_value)}</td><td className="max-w-[150px] px-3 py-3 text-slate-800">{displayValue(attribute.normalized_value)}{attribute.unit ? ` ${attribute.unit}` : ''}</td><td className="px-3 py-3 text-slate-600">{attribute.confidence ?? '—'}</td><td className="px-3 py-3 text-slate-500">{[attribute.source_type, attribute.page_number ? `p.${attribute.page_number}` : '', attribute.row_number ? `row ${attribute.row_number}` : '', attribute.source_url || attribute.source_identifier].filter(Boolean).join(' · ') || 'Unavailable'}</td></tr>)}</tbody></table></div> : <EmptyState title="No extracted attributes" description="This product has no persisted attribute records yet." />}</div>

            <div className="grid gap-4 md:grid-cols-2"><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Evidence chain</p>{detail.evidence?.length ? <div className="mt-3 space-y-3">{detail.evidence.slice(0, 4).map((evidence: AnyRecord) => <div key={evidence.id} className="border-l-2 border-indigo-300 pl-3"><p className="text-xs font-medium text-slate-700">{evidence.attribute_name || 'Source evidence'}</p><p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-500">{evidence.snippet_text}</p><p className="mt-1 text-[10px] uppercase tracking-wide text-indigo-600">{[evidence.source_type, evidence.page_number ? `page ${evidence.page_number}` : '', evidence.row_number ? `row ${evidence.row_number}` : '', evidence.source_url || evidence.source_identifier].filter(Boolean).join(' · ')}</p></div>)}</div> : <p className="mt-3 text-sm text-slate-500">Evidence is unavailable for this product.</p>}</div><div className="rounded-xl border border-slate-200 p-4"><p className="text-xs font-bold uppercase tracking-wide text-slate-500">Conflicts & review</p>{detail.conflicts?.length ? <div className="mt-3 space-y-2">{detail.conflicts.slice(0, 4).map((conflict: AnyRecord) => <div key={conflict.id} className="rounded-lg bg-amber-50 p-3"><div className="flex items-center justify-between gap-2"><span className="text-xs font-semibold text-amber-900">{conflict.attribute_name}</span><StatusPill status="REVIEW_REQUIRED" label={conflict.severity || 'CONFLICT'} /></div><p className="mt-1 text-xs text-amber-800">{conflict.source_a_name}: {conflict.source_a_value} vs {conflict.source_b_name}: {conflict.source_b_value}</p></div>)}</div> : <p className="mt-3 text-sm text-emerald-700">No persisted conflicts for this product.</p>}{detail.reviews?.length ? <p className="mt-3 text-xs text-slate-500">{detail.reviews.length} non-destructive review decision(s) recorded.</p> : null}</div></div>

            <div className="rounded-xl border border-indigo-200 bg-indigo-50/50 p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-indigo-700">Commerce Output</p><p className="mt-1 text-sm text-slate-700">Stable delivery record with field-level validation and auditability.</p></div><StatusPill status={outputValidation.product_status || (output.record ? 'AVAILABLE' : 'UNAVAILABLE')} label={outputValidation.product_status || (output.record ? 'AVAILABLE' : 'NOT GENERATED')} /></div>{output.record || outputRecord ? <div className="mt-4 grid gap-3 sm:grid-cols-2">{Object.entries(output.record || outputRecord).slice(0, 8).map(([key, value]) => <div key={key} className="rounded-lg border border-indigo-100 bg-white p-3"><p className="text-[10px] font-bold uppercase tracking-wide text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-1 truncate text-sm text-slate-800">{displayValue(value)}</p></div>)}</div> : <p className="mt-4 text-sm text-slate-600">Commerce Output has not been generated for this product yet.</p>}</div>
          </div> : <EmptyState title="Choose a product" description="Select a persisted product from the catalog list to open the evaluator demo." />}
        </div>
      </section>

      <section className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><SectionHeader eyebrow="How decisions are made" title="AI contribution and governance" description="AI helps interpret sparse product information; deterministic rules and people govern what can ship." icon={<Sparkles className="h-4 w-4" />} /><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-indigo-50 p-4"><p className="text-sm font-semibold text-indigo-900">AI / evidence-backed</p><p className="mt-2 text-xs leading-5 text-indigo-800">Product understanding, structured extraction, and controlled discovery evidence are shown with their source chain.</p></div><div className="rounded-xl bg-slate-50 p-4"><p className="text-sm font-semibold text-slate-900">Rules / human review</p><p className="mt-2 text-xs leading-5 text-slate-600">Normalization, reference checks, conflict detection, and review decisions remain explainable and non-destructive.</p></div></div></div>
        <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm"><SectionHeader eyebrow="Architecture & trust" title="Every important field stays traceable" description="Input → source → evidence → extracted value → validation → review → final output." icon={<ShieldCheck className="h-4 w-4" />} /><div className="grid gap-2 sm:grid-cols-2">{['Input catalog', 'Ingestion & validation', 'Product understanding', 'Evidence / discovery', 'Reference data', 'Enrichment', 'Conflict & review', 'Commerce output / export'].map((stage, index) => <div key={stage} className="flex items-center gap-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2"><span className="text-xs font-bold text-indigo-600">{index + 1}</span><span className="text-xs font-medium text-slate-700">{stage}</span></div>)}</div><p className="mt-4 text-xs leading-5 text-slate-500">Principles: source isolation, evidence provenance, human-in-the-loop, no fabricated values, and explainable decisions.</p></div>
      </section>

      <section className="grid gap-6 md:grid-cols-3">
        {Object.entries(overview?.availability || {}).filter(([key]) => key !== 'batch_summary').map(([key, availability]: [string, any]) => <div key={key} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm"><div className="flex items-start justify-between gap-3"><div><p className="text-xs font-bold uppercase tracking-wide text-slate-500">{key.replaceAll('_', ' ')}</p><p className="mt-2 text-sm font-semibold text-slate-900">{availability?.message || availability?.explanation || 'Status available'}</p></div><StatusPill status={availability?.status || 'UNAVAILABLE'} /></div></div>)}
      </section>
      <p className="text-center text-xs text-slate-500">REAL DATA: persisted source-backed products and the supplied 1,000-row catalog. UNAVAILABLE OFFICIAL DATA: expected-output ground truth and any reference masters not imported.</p>
    </div>
  );
};
