import React, { useEffect, useMemo, useState } from 'react';
import { AlertTriangle, CheckCircle2, Download, FileSpreadsheet, Pause, Play, RefreshCw, Search, Upload, XCircle } from 'lucide-react';
import { api } from '../services/api';

interface CatalogStatus {
  batch_id: number;
  dataset_name: string;
  filename: string;
  source_type: string;
  status: string;
  total_items: number;
  queued_items: number;
  processed_items: number;
  successful_items: number;
  review_items: number;
  failed_items: number;
  invalid_items: number;
  progress_percentage: number;
  error_summary: Record<string, unknown>;
}

interface CatalogItem {
  id: number;
  row_number: number;
  identifier?: string;
  input_snapshot: Record<string, unknown>;
  validation_status: string;
  validation_errors: string[];
  validation_warnings: string[];
  processing_status: string;
  error_message?: string;
  product_id?: number;
  result_status?: string;
  confidence?: number;
  evidence_available: boolean;
  conflict_count: number;
  review_required: boolean;
  commerce_output_id?: number;
  product_name?: string;
  manufacturer?: string;
}

interface CatalogSummary {
  metrics: Record<string, number | string | null>;
  ground_truth_message: string;
  [key: string]: unknown;
}

const formatMetric = (value: number | string | null | undefined) => typeof value === 'number' ? `${value.toFixed(1)}%` : value || 'Unavailable';

const downloadBlob = (blob: Blob, filename: string) => {
  const url = window.URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.URL.revokeObjectURL(url);
};

export const CatalogProcessingView: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [batchId, setBatchId] = useState<number | null>(null);
  const [status, setStatus] = useState<CatalogStatus | null>(null);
  const [summary, setSummary] = useState<CatalogSummary | null>(null);
  const [items, setItems] = useState<CatalogItem[]>([]);
  const [totalResults, setTotalResults] = useState(0);
  const [reviewQueue, setReviewQueue] = useState<{ total: number; items: Array<Record<string, unknown>> } | null>(null);
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState('all');
  const [page, setPage] = useState(1);
  const [uploadSummary, setUploadSummary] = useState<Record<string, unknown> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  const loadBatch = async (id: number) => {
    const [statusResponse, summaryResponse, resultsResponse, reviewResponse] = await Promise.all([
      api.getCatalogStatus(id),
      api.getCatalogSummary(id),
      api.getCatalogResults(id, { page, page_size: 25, status: filter, search: search || undefined }),
      api.getCatalogReviewQueue(id),
    ]);
    setStatus(statusResponse.data);
    setSummary(summaryResponse.data);
    setItems(resultsResponse.data.items || []);
    setTotalResults(resultsResponse.data.total || 0);
    setReviewQueue(reviewResponse.data);
  };

  useEffect(() => {
    if (!batchId) return;
    loadBatch(batchId).catch((reason) => setError(reason?.response?.data?.detail || 'Unable to load catalog batch state.'));
  }, [batchId, page, filter, search]);

  useEffect(() => {
    if (!batchId || !status || !['QUEUED', 'PROCESSING', 'PAUSED'].includes(status.status)) return;
    const timer = window.setInterval(() => loadBatch(batchId).catch(() => undefined), 2500);
    return () => window.clearInterval(timer);
  }, [batchId, status?.status, page, filter, search]);

  const handleUpload = async () => {
    if (!file) return;
    setBusy(true); setError(''); setUploadSummary(null); setSummary(null); setItems([]);
    try {
      const response = await api.uploadCatalog(file);
      setUploadSummary(response.data);
      setBatchId(response.data.batch_id);
      setPage(1); setFilter('all'); setSearch('');
    } catch (reason: any) {
      setError(reason?.response?.data?.detail || 'Catalog upload failed.');
    } finally { setBusy(false); }
  };

  const startBatch = async () => {
    if (!batchId) return;
    setBusy(true); setError('');
    try { await api.startCatalogBatch(batchId); await loadBatch(batchId); }
    catch (reason: any) { setError(reason?.response?.data?.detail || 'Unable to start catalog processing.'); }
    finally { setBusy(false); }
  };

  const cancelBatch = async () => {
    if (!batchId) return;
    try { await api.cancelCatalogBatch(batchId); await loadBatch(batchId); }
    catch (reason: any) { setError(reason?.response?.data?.detail || 'Unable to cancel catalog processing.'); }
  };

  const retryFailed = async () => {
    if (!batchId) return;
    try { await api.retryCatalogBatch(batchId); await loadBatch(batchId); }
    catch (reason: any) { setError(reason?.response?.data?.detail || 'Unable to retry failed catalog rows.'); }
  };

  const download = async (format: 'csv' | 'xlsx' | 'json') => {
    if (!batchId) return;
    try {
      const response = await api.exportCatalog(batchId, format, filter as 'all' | 'ready' | 'review_required' | 'failed');
      downloadBlob(response.data, `catalog-batch-${batchId}-${filter}.${format}`);
    } catch (reason: any) { setError(reason?.response?.data?.detail || 'Catalog export failed.'); }
  };

  const metricCards = useMemo(() => {
    const metrics = summary?.metrics || {};
    return [
      ['Processing success', metrics.processing_success_rate],
      ['Completeness', metrics.completeness],
      ['Evidence coverage', metrics.evidence_coverage],
      ['Reference compliance', metrics.reference_data_compliance],
      ['Conflict rate', metrics.conflict_rate],
      ['Human review rate', metrics.human_review_rate],
    ];
  }, [summary]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">Catalog Processing</h1>
          <p className="text-gray-600 mt-1">Validate and process large source-backed product catalogs without fabricating values or evidence.</p>
        </div>
        {batchId && <div className="text-sm text-gray-500">Batch #{batchId} · {status?.filename || uploadSummary?.filename}</div>}
      </div>

      <section className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
        <div className="flex items-center gap-2 mb-4"><FileSpreadsheet className="w-5 h-5 text-primary-600" /><h2 className="font-semibold text-gray-900">Upload catalog</h2></div>
        <div className="flex flex-col md:flex-row gap-3 items-start md:items-center">
          <input type="file" accept=".csv,.xlsx" onChange={(event) => setFile(event.target.files?.[0] || null)} className="block w-full text-sm text-gray-600" />
          <button onClick={handleUpload} disabled={!file || busy} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary-600 text-white disabled:opacity-50"><Upload className="w-4 h-4" />Validate catalog</button>
        </div>
        <p className="text-xs text-gray-500 mt-3">The uploaded file is preserved row-for-row. Required input checks use detected columns; unsupported official Unilog fields are not assumed.</p>
        {uploadSummary && <div className="mt-4 grid grid-cols-2 md:grid-cols-5 gap-3 text-sm">
          <div><span className="text-gray-500">Rows</span><p className="font-semibold">{String(uploadSummary.total_rows)}</p></div>
          <div><span className="text-gray-500">Valid</span><p className="font-semibold text-green-700">{String(uploadSummary.valid_rows)}</p></div>
          <div><span className="text-gray-500">Invalid</span><p className="font-semibold text-red-700">{String(uploadSummary.invalid_rows)}</p></div>
          <div><span className="text-gray-500">Duplicates</span><p className="font-semibold">{Array.isArray(uploadSummary.duplicate_identifiers) ? uploadSummary.duplicate_identifiers.length : 0}</p></div>
          <div><span className="text-gray-500">Columns</span><p className="font-semibold">{Array.isArray(uploadSummary.detected_columns) ? uploadSummary.detected_columns.length : 0}</p></div>
        </div>}
      </section>

      {error && <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700 flex items-center gap-2"><XCircle className="w-5 h-5" />{error}</div>}

      {status && <>
        <section className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div><div className="flex items-center gap-2"><span className="font-semibold text-gray-900">{status.status}</span>{status.status === 'COMPLETED' ? <CheckCircle2 className="w-5 h-5 text-green-600" /> : status.status === 'FAILED' ? <XCircle className="w-5 h-5 text-red-600" /> : <RefreshCw className="w-5 h-5 text-primary-600 animate-spin" />}</div><p className="text-sm text-gray-500 mt-1">{status.processed_items} of {status.total_items} rows processed · {status.successful_items} successful · {status.review_items} review · {status.failed_items} failed · {status.invalid_items} invalid</p></div>
            <div className="flex gap-2">
              {['QUEUED', 'PAUSED'].includes(status.status) && <button onClick={startBatch} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg bg-primary-600 text-white"><Play className="w-4 h-4" />Start</button>}
              {status.status === 'PROCESSING' && <button onClick={cancelBatch} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-gray-300 text-gray-700"><Pause className="w-4 h-4" />Cancel</button>}
              {status.failed_items > 0 && <button onClick={retryFailed} className="inline-flex items-center gap-2 px-3 py-2 rounded-lg border border-amber-300 text-amber-700"><RefreshCw className="w-4 h-4" />Retry failed</button>}
            </div>
          </div>
          <div className="mt-4 h-3 bg-gray-100 rounded-full overflow-hidden"><div className="h-full bg-primary-600 transition-all" style={{ width: `${status.progress_percentage}%` }} /></div>
          <div className="text-right text-xs text-gray-500 mt-1">{status.progress_percentage.toFixed(1)}%</div>
        </section>

        <section className="grid grid-cols-2 lg:grid-cols-6 gap-3">
          {metricCards.map(([label, value]) => <div key={label} className="bg-white border border-gray-200 rounded-xl p-4"><p className="text-xs text-gray-500">{label}</p><p className="text-lg font-semibold text-gray-900 mt-1">{formatMetric(value as number | string | null)}</p></div>)}
        </section>

        <section className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="flex flex-col lg:flex-row gap-3 lg:items-center lg:justify-between mb-4"><div><h2 className="font-semibold text-gray-900">Product results</h2><p className="text-sm text-gray-500">{totalResults} rows · source-backed results preserve the original input and provenance.</p></div><div className="flex flex-wrap gap-2"><div className="relative"><Search className="w-4 h-4 absolute left-3 top-2.5 text-gray-400" /><input value={search} onChange={(event) => { setSearch(event.target.value); setPage(1); }} placeholder="Search catalog" className="pl-9 pr-3 py-2 border border-gray-300 rounded-lg text-sm" /></div><select value={filter} onChange={(event) => { setFilter(event.target.value); setPage(1); }} className="border border-gray-300 rounded-lg px-3 py-2 text-sm"><option value="all">All</option><option value="ready">Ready</option><option value="review_required">Review required</option><option value="failed">Failed</option></select></div></div>
          <div className="overflow-x-auto"><table className="min-w-full text-sm"><thead><tr className="border-b text-left text-gray-500"><th className="py-3 pr-4">Row</th><th className="py-3 pr-4">Part number</th><th className="py-3 pr-4">Product</th><th className="py-3 pr-4">Manufacturer</th><th className="py-3 pr-4">Status</th><th className="py-3 pr-4">Confidence</th><th className="py-3 pr-4">Evidence</th><th className="py-3">Conflicts</th></tr></thead><tbody>{items.map((item) => <tr key={item.id} className="border-b last:border-0"><td className="py-3 pr-4 text-gray-500">{item.row_number}</td><td className="py-3 pr-4 font-medium">{item.identifier || 'Not found'}</td><td className="py-3 pr-4 max-w-xs truncate">{item.product_name || '—'}</td><td className="py-3 pr-4">{item.manufacturer || '—'}</td><td className="py-3 pr-4"><span className={`px-2 py-1 rounded-full text-xs ${item.processing_status === 'FAILED' ? 'bg-red-100 text-red-700' : item.result_status === 'READY' ? 'bg-green-100 text-green-700' : 'bg-amber-100 text-amber-700'}`}>{item.result_status || item.processing_status}</span></td><td className="py-3 pr-4">{item.confidence == null ? '—' : `${(item.confidence * 100).toFixed(0)}%`}</td><td className="py-3 pr-4">{item.evidence_available ? <CheckCircle2 className="w-4 h-4 text-green-600" /> : <AlertTriangle className="w-4 h-4 text-amber-600" />}</td><td className="py-3">{item.conflict_count || '—'}</td></tr>)}</tbody></table></div>
          <div className="flex items-center justify-between mt-4 text-sm text-gray-500"><span>Page {page}</span><div className="flex gap-2"><button disabled={page <= 1} onClick={() => setPage((value) => value - 1)} className="px-3 py-1 border rounded disabled:opacity-40">Previous</button><button disabled={page * 25 >= totalResults} onClick={() => setPage((value) => value + 1)} className="px-3 py-1 border rounded disabled:opacity-40">Next</button></div></div>
        </section>

        <section className="grid lg:grid-cols-2 gap-5">
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm"><h2 className="font-semibold text-gray-900 mb-3">Human review queue</h2><p className="text-sm text-gray-500 mb-3">{reviewQueue?.total || 0} products require review. Open the existing Product Analyzer or Commerce Output workflow using the product ID shown in each row.</p><div className="space-y-2 max-h-72 overflow-auto">{(reviewQueue?.items || []).slice(0, 12).map((item) => <div key={String(item.item_id)} className="border rounded-lg p-3 text-sm"><div className="flex justify-between"><span className="font-medium">{String(item.identifier || item.product_name || `Row ${item.row_number}`)}</span><span className="text-xs text-amber-700">{String(item.severity)}</span></div><p className="text-gray-600 mt-1">{String(item.reason)}</p></div>)}{!reviewQueue?.total && <p className="text-sm text-gray-500">No review items yet.</p>}</div></div>
          <div className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm"><h2 className="font-semibold text-gray-900 mb-3">Catalog exports</h2><p className="text-sm text-gray-500 mb-4">Exports include product status, validation context, commerce output availability, raw input snapshot, and canonical output snapshot where available.</p><div className="grid grid-cols-3 gap-2">{(['csv', 'xlsx', 'json'] as const).map((format) => <button key={format} onClick={() => download(format)} className="inline-flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-gray-300 hover:bg-gray-50"><Download className="w-4 h-4" />{format.toUpperCase()}</button>)}</div><div className="mt-5 p-3 bg-gray-50 rounded-lg text-xs text-gray-600">Ground-Truth Accuracy: <strong>UNAVAILABLE</strong>. {summary?.ground_truth_message || 'Official ground truth dataset not available.'}</div></div>
        </section>
      </>}
    </div>
  );
};

export default CatalogProcessingView;
