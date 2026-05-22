import React from 'react';
import { CampaignData, CampaignState } from '../../pages/CampaignCreate';

interface PreviewPanelProps {
  step: string;
  data: CampaignData;
  state: CampaignState;
}

const THEMES: Record<string, { name: string; color: string }> = {
  luxury_gold: { name: 'Luxury Gold', color: '#D4AF37' },
  festive_red: { name: 'Festive Red', color: '#C41E3A' },
  modern_black: { name: 'Modern Black', color: '#1a1a1a' },
  classic_emerald: { name: 'Classic Emerald', color: '#228B22' }
};

export default function PreviewPanel({ step, data, state }: PreviewPanelProps) {
  const theme = THEMES[data.theme] || THEMES.luxury_gold;

  return (
    <div className="bg-white rounded-lg shadow-md p-6 sticky top-6">
      <h3 className="text-lg font-semibold text-gray-900 mb-4">Campaign Summary</h3>

      <div className="space-y-4">
        <div>
          <p className="text-sm text-gray-500">Campaign Name</p>
          <p className="font-medium text-gray-900">{data.campaign_name || '—'}</p>
        </div>

        <div>
          <p className="text-sm text-gray-500">Target Audience</p>
          <p className="font-medium text-gray-900">{data.target_audience || '—'}</p>
        </div>

        <div>
          <p className="text-sm text-gray-500">Campaign Period</p>
          <p className="font-medium text-gray-900">
            {data.start_date && data.end_date
              ? `${data.start_date} to ${data.end_date}`
              : '—'}
          </p>
        </div>

        <div>
          <p className="text-sm text-gray-500">Theme</p>
          <div className="flex items-center mt-1">
            <div
              className="w-4 h-4 rounded-full mr-2"
              style={{ backgroundColor: theme.color }}
            />
            <span className="font-medium text-gray-900">{theme.name}</span>
          </div>
        </div>

        <hr className="border-gray-200" />

        <div>
          <p className="text-sm text-gray-500">Status</p>
          <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium mt-1 ${
            state.status === 'live'
              ? 'bg-green-100 text-green-800'
              : state.status === 'failed'
              ? 'bg-red-100 text-red-800'
              : 'bg-blue-100 text-blue-800'
          }`}>
            {state.status.replace('_', ' ')}
          </span>
        </div>

        {state.customer_count !== undefined && state.customer_count > 0 && (
          <div>
            <p className="text-sm text-gray-500">Recipients</p>
            <p className="font-medium text-gray-900">{state.customer_count} people</p>
          </div>
        )}

        {state.preview_url && (
          <div>
            <p className="text-sm text-gray-500">Preview</p>
            <a
              href={state.preview_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-blue-600 hover:text-blue-800 text-sm break-all"
            >
              View Landing Page →
            </a>
          </div>
        )}

        {state.production_url && (
          <div>
            <p className="text-sm text-gray-500">Production</p>
            <a
              href={state.production_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-green-600 hover:text-green-800 text-sm break-all"
            >
              View Live Site →
            </a>
          </div>
        )}
      </div>

      <hr className="border-gray-200 my-4" />

      <div>
        <p className="text-sm text-gray-500 mb-2">Agent Activity</p>
        <div className="space-y-2 text-xs">
          {step === 'details' && (
            <div className="flex items-center text-gray-500">
              <span className="w-2 h-2 rounded-full bg-gray-300 mr-2"></span>
              Waiting for campaign details...
            </div>
          )}
          {step === 'theme' && (
            <div className="flex items-center text-gray-500">
              <span className="w-2 h-2 rounded-full bg-yellow-400 mr-2"></span>
              Ready to generate landing page
            </div>
          )}
          {(step === 'landing' || step === 'email' || step === 'confirm') && (
            <>
              <div className="flex items-center text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                Creative Producer: Complete
              </div>
              {state.customer_count !== undefined && (
                <div className="flex items-center text-green-600">
                  <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                  Customer Analyst: {state.customer_count} found
                </div>
              )}
              {state.email_subject_en && (
                <div className="flex items-center text-green-600">
                  <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                  Delivery Manager: Email ready
                </div>
              )}
            </>
          )}
          {step === 'success' && (
            <>
              <div className="flex items-center text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                All agents: Complete
              </div>
              <div className="flex items-center text-green-600">
                <span className="w-2 h-2 rounded-full bg-green-500 mr-2"></span>
                Campaign is LIVE
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
