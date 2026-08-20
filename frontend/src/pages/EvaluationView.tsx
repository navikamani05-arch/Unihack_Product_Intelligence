import { useEffect, useMemo, useState } from 'react';
import {
  AlertTriangle,
  BarChart3,
  CheckCircle2,
  FileSpreadsheet,
  RefreshCw,
  Search,
  ShieldCheck,
  Upload,
  XCircle,
} from 'lucide-react';
import { api } from '../services/api';

type Metric = {
  name: string;
  label: string;
  passed: number;
  evaluated: number;
  compliance_percentage: number | null;
  unavailable_reason?: string | null;
};

type GroundTruthColumn = {
  name: string;
  pandas_dtype: string;
  nonempty_count: number;
  empty_count: number;
  unique_count: number;
  sample_values: string[];
  max_string_length: number;
  role: string;
  comparison_status: 'SUPPORTED' | 'PARTIALLY_SUPPORTED' | 'UNSUPPORTED' | 'UNKNOWN';
  mapped_field?: string | null;
  comparison_mode?: string | null;
  reason: string;
};

type GroundTruthSchema = {
  official_ground_truth_available: boolean;
  message: string;
  file_name?: string | null;
  row_count: number;
  column_count: number;
  identifier_column?: string | null;
  columns: GroundTruthColumn[];
};

type GroundTruthAggregate = {
  total_expected_products: number;
  products_matched: number;
  products_missing_from_output: number;
  unexpected_products: number;
  expected_nonempty_fields: number;
  comparable_fields: number;
  exact_matches: number;
  normalized_matches: number;
  partial_matches: number;
  missing_values: number;
  incorrect_values: number;
  source_data_unavailable: number;
  pipeline_missing: number;
  overall_evaluation_rate?: number | null;
  overall_match_rate?: number | null;
  overall_missing_value_rate?: number | null;
  field_metrics: Array<{ field_name: string; mapped_field?: string | null; expected_nonempty: number; exact_matches: number; normalized_matches: number; partial_matches: number; missing: number; incorrect: number; source_data_unavailable: number; pipeline_missing: number; evaluated: number; exact_match_rate?: number | null; match_rate?: number | null; missing_value_rate?: number | null; comparison_status: string; reason?: string | null }>;
  mismatches: Array<{ product_key?: string | null; expected_row_number?: number | null; field_name: string; mapped_field?: string | null; expected_value?: string | null; generated_value?: string | null; result: string; availability?: string; reason?: string | null }>;
  unsupported_columns: string[];
  unknown_columns: string[];
  lov_comparison_available: boolean;
  uom_comparison_available: boolean;
  character_limits_available: boolean;
};

type Summary = {
  run_id?: number | null;
  status: string;
  message: string;
  official_ground_truth_available: boolean;
  products_processed: number;
  products_with_generated_output: number;
  fields_evaluated: number;
  rule_based_quality_score: number | null;
  ground_truth_accuracy: number | null;
  missing_attribute_rate: number | null;
  invalid_lov_values: number;
  invalid_uom_values: number;
  character_limit_violations: number;
  human_review_candidates: number;
  metrics: Metric[];
  ground_truth?: GroundTruthAggregate | null;
  generated_at?: string | null;
};

type Failure = {
  product_result_id: number;
  input_row_number: number;
  input_product_key?: string | null;
  generated_product_id?: number | null;
  status: string;
  field: {
    field_name: string;
    check_name: string;
    outcome: string;
    generated_value?: string | null;
    details?: string | null;
    severity: string;
  };
};

type ProductDetail = {
  id: number;
  input_row_number: number;
  input_product_key?: string | null;
  source_description?: string | null;
  generated_product_id?: number | null;
  status: string;
  quality_score?: number | null;
  human_review_reason?: string | null;
  input_snapshot: Record<string, string>;
  generated_snapshot: Record<string, unknown>;
  fields: Array<{
    id: number;
    field_name: string;
    check_name: string;
    outcome: string;
    generated_value?: string | null;
    details?: string | null;
    severity: string;
  }>;
};

type Availability = {
  official_ground_truth_available: boolean;
  message: string;
  supported_file_types: string[];
  detected_columns: string[];
  identifier_column?: string | null;
};

const percentage = (value: number | null | undefined) => value === null || value === undefined ? 'Not scored' : `${value.toFixed(1)}%`;
const outcomeStyle = (outcome: string) => outcome === 'PASS' ? 'bg-green-100 text-green-800' : outcome === 'MISSING' ? 'bg-amber-100 text-amber-800' : outcome === 'FAIL' ? 'bg-red-100 text-red-800' : 'bg-gray-100 text-gray-700';

export function EvaluationView() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [groundTruth, setGroundTruth] = useState<Summary | null>(null);
  const [availability, setAvailability] = useState<Availability | null>(null);
  const [groundTruthSchema, setGroundTruthSchema] = useState<GroundTruthSchema | null>(null);
  const [failures, setFailures] = useState<Failure[]>([]);
  const [selected, setSelected] = useState<ProductDetail | null>(null);
  const [running, setRunning] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState('');

  const load = async () => {
    try {
      setError(null);
      const [qualityResponse, groundTruthResponse, availabilityResponse] = await Promise.all([
        api.getEvaluationSummary('rule_quality'),
        api.getEvaluationSummary('ground_truth'),
        api.getGroundTruthAvailability(),
      ]);
      setSummary(qualityResponse.data);
      setGroundTruth(groundTruthResponse.data);
      setAvailability(availabilityResponse.data);
      if (availabilityResponse.data.official_ground_truth_available) {
        try {
          const schemaResponse = await api.getGroundTruthSchema();
          setGroundTruthSchema(schemaResponse.data);
        } catch {
          setGroundTruthSchema(null);
        }
      } else {
        setGroundTruthSchema(null);
      }
      if (qualityResponse.data.run_id) {
        const failureResponse = await api.getEvaluationFailures(qualityResponse.data.run_id);
        setFailures(failureResponse.data.failures || []);
      } else {
        setFailures([]);
      }
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Unable to load evaluation data.');
    }
  };

  useEffect(() => { void load(); }, []);

  const runQuality = async () => {
    setRunning(true);
    try {
      await api.runEvaluation('rule_quality');
      await load();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Rule-based Quality Evaluation could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  const runGroundTruth = async () => {
    setRunning(true);
    try {
      await api.runEvaluation('ground_truth');
      await load();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Ground-Truth Evaluation could not be completed.');
    } finally {
      setRunning(false);
    }
  };

  const uploadExpected = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;
    setUploading(true);
    try {
      await api.uploadGroundTruth(file);
      await load();
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Expected-output file upload failed.');
    } finally {
      setUploading(false);
      event.target.value = '';
    }
  };

  const openDetail = async (resultId: number) => {
    try {
      const response = await api.getEvaluationProduct(resultId);
      setSelected(response.data);
    } catch (requestError: any) {
      setError(requestError?.response?.data?.detail || 'Could not load the product evaluation detail.');
    }
  };

  const filteredFailures = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return failures;
    return failures.filter((failure) => [failure.input_product_key, failure.field.field_name, failure.field.outcome, failure.field.details]
      .filter(Boolean).join(' ').toLowerCase().includes(needle));
  }, [failures, query]);

  const qualityAvailable = summary?.rule_based_quality_score !== null && summary?.rule_based_quality_score !== undefined;

  return (
    <div className="space-y-6">
      <section className="rounded-xl border border-slate-200 bg-gradient-to-r from-slate-900 to-indigo-900 p-6 text-white shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-200"><BarChart3 className="h-5 w-5" /> Phase 4 Evaluation</div>
            <h1 className="text-2xl font-bold">Data Quality & Ground-Truth Evaluation</h1>
            <p className="mt-2 max-w-3xl text-sm text-slate-200">Rule-based Quality Score evaluates generated records using transparent baseline checks. Ground-Truth Accuracy is shown only after an official expected-output dataset is uploaded.</p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button onClick={() => void runQuality()} disabled={running} className="inline-flex items-center gap-2 rounded-lg bg-white px-4 py-2 text-sm font-semibold text-slate-900 transition hover:bg-slate-100 disabled:opacity-60"><RefreshCw className={`h-4 w-4 ${running ? 'animate-spin' : ''}`} /> {running ? 'Evaluating…' : 'Run Rule-based Quality Evaluation'}</button>
            <button onClick={() => void load()} className="inline-flex items-center gap-2 rounded-lg border border-indigo-300 px-4 py-2 text-sm font-semibold text-white hover:bg-indigo-800"><RefreshCw className="h-4 w-4" /> Refresh</button>
          </div>
        </div>
      </section>

      {error && <div className="flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800"><XCircle className="h-5 w-5 shrink-0" /><span>{error}</span></div>}

      <div className="grid gap-4 md:grid-cols-2">
        <section className="rounded-xl border border-indigo-200 bg-indigo-50 p-5">
          <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-indigo-800">Rule-based Quality Score</p><p className="mt-1 text-xs text-indigo-700">Computed from transparent checks; it is not ground-truth accuracy.</p></div><ShieldCheck className="h-6 w-6 text-indigo-700" /></div>
          <p className="mt-4 text-3xl font-bold text-indigo-950">{qualityAvailable ? percentage(summary?.rule_based_quality_score) : 'Not scored'}</p>
          <p className="mt-2 text-sm text-indigo-800">{summary?.products_processed ?? 0} raw products processed · {summary?.products_with_generated_output ?? 0} matched generated records</p>
        </section>
        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <div className="flex items-start justify-between gap-4"><div><p className="text-sm font-semibold text-amber-900">Ground-Truth Accuracy</p><p className="mt-1 text-xs text-amber-800">Requires official expected-output values; none are inferred.</p></div><FileSpreadsheet className="h-6 w-6 text-amber-700" /></div>
          {availability?.official_ground_truth_available ? <><p className="mt-4 text-3xl font-bold text-amber-950">{groundTruth?.ground_truth_accuracy === null || groundTruth?.ground_truth_accuracy === undefined ? 'Ready to run' : percentage(groundTruth.ground_truth_accuracy)}</p><button onClick={() => void runGroundTruth()} disabled={running} className="mt-3 rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:opacity-60">Run Ground-Truth Evaluation</button></> : <><p className="mt-4 text-lg font-bold text-amber-950">Official ground truth dataset not available.</p><label className="mt-3 inline-flex cursor-pointer items-center gap-2 rounded-lg bg-amber-700 px-3 py-2 text-sm font-semibold text-white hover:bg-amber-800"><Upload className="h-4 w-4" /> {uploading ? 'Uploading…' : 'Upload Expected Output (.csv / .xlsx)'}<input className="hidden" type="file" accept=".csv,.xlsx" onChange={(event) => void uploadExpected(event)} disabled={uploading} /></label></>}
        </section>
      </div>

      {groundTruthSchema && <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4"><h2 className="font-semibold text-slate-900">Official expected-output schema</h2><p className="mt-1 text-sm text-slate-500">{groundTruthSchema.file_name} · {groundTruthSchema.row_count} expected products · {groundTruthSchema.column_count} columns · identifier: {groundTruthSchema.identifier_column || 'not established'}</p><p className="mt-1 text-xs text-slate-500">Only fields with a defensible mapping to generated output are included in accuracy denominators. Unknown and unsupported delivery-format columns are shown separately.</p></div>
        <div className="grid gap-3 p-5 sm:grid-cols-3"><div className="rounded-lg bg-green-50 p-3"><p className="text-xs uppercase tracking-wide text-green-700">Supported</p><p className="mt-1 text-2xl font-bold text-green-900">{groundTruthSchema.columns.filter((column) => column.comparison_status === 'SUPPORTED').length}</p></div><div className="rounded-lg bg-indigo-50 p-3"><p className="text-xs uppercase tracking-wide text-indigo-700">Partially supported</p><p className="mt-1 text-2xl font-bold text-indigo-900">{groundTruthSchema.columns.filter((column) => column.comparison_status === 'PARTIALLY_SUPPORTED').length}</p></div><div className="rounded-lg bg-amber-50 p-3"><p className="text-xs uppercase tracking-wide text-amber-700">Unknown / unsupported</p><p className="mt-1 text-2xl font-bold text-amber-900">{groundTruthSchema.columns.filter((column) => ['UNKNOWN', 'UNSUPPORTED'].includes(column.comparison_status)).length}</p></div></div>
        <div className="max-h-80 overflow-auto border-t border-slate-100"><table className="min-w-full divide-y divide-slate-200 text-left text-xs"><thead className="bg-slate-50 uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Official column</th><th className="px-5 py-3">Role</th><th className="px-5 py-3">Status</th><th className="px-5 py-3">Mapped field</th><th className="px-5 py-3">Observed data</th></tr></thead><tbody className="divide-y divide-slate-100">{groundTruthSchema.columns.map((column) => <tr key={column.name}><td className="px-5 py-2 font-medium text-slate-800">{column.name}</td><td className="px-5 py-2 text-slate-600">{column.role}</td><td className="px-5 py-2"><span className={`rounded-full px-2 py-1 font-semibold ${column.comparison_status === 'SUPPORTED' ? 'bg-green-100 text-green-800' : column.comparison_status === 'PARTIALLY_SUPPORTED' ? 'bg-indigo-100 text-indigo-800' : 'bg-amber-100 text-amber-800'}`}>{column.comparison_status}</span></td><td className="px-5 py-2 text-slate-600">{column.mapped_field || '—'}</td><td className="px-5 py-2 text-slate-500">{column.nonempty_count}/{column.nonempty_count + column.empty_count} non-empty</td></tr>)}</tbody></table></div>
      </section>}

      {groundTruth?.ground_truth && <section className="rounded-xl border border-amber-200 bg-amber-50 shadow-sm">
        <div className="border-b border-amber-200 px-5 py-4"><h2 className="font-semibold text-amber-950">Official ground-truth evaluation</h2><p className="mt-1 text-sm text-amber-800">These are comparisons against the uploaded official expected-output file, not confidence, trust, or rule-quality scores.</p></div>
        <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4"><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Expected products</p><p className="mt-1 text-2xl font-bold text-slate-900">{groundTruth.ground_truth.total_expected_products}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Products matched</p><p className="mt-1 text-2xl font-bold text-green-700">{groundTruth.ground_truth.products_matched}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Missing from output</p><p className="mt-1 text-2xl font-bold text-amber-700">{groundTruth.ground_truth.products_missing_from_output}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Unexpected products</p><p className="mt-1 text-2xl font-bold text-red-700">{groundTruth.ground_truth.unexpected_products}</p></div></div>
        <div className="grid gap-3 px-5 pb-5 sm:grid-cols-2 lg:grid-cols-4"><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Exact matches</p><p className="mt-1 text-xl font-bold text-slate-900">{groundTruth.ground_truth.exact_matches}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Normalized matches</p><p className="mt-1 text-xl font-bold text-slate-900">{groundTruth.ground_truth.normalized_matches}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Missing values</p><p className="mt-1 text-xl font-bold text-amber-700">{groundTruth.ground_truth.missing_values}</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Field match rate</p><p className="mt-1 text-xl font-bold text-slate-900">{percentage(groundTruth.ground_truth.overall_match_rate)}</p></div></div>
        <div className="grid gap-3 px-5 pb-5 sm:grid-cols-2"><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Source data unavailable</p><p className="mt-1 text-xl font-bold text-slate-700">{groundTruth.ground_truth.source_data_unavailable}</p><p className="mt-1 text-xs text-slate-500">Expected fields not present in the supplied input evidence.</p></div><div className="rounded-lg bg-white p-3"><p className="text-xs uppercase tracking-wide text-slate-500">Pipeline missing</p><p className="mt-1 text-xl font-bold text-red-700">{groundTruth.ground_truth.pipeline_missing}</p><p className="mt-1 text-xs text-slate-500">Expected fields with source evidence but no generated value.</p></div></div>
        <div className="border-t border-amber-200 px-5 py-4"><h3 className="font-semibold text-amber-950">Field-level exact and normalized comparison</h3><div className="mt-3 overflow-x-auto"><table className="min-w-full divide-y divide-amber-200 text-left text-xs"><thead className="text-amber-800"><tr><th className="px-3 py-2">Field</th><th className="px-3 py-2">Evaluated</th><th className="px-3 py-2">Exact</th><th className="px-3 py-2">Normalized</th><th className="px-3 py-2">Missing</th><th className="px-3 py-2">Unavailable</th><th className="px-3 py-2">Match rate</th></tr></thead><tbody className="divide-y divide-amber-100">{groundTruth.ground_truth.field_metrics.map((metric) => <tr key={metric.field_name}><td className="px-3 py-2 font-medium text-slate-800">{metric.field_name}</td><td className="px-3 py-2">{metric.evaluated}</td><td className="px-3 py-2">{metric.exact_matches}</td><td className="px-3 py-2">{metric.normalized_matches}</td><td className="px-3 py-2">{metric.missing}</td><td className="px-3 py-2 text-slate-600">{metric.source_data_unavailable}</td><td className="px-3 py-2 font-semibold">{percentage(metric.match_rate)}</td></tr>)}</tbody></table></div></div>
        <div className="border-t border-amber-200 px-5 py-4"><h3 className="font-semibold text-amber-950">Mismatched fields</h3><div className="mt-3 max-h-72 overflow-auto"><table className="min-w-full divide-y divide-amber-200 text-left text-xs"><thead className="text-amber-800"><tr><th className="px-3 py-2">Product</th><th className="px-3 py-2">Field</th><th className="px-3 py-2">Expected</th><th className="px-3 py-2">Generated</th><th className="px-3 py-2">Result</th><th className="px-3 py-2">Availability</th></tr></thead><tbody className="divide-y divide-amber-100">{groundTruth.ground_truth.mismatches.map((mismatch, index) => <tr key={`${mismatch.product_key}-${mismatch.field_name}-${index}`}><td className="px-3 py-2">{mismatch.product_key || '—'}</td><td className="px-3 py-2">{mismatch.field_name}</td><td className="max-w-xs px-3 py-2">{mismatch.expected_value || '—'}</td><td className="max-w-xs px-3 py-2">{mismatch.generated_value || '—'}</td><td className="px-3 py-2 font-semibold">{mismatch.result}</td><td className="px-3 py-2 text-slate-600">{mismatch.availability === 'source_data_unavailable' ? 'Source unavailable' : 'Source available'}</td></tr>)}{!groundTruth.ground_truth.mismatches.length && <tr><td colSpan={6} className="px-3 py-6 text-center text-amber-800">No mismatches were recorded for comparable non-empty fields.</td></tr>}</tbody></table></div><p className="mt-3 text-xs text-amber-800">Unsupported columns: {groundTruth.ground_truth.unsupported_columns.length || 0}. Unknown columns: {groundTruth.ground_truth.unknown_columns.length || 0}. LOV comparison: {groundTruth.ground_truth.lov_comparison_available ? 'available' : 'not available from supplied reference data'}. UOM comparison: {groundTruth.ground_truth.uom_comparison_available ? 'observed in file; no official LOV normalization assumed' : 'not available'}. Character limits: {groundTruth.ground_truth.character_limits_available ? 'available' : 'not available from supplied file'}.</p></div>
      </section>}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {[
          ['Products processed', String(summary?.products_processed ?? 0), 'text-slate-900'],
          ['Fields evaluated', String(summary?.fields_evaluated ?? 0), 'text-slate-900'],
          ['Missing attributes', percentage(summary?.missing_attribute_rate), 'text-amber-700'],
          ['Invalid UOM values', String(summary?.invalid_uom_values ?? 0), 'text-red-700'],
          ['Human-review candidates', String(summary?.human_review_candidates ?? 0), 'text-red-700'],
        ].map(([label, value, colour]) => <div key={label} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><p className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</p><p className={`mt-2 text-2xl font-bold ${colour}`}>{value}</p></div>)}
      </div>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="border-b border-slate-200 px-5 py-4"><h2 className="font-semibold text-slate-900">Field-level rule compliance</h2><p className="mt-1 text-sm text-slate-500">LOV compliance is marked unavailable until an official controlled vocabulary is provided.</p></div>
        <div className="grid gap-3 p-5 sm:grid-cols-2 xl:grid-cols-3">
          {(summary?.metrics || []).map((metric) => <div key={metric.name} className="rounded-lg border border-slate-200 p-4"><div className="flex items-start justify-between gap-3"><p className="text-sm font-medium text-slate-800">{metric.label}</p>{metric.compliance_percentage === null ? <AlertTriangle className="h-4 w-4 text-amber-500" /> : metric.compliance_percentage >= 90 ? <CheckCircle2 className="h-4 w-4 text-green-600" /> : <AlertTriangle className="h-4 w-4 text-amber-600" />}</div><p className="mt-3 text-2xl font-bold text-slate-900">{percentage(metric.compliance_percentage)}</p><p className="mt-1 text-xs text-slate-500">{metric.evaluated ? `${metric.passed}/${metric.evaluated} passed` : metric.unavailable_reason || 'No matched generated output'}</p></div>)}
          {!summary?.metrics?.length && <p className="col-span-full py-4 text-sm text-slate-500">Run the Rule-based Quality Evaluation to calculate field-level metrics.</p>}
        </div>
      </section>

      <section className="rounded-xl border border-slate-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-slate-200 px-5 py-4 md:flex-row md:items-center md:justify-between"><div><h2 className="font-semibold text-slate-900">Failed fields & human-review candidates</h2><p className="mt-1 text-sm text-slate-500">These findings retain the raw input row and never change generated product data.</p></div><label className="relative"><Search className="absolute left-3 top-2.5 h-4 w-4 text-slate-400" /><input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Filter product or field" className="rounded-lg border border-slate-300 py-2 pl-9 pr-3 text-sm outline-none focus:border-indigo-500" /></label></div>
        <div className="overflow-x-auto"><table className="min-w-full divide-y divide-slate-200 text-left text-sm"><thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-5 py-3">Raw product</th><th className="px-5 py-3">Field</th><th className="px-5 py-3">Outcome</th><th className="px-5 py-3">Explanation</th><th className="px-5 py-3"></th></tr></thead><tbody className="divide-y divide-slate-100">{filteredFailures.slice(0, 100).map((failure, index) => <tr key={`${failure.product_result_id}-${failure.field.check_name}-${index}`}><td className="px-5 py-3 font-medium text-slate-900"><div>{failure.input_product_key || 'No Mfg_Part_Num'}</div><div className="text-xs font-normal text-slate-500">CSV row {failure.input_row_number}</div></td><td className="px-5 py-3 text-slate-700">{failure.field.field_name}</td><td className="px-5 py-3"><span className={`rounded-full px-2 py-1 text-xs font-semibold ${outcomeStyle(failure.field.outcome)}`}>{failure.field.outcome}</span></td><td className="max-w-md px-5 py-3 text-slate-600">{failure.field.details}</td><td className="px-5 py-3"><button onClick={() => void openDetail(failure.product_result_id)} className="text-sm font-semibold text-indigo-700 hover:text-indigo-900">Review</button></td></tr>)}{!filteredFailures.length && <tr><td colSpan={5} className="px-5 py-8 text-center text-slate-500">No failures are available for the selected evaluation run.</td></tr>}</tbody></table></div>
      </section>

      {selected && <section className="rounded-xl border border-indigo-200 bg-indigo-50 p-5 shadow-sm"><div className="flex items-start justify-between"><div><h2 className="font-semibold text-indigo-950">Evaluation detail: {selected.input_product_key || `CSV row ${selected.input_row_number}`}</h2><p className="mt-1 text-sm text-indigo-800">{selected.human_review_reason || `Rule-based Quality Score: ${percentage(selected.quality_score)}`}</p></div><button onClick={() => setSelected(null)} className="text-indigo-800 hover:text-indigo-950"><XCircle className="h-5 w-5" /></button></div><div className="mt-4 grid gap-3 md:grid-cols-2">{selected.fields.map((field) => <div key={field.id} className="rounded-lg border border-indigo-100 bg-white p-3"><div className="flex items-center justify-between gap-3"><span className="font-medium text-slate-800">{field.field_name}</span><span className={`rounded-full px-2 py-1 text-xs font-semibold ${outcomeStyle(field.outcome)}`}>{field.outcome}</span></div><p className="mt-2 text-sm text-slate-600">{field.details}</p>{field.generated_value && <p className="mt-2 text-xs text-slate-500">Generated: {field.generated_value}</p>}</div>)}</div></section>}
    </div>
  );
}
