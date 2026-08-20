import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { IngestionView } from './pages/IngestionView';
import { InvestigationsView } from './pages/InvestigationsView';
import { EvaluationView } from './pages/EvaluationView';
import { ReferenceDataView } from './pages/ReferenceDataView';
import ProductAnalyzerView from './pages/ProductAnalyzerView';
import CommerceOutputView from './pages/CommerceOutputView';
import CatalogProcessingView from './pages/CatalogProcessingView';
import { api } from './services/api';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [apiStatus, setApiStatus] = useState<'connected' | 'disconnected'>('disconnected');

  useEffect(() => {
    // Check API health on mount
    const checkHealth = async () => {
      try {
        await api.health();
        setApiStatus('connected');
      } catch (error) {
        setApiStatus('disconnected');
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 30000); // Check every 30 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="flex h-screen bg-gray-50">
      <Sidebar activeTab={activeTab} onTabChange={setActiveTab} />
      <div className="flex-1 flex flex-col overflow-hidden">
        <Header />
        <div className="flex-1 overflow-auto">
          <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
            {apiStatus === 'disconnected' && (
              <div className="mb-4 bg-yellow-50 border border-yellow-200 rounded-lg p-4 text-yellow-700">
                <p className="font-semibold">Backend API is not responding</p>
                <p className="text-sm">Check the configured API endpoint and confirm the backend health check is available.</p>
              </div>
            )}

            {activeTab === 'dashboard' && <Dashboard onNavigate={setActiveTab} />}
            {activeTab === 'ingestion' && <IngestionView />}
            {activeTab === 'investigations' && <InvestigationsView />}
            {activeTab === 'evaluation' && <EvaluationView />}
            {activeTab === 'reference-data' && <ReferenceDataView />}
            {activeTab === 'product-analyzer' && <ProductAnalyzerView />}
            {activeTab === 'products' && (
              <div className="mx-auto max-w-2xl rounded-2xl border border-slate-200 bg-white p-8 text-center shadow-sm">
                <h1 className="text-2xl font-semibold text-slate-900">Product records</h1>
                <p className="mt-3 text-sm leading-6 text-slate-600">Persisted products are available in the evaluator Dashboard catalog, Product Analyzer, and Catalog Processing views so their source, evidence, status, and delivery path stay together.</p>
                <button type="button" onClick={() => setActiveTab('dashboard')} className="mt-5 rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-indigo-700">Open Dashboard catalog</button>
              </div>
            )}
            {activeTab === 'conflicts' && (
              <div className="mx-auto max-w-2xl rounded-2xl border border-amber-200 bg-amber-50 p-8 text-center shadow-sm">
                <h1 className="text-2xl font-semibold text-amber-950">Conflicts and review</h1>
                <p className="mt-3 text-sm leading-6 text-amber-900">Conflicting source-backed values are preserved and routed through Product Investigations and Product Analyzer. No conflict is silently resolved or overwritten.</p>
                <div className="mt-5 flex flex-wrap justify-center gap-3"><button type="button" onClick={() => setActiveTab('investigations')} className="rounded-lg bg-amber-700 px-4 py-2.5 text-sm font-semibold text-white hover:bg-amber-800">Open Investigations</button><button type="button" onClick={() => setActiveTab('product-analyzer')} className="rounded-lg border border-amber-300 bg-white px-4 py-2.5 text-sm font-semibold text-amber-900 hover:bg-amber-100">Open Product Analyzer</button></div>
              </div>
            )}
            {activeTab === 'export' && <CommerceOutputView />}
            {activeTab === 'catalog' && <CatalogProcessingView />}
          </main>
        </div>
      </div>
    </div>
  );
}

export default App;
