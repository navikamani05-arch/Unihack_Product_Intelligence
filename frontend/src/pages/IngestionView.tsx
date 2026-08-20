import React, { useEffect, useRef, useState } from 'react';
import { Upload, CheckCircle, AlertCircle, Clock, FileText, Globe, Table } from 'lucide-react';
import { api } from '../services/api';

interface UploadStatus {
  status: 'idle' | 'uploading' | 'processing' | 'completed' | 'error';
  message: string;
  jobId?: number;
  totalPages?: number;
  chunksCreated?: number;
  error?: string;
  sourceType?: string;
}

type SourceType = 'pdf' | 'website' | 'csv';
type ExtractionStatus = 'idle' | 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled' | 'error';

interface ExtractionTaskStatus {
  job_id: number;
  task_id: number;
  status: string;
  current_batch: number;
  total_batches: number;
  processed_evidence_count: number;
  total_evidence_count: number;
  extracted_product_count: number;
  error?: string | null;
  cancellation_requested?: boolean;
  result?: any;
}

async function readJsonResponse<T = any>(response: Response, fallbackMessage: string): Promise<T> {
  const contentType = response.headers.get('content-type') || 'unknown';
  const body = await response.text();
  const trimmedBody = body.trim();

  if (!response.ok) {
    if (trimmedBody.startsWith('<')) {
      throw new Error(
        `Request failed with HTTP ${response.status} (${contentType}): the server returned an HTML error page. Check the frontend proxy and backend URL.`,
      );
    }

    let parsed: any;
    try {
      parsed = JSON.parse(trimmedBody);
    } catch {
      throw new Error(`${fallbackMessage} (HTTP ${response.status}, ${contentType})`);
    }
    const detail = Array.isArray(parsed?.detail)
      ? parsed.detail.map((item: any) => item?.msg || String(item)).join('; ')
      : parsed?.detail;
    throw new Error(detail || `${fallbackMessage} (HTTP ${response.status})`);
  }

  if (!trimmedBody) {
    throw new Error(`${fallbackMessage}: the server returned an empty response (HTTP ${response.status})`);
  }

  try {
    return JSON.parse(trimmedBody) as T;
  } catch {
    throw new Error(
      `${fallbackMessage}: the server returned non-JSON content (${contentType}, HTTP ${response.status})`,
    );
  }
}

export const IngestionView: React.FC = () => {
  const [sourceType, setSourceType] = useState<SourceType>('pdf');
  const [uploadStatus, setUploadStatus] = useState<UploadStatus>({
    status: 'idle',
    message: 'Ready to ingest data',
  });
  const [isDragging, setIsDragging] = useState(false);
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [extractionStatus, setExtractionStatus] = useState<ExtractionStatus>('idle');
  const [extractionError, setExtractionError] = useState('');
  const [extractionTask, setExtractionTask] = useState<ExtractionTaskStatus | null>(null);
  const [productResults, setProductResults] = useState<any[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const extractionPollRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => {
      if (extractionPollRef.current) {
        clearTimeout(extractionPollRef.current);
      }
    };
  }, []);

  const resetExtractionState = () => {
    if (extractionPollRef.current) {
      clearTimeout(extractionPollRef.current);
      extractionPollRef.current = null;
    }
    setProductResults([]);
    setExtractionStatus('idle');
    setExtractionError('');
    setExtractionTask(null);
  };

  const applyCompletedResult = (payload: any) => {
    const result = payload?.result || payload;
    const extractedProducts = Array.isArray(result?.extracted_products)
      ? result.extracted_products
      : result?.extracted_data
        ? [result.extracted_data]
        : [];
    setProductResults(extractedProducts);
  };

  const normalizeExtractionStatus = (status: string): ExtractionStatus => {
    const normalized = String(status || '').toLowerCase();
    if (normalized === 'queued') return 'queued';
    if (normalized === 'processing') return 'processing';
    if (normalized === 'completed' || normalized === 'success') return 'completed';
    if (normalized === 'cancelled') return 'cancelled';
    if (normalized === 'failed') return 'failed';
    return 'error';
  };

  const pollExtractionStatus = async (jobId: number, taskId: number): Promise<void> => {
    try {
      const response = await fetch(`/api/v1/extract/tasks/${taskId}/status`);
      const data = await readJsonResponse<ExtractionTaskStatus>(response, 'Could not read extraction status');
      const nextStatus = normalizeExtractionStatus(data.status);
      setExtractionTask(data);
      setExtractionStatus(nextStatus);

      if (nextStatus === 'completed') {
        applyCompletedResult(data);
        return;
      }
      if (nextStatus === 'failed' || nextStatus === 'cancelled' || nextStatus === 'error') {
        setExtractionError(data.error || (nextStatus === 'cancelled' ? 'Extraction cancelled.' : 'Product extraction failed.'));
        return;
      }

      extractionPollRef.current = setTimeout(() => {
        void pollExtractionStatus(jobId, taskId);
      }, 1500);
    } catch (error) {
      setExtractionStatus('error');
      setExtractionError(error instanceof Error ? error.message : 'Could not read extraction status');
    }
  };

  const handleExtractionCancel = async () => {
    if (!extractionTask?.task_id) return;
    try {
      const response = await fetch(`/api/v1/extract/tasks/${extractionTask.task_id}/cancel`, { method: 'POST' });
      const data = await readJsonResponse<ExtractionTaskStatus>(response, 'Could not cancel extraction');
      setExtractionTask(data);
      setExtractionStatus(normalizeExtractionStatus(data.status));
      if (data.status === 'CANCELLED') {
        setExtractionError(data.error || 'Extraction cancelled.');
      }
    } catch (error) {
      setExtractionError(error instanceof Error ? error.message : 'Could not cancel extraction');
    }
  };


  const handleFileSelect = async (file: File) => {
    if (sourceType === 'pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
      setUploadStatus({
        status: 'error',
        message: 'Please select a PDF file',
        error: 'Only PDF files are supported',
      });
      return;
    }

    if (sourceType === 'csv' && !file.name.toLowerCase().endsWith('.csv')) {
      setUploadStatus({
        status: 'error',
        message: 'Please select a CSV file',
        error: 'Only CSV files are supported',
      });
      return;
    }

    try {
      resetExtractionState();
      setUploadStatus({
        status: 'uploading',
        message: `Uploading ${sourceType.toUpperCase()} file...`,
        sourceType,
      });

      const formData = new FormData();
      formData.append('file', file);
      formData.append('job_name', `Upload - ${file.name}`);

      const endpoint =
        sourceType === 'pdf'
          ? '/api/v1/ingest/upload-pdf'
          : '/api/v1/ingest/upload-csv';

      const response = await fetch(endpoint, {
        method: 'POST',
        body: formData,
      });

      const data = await readJsonResponse<any>(response, 'Upload failed');

      setUploadStatus({
        status: 'completed',
        message: `${sourceType.toUpperCase()} processed successfully`,
        jobId: data.job_id,
        totalPages: data.total_pages,
        chunksCreated: data.chunks_created,
        sourceType,
      });
    } catch (error) {
      setUploadStatus({
        status: 'error',
        message: 'Upload failed',
        error: error instanceof Error ? error.message : 'Unknown error',
        sourceType,
      });
    }
  };

  const handleWebsiteSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!websiteUrl.trim()) {
      setUploadStatus({
        status: 'error',
        message: 'Please enter a URL',
        error: 'URL is required',
        sourceType: 'website',
      });
      return;
    }

    try {
      resetExtractionState();
      setUploadStatus({
        status: 'uploading',
        message: 'Fetching website content...',
        sourceType: 'website',
      });

      const response = await fetch(
        `/api/v1/ingest/upload-website?url=${encodeURIComponent(websiteUrl)}&job_name=Website+Upload`,
        {
          method: 'POST',
        }
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Ingestion failed');
      }

      const data = await response.json();

      setUploadStatus({
        status: 'completed',
        message: 'Website processed successfully',
        jobId: data.job_id,
        totalPages: data.total_pages,
        chunksCreated: data.chunks_created,
        sourceType: 'website',
      });

      setWebsiteUrl('');
    } catch (error) {
      setUploadStatus({
        status: 'error',
        message: 'Website ingestion failed',
        error: error instanceof Error ? error.message : 'Unknown error',
        sourceType: 'website',
      });
    }
  };

  const handleExtraction = async () => {
    if (!uploadStatus.jobId) return;

    try {
      resetExtractionState();
      setExtractionStatus('queued');
      setExtractionError('');
      const response = await fetch(`/api/v1/extract/${uploadStatus.jobId}`, {
        method: 'POST',
      });
      const data = await readJsonResponse<any>(response, 'Product extraction failed');
      const initialStatus = normalizeExtractionStatus(data.status);
      setExtractionTask({
        job_id: uploadStatus.jobId,
        task_id: data.task_id,
        status: data.status,
        current_batch: 0,
        total_batches: 0,
        processed_evidence_count: 0,
        total_evidence_count: uploadStatus.chunksCreated || 0,
        extracted_product_count: 0,
      });
      setExtractionStatus(initialStatus);

      if (initialStatus === 'completed') {
        applyCompletedResult(data);
        return;
      }
      if (!data.task_id) {
        throw new Error('Product extraction did not return a task ID.');
      }
      await pollExtractionStatus(uploadStatus.jobId, data.task_id);
    } catch (error) {
      setExtractionStatus('error');
      setExtractionError(error instanceof Error ? error.message : 'Unknown extraction error');
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = () => {
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.currentTarget.files;
    if (files && files.length > 0) {
      handleFileSelect(files[0]);
    }
  };

  const handleClick = () => {
    if (sourceType !== 'website') {
      fileInputRef.current?.click();
    }
  };

  const formatAttributeValue = (attribute: any) => {
    const value = attribute.normalized_value ?? attribute.raw_value;
    if (value === null || value === undefined || String(value).trim() === '') {
      return 'Not found in provided sources';
    }

    const text = String(value).trim();
    const unit = typeof attribute.unit === 'string' ? attribute.unit.trim() : '';
    if (!unit) return text;

    // The backend normalizes repeated units; this view keeps a final presentation guard.
    const terminalUnit = new RegExp(`\\\\s${unit.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&')}$`, 'i');
    return terminalUnit.test(text) ? text : `${text} ${unit}`;
  };

  const formatConfidence = (attribute: any) => {
    const score = attribute.confidence_score;
    if (attribute.raw_value === null || attribute.raw_value === undefined || score === null || score === undefined) {
      return <span className="text-xs text-gray-400">Not scored</span>;
    }
    const percentage = Math.round(score * 100);
    const label = score >= 0.9 ? 'High' : score >= 0.6 ? 'Medium' : 'Low';
    const color = score >= 0.9 ? 'bg-green-100 text-green-700' : score >= 0.6 ? 'bg-yellow-100 text-yellow-700' : 'bg-red-100 text-red-700';
    return <span className={`px-2 py-0.5 rounded text-xs ${color}`}>{label} · {percentage}%</span>;
  };

  const formatProvenance = (item: any) => {
    const sourceType = String(item.source_type || '').toLowerCase();
    if (sourceType === 'csv') {
      return `CSV · ${item.source_identifier || 'Source'}${item.row_number ? ` · Row ${item.row_number}` : ''}`;
    }
    if (sourceType === 'pdf') {
      return `PDF · ${item.source_identifier || 'Source'}${item.page_number ? ` · Page ${item.page_number}` : ''}`;
    }
    if (sourceType === 'website') {
      return `Website · ${item.source_url || item.source_identifier || 'Source URL'}`;
    }
    return item.source_identifier || item.source_url || 'Source';
  };

  const getStatusIcon = () => {
    switch (uploadStatus.status) {
      case 'uploading':
      case 'processing':
        return <Clock className="w-12 h-12 text-primary-500 animate-spin" />;
      case 'completed':
        return <CheckCircle className="w-12 h-12 text-success-500" />;
      case 'error':
        return <AlertCircle className="w-12 h-12 text-danger-500" />;
      default:
        return null;
    }
  };

  const getStatusColor = () => {
    switch (uploadStatus.status) {
      case 'completed':
        return 'bg-success-50 border-success-200';
      case 'error':
        return 'bg-danger-50 border-danger-200';
      case 'uploading':
      case 'processing':
        return 'bg-primary-50 border-primary-200';
      default:
        return 'bg-gray-50 border-gray-200';
    }
  };

  const getSourceIcon = () => {
    switch (sourceType) {
      case 'pdf':
        return <FileText className="w-16 h-16 text-gray-400" />;
      case 'website':
        return <Globe className="w-16 h-16 text-gray-400" />;
      case 'csv':
        return <Table className="w-16 h-16 text-gray-400" />;
    }
  };

  const getSourcePlaceholder = () => {
    switch (sourceType) {
      case 'pdf':
        return 'Drop PDF here or click to select';
      case 'website':
        return 'Enter website URL';
      case 'csv':
        return 'Drop CSV here or click to select';
    }
  };

  const getSourceDescription = () => {
    switch (sourceType) {
      case 'pdf':
        return 'Supported format: PDF files only';
      case 'website':
        return 'Enter a valid product page URL (http:// or https://)';
      case 'csv':
        return 'Supported format: CSV files only';
    }
  };

  return (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Multi-Source Ingestion</h2>

      {/* Source Type Selection */}
      <div className="grid grid-cols-3 gap-4">
        {(['pdf', 'website', 'csv'] as const).map((type) => (
          <button
            key={type}
            onClick={() => {
              setSourceType(type);
              setUploadStatus({ status: 'idle', message: 'Ready to ingest data' });
              resetExtractionState();
            }}
            className={`p-4 rounded-lg border-2 transition-all ${
              sourceType === type
                ? 'border-primary-500 bg-primary-50'
                : 'border-gray-200 hover:border-primary-300'
            }`}
          >
            <div className="flex items-center justify-center mb-2">
              {type === 'pdf' && <FileText className="w-8 h-8" />}
              {type === 'website' && <Globe className="w-8 h-8" />}
              {type === 'csv' && <Table className="w-8 h-8" />}
            </div>
            <p className="font-semibold text-gray-900 capitalize">{type}</p>
            <p className="text-xs text-gray-500 mt-1">
              {type === 'pdf' && 'Upload PDF'}
              {type === 'website' && 'Enter URL'}
              {type === 'csv' && 'Upload CSV'}
            </p>
          </button>
        ))}
      </div>

      {/* PDF/CSV Upload Area */}
      {sourceType !== 'website' && (
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={handleClick}
          className={`border-2 border-dashed rounded-lg p-12 text-center cursor-pointer transition-colors ${
            isDragging
              ? 'border-primary-500 bg-primary-50'
              : 'border-gray-300 hover:border-primary-400'
          }`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept={sourceType === 'pdf' ? '.pdf' : '.csv'}
            onChange={handleInputChange}
            className="hidden"
          />
          <div className="flex flex-col items-center gap-3">
            {getSourceIcon()}
            <div>
              <p className="text-lg font-semibold text-gray-900">
                {getSourcePlaceholder()}
              </p>
              <p className="text-sm text-gray-500 mt-1">{getSourceDescription()}</p>
            </div>
          </div>
        </div>
      )}

      {/* Website URL Input */}
      {sourceType === 'website' && (
        <form onSubmit={handleWebsiteSubmit} className="space-y-4">
          <div className="flex gap-2">
            <input
              type="url"
              value={websiteUrl}
              onChange={(e) => setWebsiteUrl(e.target.value)}
              placeholder="https://example.com/product"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              type="submit"
              className="px-6 py-2 bg-primary-500 text-white rounded-lg hover:bg-primary-600 transition-colors font-medium"
            >
              Process
            </button>
          </div>
          <p className="text-sm text-gray-500">{getSourceDescription()}</p>
        </form>
      )}

      {/* Status Display */}
      {uploadStatus.status !== 'idle' && (
        <div className={`border rounded-lg p-6 ${getStatusColor()}`}>
          <div className="flex items-start gap-4">
            {getStatusIcon()}
            <div className="flex-1">
              <h3 className="font-semibold text-gray-900 mb-1">
                {uploadStatus.message}
              </h3>
              {uploadStatus.error && (
                <p className="text-sm text-danger-600">{uploadStatus.error}</p>
              )}
              {uploadStatus.status === 'completed' && (
                <div className="mt-3 space-y-3 text-sm text-gray-700">
                  <div className="space-y-1">
                    <p><span className="font-medium">Job ID:</span> {uploadStatus.jobId}</p>
                    <p><span className="font-medium">Source Type:</span> {uploadStatus.sourceType?.toUpperCase()}</p>
                    <p><span className="font-medium">Records Extracted:</span> {uploadStatus.chunksCreated}</p>
                  </div>
                  <button
                    type="button"
                    onClick={handleExtraction}
                    disabled={extractionStatus === 'queued' || extractionStatus === 'processing'}
                    className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 disabled:opacity-50 font-medium"
                  >
                    {extractionStatus === 'queued' || extractionStatus === 'processing'
                      ? 'Product Intelligence in progress...'
                      : 'Extract Product Intelligence'}
                  </button>

                  {extractionTask && extractionStatus !== 'idle' && (
                    <div className="mt-3 rounded-md border border-indigo-100 bg-indigo-50 p-3 text-sm text-indigo-900">
                      <div className="flex items-center justify-between gap-3">
                        <p>
                          <span className="font-medium">Extraction status:</span>{' '}
                          {extractionStatus === 'queued' ? 'Queued' :
                            extractionStatus === 'processing' ? 'Processing' :
                              extractionStatus === 'completed' ? 'Completed' :
                                extractionStatus === 'cancelled' ? 'Cancelled' : 'Failed'}
                        </p>
                        {(extractionStatus === 'queued' || extractionStatus === 'processing') && (
                          <button
                            type="button"
                            onClick={handleExtractionCancel}
                            className="rounded border border-indigo-300 px-2 py-1 text-xs font-medium hover:bg-indigo-100"
                          >
                            Cancel
                          </button>
                        )}
                      </div>
                      {(extractionTask.total_batches > 0 || extractionTask.total_evidence_count > 0) && (
                        <div className="mt-2 space-y-1 text-xs text-indigo-800">
                          <p>
                            Batch: {extractionTask.current_batch} / {extractionTask.total_batches || '?'}
                          </p>
                          <p>
                            Evidence processed: {extractionTask.processed_evidence_count} / {extractionTask.total_evidence_count}
                          </p>
                          <p>Products extracted: {extractionTask.extracted_product_count}</p>
                        </div>
                      )}
                      {(extractionStatus === 'failed' || extractionStatus === 'cancelled' || extractionStatus === 'error') && extractionError && (
                        <p className="mt-2 text-sm text-danger-600">{extractionError}</p>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {productResults.length > 0 && extractionStatus === 'completed' && (
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <h3 className="text-xl font-bold text-gray-900">
              Extracted Results ({productResults.length} {productResults.length === 1 ? 'Product' : 'Products'})
            </h3>
          </div>
          
          {productResults.map((product, pIndex) => (
            <div key={pIndex} className="bg-white rounded-lg shadow p-6 space-y-5 border border-gray-100">
              <div className="flex items-center justify-between">
                <h4 className="text-lg font-semibold text-primary-700">
                  {product.product_name || `Product ${pIndex + 1}`}
                </h4>
                <span className="rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-700">Validated</span>
              </div>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div>
                  <p><span className="font-medium text-gray-500">SKU / Product ID:</span> {product.sku || 'Not found in provided sources'}</p>
                  {product.sku && product.sku_evidence_chunk_id && (
                    <p className="mt-1 text-xs text-gray-500">{formatProvenance({
                      source_type: product.sku_source_type,
                      source_identifier: product.sku_source_identifier,
                      source_url: product.sku_source_url,
                      page_number: product.sku_page_number,
                      row_number: product.sku_row_number,
                    })}</p>
                  )}
                </div>
                <p><span className="font-medium text-gray-500">Brand:</span> {product.brand || 'Missing'}</p>
                <p><span className="font-medium text-gray-500">Category:</span> {product.category || 'Missing'}</p>
                <p><span className="font-medium text-gray-500">Description:</span> {product.description || 'Missing'}</p>
              </div>
              
              <div>
                <h5 className="font-medium text-gray-900 mb-2 text-sm">Extracted attributes</h5>
                {product.attributes?.length ? (
                  <div className="overflow-x-auto">
                    <table className="min-w-full text-sm">
                      <thead>
                        <tr className="border-b text-left text-gray-400 font-normal">
                          <th className="py-2 pr-4 font-normal">Attribute</th>
                          <th className="py-2 pr-4 font-normal">Value</th>
                          <th className="py-2 pr-4 font-normal">Confidence</th>
                          <th className="py-2 font-normal">Source</th>
                        </tr>
                      </thead>
                      <tbody>
                        {product.attributes.map((attribute: any, aIndex: number) => (
                          <tr key={`${attribute.attribute_name}-${aIndex}`} className="border-b last:border-0 hover:bg-gray-50">
                            <td className="py-2 pr-4 font-medium text-gray-700">{attribute.attribute_name}</td>
                            <td className="py-2 pr-4">
                              {formatAttributeValue(attribute)}
                            </td>
                            <td className="py-2 pr-4">
                              {formatConfidence(attribute)}
                            </td>
                            <td className="py-2 text-xs text-gray-500">
                              {formatProvenance(attribute)}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <p className="text-sm text-gray-500 italic">No attributes extracted.</p>
                )}
              </div>
              {product.missing_attributes?.length > 0 && (
                <div className="rounded-lg bg-amber-50 border border-amber-200 p-3 text-xs text-amber-800 space-y-1">
                  {product.missing_attributes.some((attribute: string) => attribute.toLowerCase() === 'sku') && (
                    <>
                      <p className="font-medium">Missing critical attribute: SKU / Product ID</p>
                      <p>This product source does not contain a specific product identifier.</p>
                    </>
                  )}
                  {product.missing_attributes.filter((attribute: string) => attribute.toLowerCase() !== 'sku').length > 0 && (
                    <p><span className="font-medium">Other missing attributes:</span> {product.missing_attributes.filter((attribute: string) => attribute.toLowerCase() !== 'sku').join(', ')}</p>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Information Section */}
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold text-gray-900 mb-4">Supported Sources</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <FileText className="w-5 h-5" /> PDF Files
            </h4>
            <p className="text-sm text-gray-600">
              Upload product datasheets and technical documents. Text is extracted from every page.
            </p>
          </div>
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <Globe className="w-5 h-5" /> Websites
            </h4>
            <p className="text-sm text-gray-600">
              Scrape product information from web pages. Content is cleaned and chunked for processing.
            </p>
          </div>
          <div className="space-y-2">
            <h4 className="font-medium text-gray-900 flex items-center gap-2">
              <Table className="w-5 h-5" /> CSV Files
            </h4>
            <p className="text-sm text-gray-600">
              Upload product catalogs. Each row is converted to an evidence record with preserved values.
            </p>
          </div>
        </div>
      </div>

      {/* Features Section */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="font-semibold text-blue-900 mb-2">Phase 2C Features</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>✓ Multi-source ingestion (PDF, Website, CSV)</li>
          <li>✓ Website content extraction with BeautifulSoup</li>
          <li>✓ CSV parsing with flexible column detection</li>
          <li>✓ Evidence chunk creation for all sources</li>
          <li>✓ Row number and page number preservation</li>
          <li>✓ Error handling for invalid inputs</li>
          <li>✓ Unified job tracking and status monitoring</li>
          <li>✓ Structured product extraction with provenance</li>
          <li>✓ Missing-value handling without hallucination</li>
        </ul>
      </div>
    </div>
  );
};
