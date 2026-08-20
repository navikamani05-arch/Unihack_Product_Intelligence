import React from 'react';
import { Package } from 'lucide-react';

export const Header: React.FC = () => {
  return (
    <header className="bg-gradient-to-r from-primary-600 to-primary-700 text-white shadow-lg">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex items-center gap-3">
          <Package className="w-8 h-8" />
          <div>
            <h1 className="text-3xl font-bold">AI Product Intelligence</h1>
            <p className="text-primary-100 text-sm">Industrial Commerce Trust Engine</p>
          </div>
        </div>
      </div>
    </header>
  );
};
