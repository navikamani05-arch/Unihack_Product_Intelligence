import React, { useEffect, useState } from 'react';
import { CheckCircle2, Database, FileUp, Search, ShieldAlert, XCircle } from 'lucide-react';
import { api } from '../services/api';

type Dataset = {
  id?: number;
  dataset_type: string;
  name: string;
  file_name?: string;
  version?: string;
  row_count?: number | null;
  status: string;
  is_active: boolean;
  imported_at?: string | null;
  import_statistics?: { duplicates?: number; empty_rows_removed?: number } | null;
};

type Result = {
  status: string;
  match_type?: string;
  input?: string | null;
  original_value?: string | null;
  canonical_name?: string | null;
  canonical_value?: string | null;
  normalized_value?: string | null;
  confidence?: number | null;
  reference_dataset?: string | null;
  explanation: string;
  candidates?: Array<{ display_value: string; code?: string; score?: number }>;
  allowed?: boolean;
  uom?: string | null;
};

const STATUS_STYLE: Record<string, string> = {
  APPROVED: 'bg-emerald-100 text-emerald-800',
  AVAILABLE: 'bg-emerald-100 text-emerald-800',
  CANDIDATE: 'bg-amber-100 text-amber-800',
  AMBIGUOUS: 'bg-amber-100 text-amber-800',
  BRAND_MANUFACTURER_MISMATCH: 'bg-red-100 text-red-800',
  NOT_IN_APPROVED_LOV: 'bg-red-100 text-red-800',
  NOT_FOUND: 'bg-slate-100 text-slate-700',
  REFERENCE_DATA_UNAVAILABLE: 'bg-slate-100 text-slate-700',
};

const labelFor = (value?: string | null) => (value || 'Not available').replaceAll('_', ' ');

export const ReferenceDataView: React.FC = () => {
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [datasetType, setDatasetType] = useState('');
  const [version, setVersion] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [mode, setMode] = useState<'manufacturer' | 'brand' | 'lov' | 'uom' | 'fraction'>('manufacturer');
  const [value, setValue] = useState('');
  const [manufacturer, setManufacturer] = useState('');
  const [classpath, setClasspath] = useState('');
  const [attribute, setAttribute] = useState('');
  const [result, setResult] = useState<Result | null>(null);

  const load = async () => {
    try {
      const response = await api.getReferenceDatasets();
      setDatasets(response.data.datasets || []);
    } catch {
      setMessage('Unable to load the Reference Data Registry. Ensure the backend is running.');
    }
  };

  useEffect(() => { void load(); }, []);

  const upload = async () => {
    if (!file) { setMessage('Choose an official CSV/XLSX reference dataset before importing.'); return; }
    setBusy(true); setMessage('');
    try {
      const response = await api.importReferenceData(file, datasetType || undefined, version || undefined);
      setMessage(`${response.data.name} imported: ${response.data.row_count ?? 0} official rows. Display values were preserved.`);
      setFile(null); setDatasetType(''); setVersion('');
      await load();
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'Reference-data import failed. No dataset was activated.');
    } finally { setBusy(false); }
  };

  const resolve = async () => {
    setBusy(true); setMessage(''); setResult(null);
    try {
      let response;
      if (mode === 'manufacturer') response = await api.resolveManufacturer(value);
      else if (mode === 'brand') response = await api.resolveBrand(value, manufacturer || undefined);
      else if (mode === 'lov') response = await api.resolveAttribute({ classpath: classpath || undefined, attribute, candidate_value: value });
      else if (mode === 'uom') response = await api.normalizeUom(value);
      else response = await api.normalizeFraction(value);
      setResult(response.data);
    } catch (error: any) {
      setMessage(error?.response?.data?.detail || 'The resolution request failed.');
    } finally { setBusy(false); }
  };

  const unavailable = datasets.filter((dataset) => dataset.status === 'not_available').length;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <div className="flex items-center gap-2 text-slate-900"><Database className="h-6 w-6 text-primary-600" /><h1 className="text-2xl font-bold">Reference Data</h1></div>
            <p className="mt-2 max-w-3xl text-sm text-slate-600">Official Unilog master data is the approval layer for manufacturer, brand, controlled vocabulary, UOM, and fraction normalization. An LLM-proposed value remains unapproved until it matches an active imported official dataset.</p>
          </div>
          <div className="rounded-lg bg-slate-50 px-4 py-3 text-sm text-slate-700"><strong>{datasets.filter((item) => item.status === 'available').length}</strong> active dataset(s)<br /><span className="text-xs">{unavailable} expected dataset type(s) unavailable</span></div>
        </div>
      </section>

      {message && <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">{message}</div>}

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2"><FileUp className="h-5 w-5 text-primary-600" /><h2 className="font-semibold text-slate-900">Import Official Reference Data</h2></div>
        <div className="grid gap-3 md:grid-cols-4">
          <input aria-label="Reference dataset file" type="file" accept=".csv,.xlsx,.xls" onChange={(event) => setFile(event.target.files?.[0] || null)} className="rounded-lg border border-slate-300 p-2 text-sm" />
          <select aria-label="Reference dataset type" value={datasetType} onChange={(event) => setDatasetType(event.target.value)} className="rounded-lg border border-slate-300 p-2 text-sm"><option value="">Infer from filename</option><option value="manufacturer_brand">Manufacturer/Brand Master</option><option value="lov">Unilog LOV</option><option value="faucets_lov">Faucets LOV</option><option value="fittings_lov">Fittings LOV</option><option value="uom">UOM Master</option><option value="fraction">Decimal/Fraction Master</option></select>
          <input aria-label="Dataset version" value={version} onChange={(event) => setVersion(event.target.value)} placeholder="Version (optional)" className="rounded-lg border border-slate-300 p-2 text-sm" />
          <button disabled={busy} onClick={() => void upload()} className="rounded-lg bg-primary-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">{busy ? 'Processing…' : 'Import official data'}</button>
        </div>
        <p className="mt-3 text-xs text-slate-500">Imports inspect workbook sheets and headers, trim comparison values, preserve official display values, remove empty rows, and record import statistics. No unofficial data is synthesized.</p>
      </section>

      <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-6 py-4"><h2 className="font-semibold text-slate-900">Reference Data Registry</h2></div>
        <div className="overflow-x-auto"><table className="min-w-full text-left text-sm"><thead className="bg-slate-50 text-xs uppercase text-slate-500"><tr><th className="px-5 py-3">Dataset</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Version</th><th className="px-5 py-3">Rows</th><th className="px-5 py-3">Last updated</th></tr></thead><tbody>{datasets.map((dataset, index) => <tr key={`${dataset.dataset_type}-${dataset.id ?? index}`} className="border-t border-slate-100"><td className="px-5 py-3"><div className="font-medium text-slate-800">{dataset.name}</div><div className="text-xs text-slate-500">{dataset.file_name || dataset.dataset_type}</div></td><td className="px-5 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${dataset.status === 'available' ? 'bg-emerald-100 text-emerald-800' : 'bg-slate-100 text-slate-700'}`}>{labelFor(dataset.status)}</span></td><td className="px-5 py-3 text-slate-600">{dataset.version || '—'}</td><td className="px-5 py-3 text-slate-600">{dataset.row_count?.toLocaleString() || '—'}</td><td className="px-5 py-3 text-slate-600">{dataset.imported_at ? new Date(dataset.imported_at).toLocaleString() : '—'}</td></tr>)}</tbody></table></div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="mb-4 flex items-center gap-2"><Search className="h-5 w-5 text-primary-600" /><h2 className="font-semibold text-slate-900">Explainable Resolution</h2></div>
        <div className="mb-4 flex flex-wrap gap-2">{(['manufacturer', 'brand', 'lov', 'uom', 'fraction'] as const).map((item) => <button key={item} onClick={() => { setMode(item); setResult(null); }} className={`rounded-full px-3 py-1.5 text-sm font-medium ${mode === item ? 'bg-primary-600 text-white' : 'bg-slate-100 text-slate-700'}`}>{item === 'lov' ? 'LOV' : item.toUpperCase()}</button>)}</div>
        <div className="grid gap-3 md:grid-cols-3">
          {mode === 'lov' && <><input value={classpath} onChange={(event) => setClasspath(event.target.value)} placeholder="Classpath (required for scoped validation)" className="rounded-lg border border-slate-300 p-2 text-sm" /><input value={attribute} onChange={(event) => setAttribute(event.target.value)} placeholder="Attribute label" className="rounded-lg border border-slate-300 p-2 text-sm" /></>}
          {mode === 'brand' && <input value={manufacturer} onChange={(event) => setManufacturer(event.target.value)} placeholder="Manufacturer evidence (optional)" className="rounded-lg border border-slate-300 p-2 text-sm" />}
          <input value={value} onChange={(event) => setValue(event.target.value)} placeholder={mode === 'lov' ? 'Candidate value' : mode === 'uom' ? 'Example: 24 inches' : mode === 'fraction' ? 'Example: 50.25 in' : 'Source value'} className="rounded-lg border border-slate-300 p-2 text-sm" />
          <button disabled={busy || (mode === 'lov' && !attribute)} onClick={() => void resolve()} className="rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Resolve against official data</button>
        </div>
        {result && <div className="mt-5 rounded-lg border border-slate-200 bg-slate-50 p-4"><div className="mb-3 flex flex-wrap items-center gap-2"><span className={`rounded-full px-2 py-1 text-xs font-bold ${STATUS_STYLE[result.status] || 'bg-slate-100 text-slate-700'}`}>{labelFor(result.status)}</span>{result.match_type && <span className="text-xs text-slate-500">{labelFor(result.match_type)}</span>}</div><div className="grid gap-3 text-sm md:grid-cols-3"><div><p className="text-xs uppercase text-slate-500">Original value</p><p className="font-medium">{result.input || result.original_value || '—'}</p></div><div><p className="text-xs uppercase text-slate-500">Canonical value</p><p className="font-medium">{result.canonical_name || result.canonical_value || result.normalized_value || 'Not approved'}</p></div><div><p className="text-xs uppercase text-slate-500">Reference source</p><p className="font-medium">{result.reference_dataset || 'Unavailable'}</p></div></div><p className="mt-3 text-sm text-slate-700">{result.explanation}</p>{typeof result.confidence === 'number' && <p className="mt-2 text-xs text-slate-500">Confidence: {(result.confidence * 100).toFixed(0)}%</p>}{result.candidates && result.candidates.length > 0 && <div className="mt-3 border-t border-slate-200 pt-3 text-sm"><p className="font-medium text-slate-700">Candidates requiring review</p>{result.candidates.map((candidate, index) => <p key={`${candidate.display_value}-${index}`} className="mt-1 text-slate-600">{candidate.display_value}{candidate.code ? ` (${candidate.code})` : ''}{typeof candidate.score === 'number' ? ` — ${(candidate.score * 100).toFixed(0)}% similarity` : ''}</p>)}</div>}</div>}
      </section>

      <section className="rounded-xl border border-slate-200 bg-white p-5 text-sm text-slate-600 shadow-sm"><div className="flex gap-3"><ShieldAlert className="h-5 w-5 shrink-0 text-amber-600" /><p><strong className="text-slate-800">Approval safety:</strong> missing datasets return <code>REFERENCE_DATA_UNAVAILABLE</code>; ambiguous candidates are not silently selected; brand/manufacturer mismatches are flagged; and original source evidence remains unchanged alongside each decision.</p></div></section>
    </div>
  );
};
