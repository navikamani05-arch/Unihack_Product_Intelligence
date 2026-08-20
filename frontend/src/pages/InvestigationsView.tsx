import React, { useEffect, useMemo, useState } from 'react';
import {
  AlertCircle,
  AlertTriangle,
  CheckCircle2,
  ChevronRight,
  FileText,
  Globe2,
  Loader2,
  Plus,
  RefreshCw,
  SearchCheck,
  Table2,
  Trash2,
} from 'lucide-react';
import { api } from '../services/api';

type SourceDocument = {
  id: number;
  filename: string;
  source_url?: string | null;
};

type AttachedJob = {
  id: number;
  job_id: number;
  job_name: string;
  status: string;
  source_type: string;
  source_count: number;
  evidence_chunk_count: number;
  sources: SourceDocument[];
  attached_at: string;
};

type Investigation = {
  id: number;
  name: string;
  description?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  source_jobs: AttachedJob[];
};

type AvailableJob = {
  id: number;
  job_name: string;
  status: string;
  source_type: string;
  created_at: string;
  source_count: number;
  evidence_chunk_count: number;
};

type IdentityField = {
  field: string;
  value: string;
  source_type?: string | null;
  source_identifier?: string | null;
  source_url?: string | null;
  page_number?: number | null;
  row_number?: number | null;
};

type Match = {
  source_job_ids: number[];
  match_score: number;
  match_status: string;
  reasons: string[];
};

type AttributeValue = {
  job_id: number;
  source_type: string;
  value: string;
  unit?: string | null;
  confidence_score?: number | null;
  source_identifier?: string | null;
  source_url?: string | null;
  page_number?: number | null;
  row_number?: number | null;
  evidence_snippet?: string | null;
  normalized_value?: string | null;
  source_authority?: string | null;
};

type ConflictSummary = {
  attribute_name: string;
  status: string;
  severity?: string | null;
  agreement_count: number;
  total_sources: number;
  agreement_percentage: number;
  missing_job_ids: number[];
};

type Conflict = ConflictSummary & {
  conflict_id?: number | null;
  values: AttributeValue[];
  requires_review: boolean;
  explanation?: string | null;
  suggested_value?: string | null;
  suggestion_reason?: string | null;
  resolution_status?: string;
  resolution_action?: string | null;
  resolution_reason?: string | null;
};

type ConflictDetail = Conflict & {
  source_authority_summary?: { job_id: number; source_type: string; source_authority: string; rank: number }[];
  created_at?: string | null;
  resolved_at?: string | null;
};

type ConflictReport = {
  investigation_id: number;
  total_sources: number;
  conflict_count: number;
  conflicts: Conflict[];
  attribute_summaries: ConflictSummary[];
};

type Comparison = {
  investigation_id: number;
  investigation_name: string;
  status: string;
  source_identities: { job_id: number; source_type: string; product_ids: number[]; identity_fields: IdentityField[] }[];
  matches: Match[];
  attributes: { attribute_name: string; values: AttributeValue[]; different_values_detected: boolean; conflict_status: string; conflict_severity?: string | null; agreement_count: number; total_sources: number }[];
};

const sourceIcon = (sourceType: string) => {
  const kind = sourceType.toLowerCase();
  if (kind === 'website' || kind === 'url') return Globe2;
  if (kind === 'csv') return Table2;
  return FileText;
};

const sourceLabel = (sourceType: string) => {
  const kind = sourceType.toLowerCase();
  if (kind === 'website' || kind === 'url') return 'Website';
  if (kind === 'csv') return 'CSV';
  return 'PDF';
};

const formatField = (field: string) => field.replace(/_/g, ' ').replace(/\b\w/g, (letter) => letter.toUpperCase());

const formatProvenance = (value: AttributeValue | IdentityField) => {
  const type = String(value.source_type || '').toLowerCase();
  if (!type) return 'No source citation available';
  if (type === 'csv') {
    return `CSV · ${value.source_identifier || 'Source'}${value.row_number ? ` · Row ${value.row_number}` : ''}`;
  }
  if (type === 'website' || type === 'url') {
    return `Website · ${value.source_url || value.source_identifier || 'Source URL'}`;
  }
  return `PDF · ${value.source_identifier || 'Source'}${value.page_number ? ` · Page ${value.page_number}` : ''}`;
};

const matchTone = (status: string) => {
  if (status === 'HIGH_CONFIDENCE_MATCH') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (status === 'POSSIBLE_MATCH') return 'bg-blue-100 text-blue-800 border-blue-200';
  if (status === 'LOW_CONFIDENCE_MATCH') return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-rose-100 text-rose-800 border-rose-200';
};

const conflictTone = (status: string) => {
  if (status === 'NO_CONFLICT') return 'bg-emerald-100 text-emerald-800 border-emerald-200';
  if (status === 'MISSING_IN_SOURCE') return 'bg-amber-100 text-amber-800 border-amber-200';
  return 'bg-rose-100 text-rose-800 border-rose-200';
};

const formatConfidence = (score?: number | null) => score === null || score === undefined ? 'Not scored' : `${Math.round(score * 100)}%`;

export const InvestigationsView: React.FC = () => {
  const [investigations, setInvestigations] = useState<Investigation[]>([]);
  const [availableJobs, setAvailableJobs] = useState<AvailableJob[]>([]);
  const [selected, setSelected] = useState<Investigation | null>(null);
  const [comparison, setComparison] = useState<Comparison | null>(null);
  const [conflictReport, setConflictReport] = useState<ConflictReport | null>(null);
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [matching, setMatching] = useState(false);
  const [error, setError] = useState('');
  const [severityFilter, setSeverityFilter] = useState('ALL');
  const [attributeFilter, setAttributeFilter] = useState('');
  const [sourceFilter, setSourceFilter] = useState('ALL');
  const [resolutionFilter, setResolutionFilter] = useState('ALL');
  const [selectedConflictDetail, setSelectedConflictDetail] = useState<ConflictDetail | null>(null);
  const [resolvingConflictId, setResolvingConflictId] = useState<number | null>(null);

  const loadData = async (preferredId?: number) => {
    setLoading(true);
    try {
      const [investigationResponse, jobResponse] = await Promise.all([
        api.listInvestigations(),
        api.getAvailableInvestigationJobs(),
      ]);
      const nextInvestigations: Investigation[] = investigationResponse.data;
      setInvestigations(nextInvestigations);
      setAvailableJobs(jobResponse.data);
      const desiredId = preferredId ?? selected?.id;
      const nextSelected = nextInvestigations.find((item) => item.id === desiredId) ?? nextInvestigations[0] ?? null;
      setSelected(nextSelected);
      if (!nextSelected || nextSelected.id !== desiredId) {
        setComparison(null);
        setConflictReport(null);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load investigations.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    // Initial load only. Subsequent refreshes are triggered by user actions.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const attachedJobIds = useMemo(
    () => new Set(selected?.source_jobs.map((source) => source.job_id) || []),
    [selected]
  );

  const filteredConflicts = useMemo(() => {
    const conflicts = conflictReport?.conflicts || [];
    return conflicts.filter((conflict) => {
      const severityMatches = severityFilter === 'ALL' || conflict.severity === severityFilter;
      const attributeMatches = !attributeFilter.trim() || conflict.attribute_name.toLowerCase().includes(attributeFilter.trim().toLowerCase());
      const sourceMatches = sourceFilter === 'ALL' || conflict.values.some((value) => value.source_type.toLowerCase() === sourceFilter.toLowerCase());
      const resolutionMatches = resolutionFilter === 'ALL' || (conflict.resolution_status || 'unresolved') === resolutionFilter;
      return severityMatches && attributeMatches && sourceMatches && resolutionMatches;
    });
  }, [attributeFilter, conflictReport, resolutionFilter, severityFilter, sourceFilter]);

  const severityCounts = useMemo(() => {
    const counts = { CRITICAL: 0, HIGH: 0, MEDIUM: 0, LOW: 0 };
    (conflictReport?.conflicts || []).forEach((conflict) => {
      if (conflict.severity && conflict.severity in counts) counts[conflict.severity as keyof typeof counts] += 1;
    });
    return counts;
  }, [conflictReport]);

  const createInvestigation = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!name.trim()) return;
    setSaving(true);
    setError('');
    try {
      const response = await api.createInvestigation({
        name: name.trim(),
        description: description.trim() || undefined,
      });
      setName('');
      setDescription('');
      setComparison(null);
      setConflictReport(null);
      await loadData(response.data.id);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to create investigation.');
    } finally {
      setSaving(false);
    }
  };

  const selectInvestigation = (investigation: Investigation) => {
    setSelected(investigation);
    setComparison(null);
    setConflictReport(null);
    setError('');
  };

  const attachJob = async (jobId: number) => {
    if (!selected) return;
    setSaving(true);
    setError('');
    try {
      const response = await api.attachInvestigationJob(selected.id, jobId);
      const updated: Investigation = response.data;
      setSelected(updated);
      setInvestigations((current) => current.map((item) => (item.id === updated.id ? updated : item)));
      setComparison(null);
      setConflictReport(null);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to attach this source.');
    } finally {
      setSaving(false);
    }
  };

  const runMatching = async () => {
    if (!selected) return;
    setMatching(true);
    setError('');
    try {
      const [comparisonResponse, conflictsResponse] = await Promise.all([
        api.getInvestigationComparison(selected.id),
        api.getInvestigationConflicts(selected.id),
      ]);
      setComparison(comparisonResponse.data);
      setConflictReport(conflictsResponse.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to run product matching.');
    } finally {
      setMatching(false);
    }
  };

  const loadConflictDetail = async (conflictId: number) => {
    if (!selected) return;
    setError('');
    try {
      const response = await api.getInvestigationConflict(selected.id, conflictId);
      setSelectedConflictDetail(response.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to load conflict detail.');
    }
  };

  const resolveConflict = async (conflict: Conflict, action: 'ACCEPT_SOURCE_VALUE' | 'ACCEPT_OTHER_VALUE' | 'MARK_AS_UNRESOLVED' | 'MARK_AS_HUMAN_REVIEW') => {
    if (!selected || !conflict.conflict_id) return;
    setResolvingConflictId(conflict.conflict_id);
    setError('');
    try {
      const suggested = conflict.suggested_value || conflict.values[0]?.value;
      const sourceValue = conflict.values[0]?.value;
      const acceptedAction = action === 'ACCEPT_SOURCE_VALUE' && suggested && suggested !== sourceValue ? 'ACCEPT_OTHER_VALUE' : action;
      const response = await api.resolveInvestigationConflict(selected.id, conflict.conflict_id, {
        action: acceptedAction,
        chosen_value: acceptedAction === 'ACCEPT_OTHER_VALUE' ? suggested : undefined,
        reasoning: action === 'MARK_AS_HUMAN_REVIEW'
          ? 'Flagged for human review from the Product Investigations conflict panel.'
          : action === 'MARK_AS_UNRESOLVED'
            ? 'Returned to unresolved review state from the Product Investigations conflict panel.'
            : 'Suggested source-backed value accepted by a reviewer from the Product Investigations conflict panel.',
      });
      setSelectedConflictDetail(response.data);
      const refreshed = await api.getInvestigationConflicts(selected.id);
      setConflictReport(refreshed.data);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to store the conflict review decision.');
    } finally {
      setResolvingConflictId(null);
    }
  };

  const removeInvestigation = async () => {
    if (!selected) return;
    setSaving(true);
    setError('');
    try {
      await api.deleteInvestigation(selected.id);
      setComparison(null);
      setConflictReport(null);
      await loadData();
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : 'Unable to delete investigation.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-2xl bg-gradient-to-r from-slate-900 via-slate-800 to-indigo-900 p-7 text-white shadow-lg">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="mb-2 flex items-center gap-2 text-indigo-200"><SearchCheck className="h-5 w-5" /> Phases 3A–3B workspace</div>
            <h1 className="text-3xl font-bold tracking-tight">Product Investigations</h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-200">
              Attach only the completed sources you intend to compare. Matching and conflict detection remain explainable and preserve every source citation.
            </p>
          </div>
          <div className="rounded-xl border border-white/15 bg-white/10 px-4 py-3 text-sm text-slate-100">
            <span className="font-semibold">Isolation preserved.</span> Unattached jobs are never included.
          </div>
        </div>
      </section>

      {error && (
        <div className="flex items-start gap-3 rounded-xl border border-rose-200 bg-rose-50 p-4 text-rose-800">
          <AlertCircle className="mt-0.5 h-5 w-5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="grid gap-6 xl:grid-cols-[340px_minmax(0,1fr)]">
        <aside className="space-y-5">
          <form onSubmit={createInvestigation} className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-lg font-semibold text-slate-900">New investigation</h2>
            <p className="mt-1 text-sm text-slate-500">Create a workspace before attaching completed ingestion jobs.</p>
            <label className="mt-4 block text-sm font-medium text-slate-700">Name</label>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              placeholder="SIMOTICS GP Motor Investigation"
              maxLength={255}
            />
            <label className="mt-3 block text-sm font-medium text-slate-700">Description <span className="font-normal text-slate-400">(optional)</span></label>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              className="mt-1 min-h-[80px] w-full resize-y rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none transition focus:border-indigo-500 focus:ring-2 focus:ring-indigo-100"
              placeholder="Multi-source analysis of one product"
              maxLength={4000}
            />
            <button
              type="submit"
              disabled={!name.trim() || saving}
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              Create investigation
            </button>
          </form>

          <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-sm">
            <div className="flex items-center justify-between px-2 py-2">
              <h2 className="font-semibold text-slate-900">Your workspaces</h2>
              <button onClick={() => loadData(selected?.id)} className="rounded p-1.5 text-slate-500 hover:bg-slate-100" title="Refresh investigations">
                <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              </button>
            </div>
            {loading ? (
              <div className="px-2 py-8 text-center text-sm text-slate-500">Loading investigations…</div>
            ) : investigations.length === 0 ? (
              <div className="px-2 py-8 text-center text-sm text-slate-500">No investigations yet.</div>
            ) : (
              <div className="space-y-1">
                {investigations.map((investigation) => (
                  <button
                    key={investigation.id}
                    onClick={() => selectInvestigation(investigation)}
                    className={`w-full rounded-xl px-3 py-3 text-left transition ${selected?.id === investigation.id ? 'bg-indigo-50 ring-1 ring-indigo-200' : 'hover:bg-slate-50'}`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <span className="font-medium text-slate-900">{investigation.name}</span>
                      <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                    </div>
                    <div className="mt-1 text-xs text-slate-500">{investigation.source_jobs.length} attached source job{investigation.source_jobs.length === 1 ? '' : 's'}</div>
                  </button>
                ))}
              </div>
            )}
          </section>
        </aside>

        <main className="min-w-0 space-y-6">
          {!selected ? (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center shadow-sm">
              <SearchCheck className="mx-auto h-10 w-10 text-slate-300" />
              <h2 className="mt-4 text-lg font-semibold text-slate-800">Start a product investigation</h2>
              <p className="mx-auto mt-2 max-w-md text-sm text-slate-500">Create a workspace, then attach the PDF, website, and CSV jobs that describe the product you want to investigate.</p>
            </div>
          ) : (
            <>
              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col justify-between gap-4 md:flex-row md:items-start">
                  <div>
                    <div className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">{selected.status}</div>
                    <h2 className="mt-1 text-2xl font-bold text-slate-900">{selected.name}</h2>
                    {selected.description && <p className="mt-2 text-sm text-slate-600">{selected.description}</p>}
                  </div>
                  <div className="flex flex-wrap gap-2">
                    <button onClick={runMatching} disabled={matching || selected.source_jobs.length < 2} className="inline-flex items-center gap-2 rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-50">
                      {matching ? <Loader2 className="h-4 w-4 animate-spin" /> : <SearchCheck className="h-4 w-4" />}
                      Run matching & conflict detection
                    </button>
                    <button onClick={removeInvestigation} disabled={saving} className="inline-flex items-center gap-2 rounded-lg border border-rose-200 px-3 py-2.5 text-sm font-medium text-rose-700 transition hover:bg-rose-50 disabled:opacity-50">
                      <Trash2 className="h-4 w-4" /> Delete
                    </button>
                  </div>
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <div className="flex flex-col justify-between gap-2 sm:flex-row sm:items-end">
                  <div>
                    <h3 className="text-lg font-semibold text-slate-900">Attach completed sources</h3>
                    <p className="mt-1 text-sm text-slate-500">Each attachment is a reference to the existing ingestion job—evidence is not copied.</p>
                  </div>
                  <span className="text-sm font-medium text-slate-500">{selected.source_jobs.length} attached</span>
                </div>
                <div className="mt-4 grid gap-3 lg:grid-cols-2">
                  {availableJobs.length === 0 ? (
                    <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">No completed ingestion jobs are available. Ingest a PDF, website, or CSV first.</p>
                  ) : availableJobs.map((job) => {
                    const Icon = sourceIcon(job.source_type);
                    const attached = attachedJobIds.has(job.id);
                    return (
                      <div key={job.id} className="flex items-center justify-between gap-3 rounded-xl border border-slate-200 p-4">
                        <div className="flex min-w-0 items-center gap-3">
                          <div className="rounded-lg bg-slate-100 p-2 text-slate-600"><Icon className="h-5 w-5" /></div>
                          <div className="min-w-0">
                            <div className="truncate text-sm font-semibold text-slate-800">{job.job_name}</div>
                            <div className="mt-0.5 text-xs text-slate-500">{sourceLabel(job.source_type)} · {job.evidence_chunk_count} evidence record{job.evidence_chunk_count === 1 ? '' : 's'}</div>
                          </div>
                        </div>
                        <button
                          onClick={() => attachJob(job.id)}
                          disabled={attached || saving}
                          className={`shrink-0 rounded-lg px-3 py-2 text-xs font-semibold transition ${attached ? 'bg-emerald-50 text-emerald-700' : 'bg-indigo-600 text-white hover:bg-indigo-700'} disabled:cursor-not-allowed disabled:opacity-60`}
                        >
                          {attached ? 'Attached' : 'Attach'}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </section>

              <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                <h3 className="text-lg font-semibold text-slate-900">Attached sources</h3>
                {selected.source_jobs.length === 0 ? (
                  <p className="mt-3 rounded-lg bg-slate-50 p-4 text-sm text-slate-500">Attach at least two completed source jobs to enable product matching.</p>
                ) : (
                  <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                    {selected.source_jobs.map((source) => {
                      const Icon = sourceIcon(source.source_type);
                      return (
                        <div key={source.id} className="rounded-xl border border-slate-200 p-4">
                          <div className="flex items-center gap-2 text-sm font-semibold text-slate-800"><Icon className="h-4 w-4 text-indigo-600" /> {sourceLabel(source.source_type)}</div>
                          <div className="mt-2 space-y-1.5 text-sm text-slate-600">
                            {source.sources.map((document) => <div key={document.id} className="truncate" title={document.source_url || document.filename}>{document.source_url || document.filename}</div>)}
                            <div className="text-xs text-slate-400">{source.evidence_chunk_count} evidence record{source.evidence_chunk_count === 1 ? '' : 's'}</div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </section>

              {comparison && (
                <>
                  <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <div className="flex items-center gap-2"><CheckCircle2 className="h-5 w-5 text-emerald-600" /><h3 className="text-lg font-semibold text-slate-900">Product match</h3></div>
                    {comparison.matches.length === 0 ? (
                      <p className="mt-4 text-sm text-slate-500">Attach at least two sources to generate a comparison.</p>
                    ) : (
                      <div className="mt-4 grid gap-4 xl:grid-cols-2">
                        {comparison.matches.map((match) => (
                          <article key={match.source_job_ids.join('-')} className="rounded-xl border border-slate-200 bg-slate-50 p-5">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <div className="text-3xl font-bold text-slate-900">{match.match_score}%</div>
                                <div className="text-xs text-slate-500">Jobs #{match.source_job_ids.join(' and #')}</div>
                              </div>
                              <span className={`rounded-full border px-3 py-1.5 text-xs font-bold ${matchTone(match.match_status)}`}>{formatField(match.match_status)}</span>
                            </div>
                            <div className="mt-4 border-t border-slate-200 pt-3">
                              <div className="text-xs font-bold uppercase tracking-wide text-slate-500">Why this result</div>
                              <ul className="mt-2 space-y-1.5 text-sm text-slate-700">
                                {match.reasons.map((reason) => <li key={reason} className="flex gap-2"><span className="text-indigo-600">•</span><span>{reason}</span></li>)}
                              </ul>
                            </div>
                          </article>
                        ))}
                      </div>
                    )}
                  </section>

                  {conflictReport && (
                    <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <AlertTriangle className={`h-5 w-5 ${conflictReport.conflict_count ? 'text-amber-600' : 'text-emerald-600'}`} />
                            <h3 className="text-lg font-semibold text-slate-900">Conflict detection</h3>
                          </div>
                          <p className="mt-1 text-sm text-slate-500">Values are normalized before comparison. This view never selects or overwrites a source value.</p>
                        </div>
                        <span className={`w-fit rounded-full border px-3 py-1.5 text-xs font-bold ${conflictReport.conflict_count ? 'border-amber-200 bg-amber-50 text-amber-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>
                          {conflictReport.conflict_count ? `${conflictReport.conflict_count} requires review` : 'No conflicts detected'}
                        </span>
                      </div>
                      {conflictReport.conflict_count === 0 ? (
                        <div className="mt-4 rounded-xl border border-emerald-100 bg-emerald-50 p-4 text-sm text-emerald-800">All compared attributes are consistent across the attached sources.</div>
                      ) : (
                        <div className="mt-4 space-y-4">
                          <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
                            {(['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] as const).map((severity) => (
                              <button key={severity} onClick={() => setSeverityFilter(severityFilter === severity ? 'ALL' : severity)} className={`rounded-lg border px-3 py-2 text-left text-xs font-semibold ${severityFilter === severity ? 'border-indigo-300 bg-indigo-50 text-indigo-800' : 'border-slate-200 bg-slate-50 text-slate-700'}`}>
                                {severity}: {severityCounts[severity]}
                              </button>
                            ))}
                          </div>
                          <div className="grid gap-2 rounded-xl border border-slate-200 bg-slate-50 p-3 md:grid-cols-4">
                            <input value={attributeFilter} onChange={(event) => setAttributeFilter(event.target.value)} placeholder="Filter attribute" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm" />
                            <select value={sourceFilter} onChange={(event) => setSourceFilter(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="ALL">All sources</option><option value="pdf">PDF</option><option value="csv">CSV</option><option value="website">Website</option></select>
                            <select value={resolutionFilter} onChange={(event) => setResolutionFilter(event.target.value)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"><option value="ALL">All review states</option><option value="unresolved">Unresolved</option><option value="human_review">Human review</option><option value="resolved_source_value">Resolved from source</option><option value="resolved_other_value">Resolved from other source</option></select>
                            <button onClick={() => { setSeverityFilter('ALL'); setAttributeFilter(''); setSourceFilter('ALL'); setResolutionFilter('ALL'); }} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm font-medium text-slate-700 hover:bg-slate-100">Clear filters</button>
                          </div>
                          {filteredConflicts.length === 0 ? <p className="rounded-lg bg-slate-50 p-4 text-sm text-slate-500">No conflicts match the selected filters.</p> : filteredConflicts.map((conflict) => (
                            <article key={conflict.conflict_id || `${conflict.attribute_name}-${conflict.status}`} className="rounded-xl border border-amber-200 bg-amber-50/40 p-5">
                              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                                <div>
                                  <div className="flex flex-wrap items-center gap-2">
                                    <h4 className="font-semibold text-slate-900">{formatField(conflict.attribute_name)}</h4>
                                    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-bold ${conflictTone(conflict.status)}`}>{formatField(conflict.status)}</span>
                                    {conflict.severity && <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-bold text-white">{conflict.severity}</span>}
                                    <span className="rounded-full border border-slate-200 bg-white px-2.5 py-1 text-[11px] font-semibold text-slate-700">{formatField(conflict.resolution_status || 'unresolved')}</span>
                                  </div>
                                  <p className="mt-1 text-sm text-slate-600">Agreement: <strong>{conflict.agreement_count} / {conflict.total_sources}</strong> sources ({conflict.agreement_percentage}%).</p>
                                  {conflict.explanation && <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-700">{conflict.explanation}</p>}
                                </div>
                                {conflict.missing_job_ids.length > 0 && <span className="text-xs font-medium text-amber-800">Missing in job{conflict.missing_job_ids.length > 1 ? 's' : ''} #{conflict.missing_job_ids.join(', #')}</span>}
                              </div>
                              {conflict.suggested_value && <div className="mt-4 rounded-lg border border-indigo-100 bg-indigo-50 p-3 text-sm text-indigo-950"><strong>Suggested value for human review:</strong> {conflict.suggested_value}<div className="mt-1 text-xs leading-5 text-indigo-800">{conflict.suggestion_reason}</div></div>}
                              <div className="mt-4 grid gap-3 lg:grid-cols-3">
                                {conflict.values.map((value, index) => (
                                  <div key={`${value.job_id}-${index}-${value.value}`} className="rounded-lg border border-slate-200 bg-white p-3">
                                    <div className="text-base font-semibold text-slate-900">{value.value}{value.unit && !value.value.toLowerCase().includes(value.unit.toLowerCase()) ? ` ${value.unit}` : ''}</div>
                                    <div className="mt-1 text-xs text-slate-500">Normalized: {value.normalized_value || value.value}</div>
                                    <div className="mt-1 text-xs text-slate-500">{formatProvenance(value)}</div>
                                    <div className="mt-2 text-xs font-medium text-slate-700">Confidence: {formatConfidence(value.confidence_score)} · Authority: {formatField(value.source_authority || 'unknown')}</div>
                                    {value.evidence_snippet && <div className="mt-2 line-clamp-3 text-xs leading-5 text-slate-500" title={value.evidence_snippet}>Evidence: {value.evidence_snippet}</div>}
                                  </div>
                                ))}
                              </div>
                              <div className="mt-4 flex flex-wrap gap-2 border-t border-amber-100 pt-4">
                                {conflict.conflict_id && <button onClick={() => loadConflictDetail(conflict.conflict_id!)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100">View detail</button>}
                                {conflict.conflict_id && <button disabled={resolvingConflictId === conflict.conflict_id} onClick={() => resolveConflict(conflict, 'ACCEPT_SOURCE_VALUE')} className="rounded-lg bg-indigo-600 px-3 py-2 text-xs font-semibold text-white hover:bg-indigo-700 disabled:opacity-60">Resolve suggested</button>}
                                {conflict.conflict_id && <button disabled={resolvingConflictId === conflict.conflict_id} onClick={() => resolveConflict(conflict, 'MARK_AS_HUMAN_REVIEW')} className="rounded-lg border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900 hover:bg-amber-100 disabled:opacity-60">Needs human review</button>}
                                {conflict.conflict_id && (conflict.resolution_status || 'unresolved') !== 'unresolved' && <button disabled={resolvingConflictId === conflict.conflict_id} onClick={() => resolveConflict(conflict, 'MARK_AS_UNRESOLVED')} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 disabled:opacity-60">Mark unresolved</button>}
                              </div>
                              {selectedConflictDetail?.conflict_id === conflict.conflict_id && <div className="mt-3 rounded-lg border border-slate-200 bg-white p-3 text-xs text-slate-600"><strong className="text-slate-800">Persisted review detail.</strong> {selectedConflictDetail.resolution_reason || 'No reviewer reasoning has been recorded.'}{selectedConflictDetail.resolved_at && <span className="ml-2">Decision recorded: {new Date(selectedConflictDetail.resolved_at).toLocaleString()}.</span>}</div>}
                            </article>
                          ))}
                        </div>
                      )}
                    </section>
                  )}

                  <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-slate-900">Source-backed product identity</h3>
                    <p className="mt-1 text-sm text-slate-500">Unspecified fields remain marked as not found; no identifier is generated or inferred.</p>
                    <div className="mt-4 grid gap-4 xl:grid-cols-3">
                      {comparison.source_identities.map((identity) => (
                        <article key={identity.job_id} className="overflow-hidden rounded-xl border border-slate-200">
                          <div className="bg-slate-50 px-4 py-3 text-sm font-semibold text-slate-800">Job #{identity.job_id} · {sourceLabel(identity.source_type)}</div>
                          <dl className="divide-y divide-slate-100">
                            {identity.identity_fields.map((field) => (
                              <div key={field.field} className="px-4 py-2.5">
                                <dt className="text-xs font-medium uppercase tracking-wide text-slate-500">{formatField(field.field)}</dt>
                                <dd className="mt-1 text-sm font-medium text-slate-800">{field.value}</dd>
                                {field.source_type && <div className="mt-1 text-xs text-slate-500">{formatProvenance(field)}</div>}
                              </div>
                            ))}
                          </dl>
                        </article>
                      ))}
                    </div>
                  </section>

                  <section className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
                    <h3 className="text-lg font-semibold text-slate-900">Source comparison</h3>
                    <p className="mt-1 text-sm text-slate-500">Each value retains its source, confidence, agreement, and Phase 3B conflict status. No value is automatically selected or resolved.</p>
                    {comparison.attributes.length === 0 ? (
                      <p className="mt-4 rounded-lg bg-slate-50 p-4 text-sm text-slate-500">No extracted attributes from the attached jobs are available yet. Run extraction for each source job, then refresh matching.</p>
                    ) : (
                      <div className="mt-4 overflow-x-auto rounded-xl border border-slate-200">
                        <table className="min-w-full divide-y divide-slate-200 text-left text-sm">
                          <thead className="bg-slate-50 text-xs uppercase tracking-wide text-slate-500"><tr><th className="px-4 py-3 font-semibold">Attribute</th><th className="px-4 py-3 font-semibold">Source values and provenance</th><th className="px-4 py-3 font-semibold">Observation</th></tr></thead>
                          <tbody className="divide-y divide-slate-100 bg-white">
                            {comparison.attributes.map((attribute) => (
                              <tr key={attribute.attribute_name}>
                                <td className="whitespace-nowrap px-4 py-3 font-medium text-slate-800">{formatField(attribute.attribute_name)}</td>
                                <td className="px-4 py-3">
                                  <div className="space-y-2">{attribute.values.map((value, index) => <div key={`${value.job_id}-${index}`}><div className="font-medium text-slate-800">{value.value}{value.unit && !value.value.toLowerCase().includes(value.unit.toLowerCase()) ? ` ${value.unit}` : ''}</div><div className="text-xs text-slate-500">{formatProvenance(value)}</div><div className="text-xs text-slate-500">Confidence: {formatConfidence(value.confidence_score)}</div></div>)}</div>
                                </td>
                                <td className="px-4 py-3"><div className="space-y-2"><span className={`inline-block rounded-full border px-2.5 py-1 text-xs font-medium ${conflictTone(attribute.conflict_status)}`}>{formatField(attribute.conflict_status)}</span><div className="text-xs text-slate-500">Agreement: {attribute.agreement_count}/{attribute.total_sources}{attribute.conflict_severity ? ` · ${attribute.conflict_severity}` : ''}</div></div></td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    )}
                  </section>
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
};
