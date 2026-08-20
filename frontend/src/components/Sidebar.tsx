import React from 'react';
import { Upload, Package, AlertCircle, TrendingUp, Download, SearchCheck, BarChart3, Database, Sparkles, ListChecks } from 'lucide-react';

interface SidebarProps {
  activeTab: string;
  onTabChange: (tab: string) => void;
}

export const Sidebar: React.FC<SidebarProps> = ({ activeTab, onTabChange }) => {
  const tabs = [
    { id: 'dashboard', label: 'Dashboard', icon: TrendingUp },
    { id: 'ingestion', label: 'Ingestion', icon: Upload },
    { id: 'products', label: 'Products', icon: Package },
    { id: 'investigations', label: 'Product Investigations', icon: SearchCheck },
    { id: 'evaluation', label: 'Evaluation', icon: BarChart3 },
    { id: 'reference-data', label: 'Reference Data', icon: Database },
    { id: 'product-analyzer', label: 'Product Analyzer', icon: Sparkles },
    { id: 'conflicts', label: 'Conflicts', icon: AlertCircle },
    { id: 'export', label: 'Commerce Output', icon: Download },
    { id: 'catalog', label: 'Catalog Processing', icon: ListChecks },
  ];

  return (
    <aside className="w-64 bg-gray-900 text-white h-screen shadow-lg">
      <nav className="p-4 space-y-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          const isActive = activeTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onTabChange(tab.id)}
              className={`w-full flex items-center gap-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-primary-600 text-white'
                  : 'text-gray-300 hover:bg-gray-800'
              }`}
            >
              <Icon className="w-5 h-5" />
              <span>{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </aside>
  );
};
