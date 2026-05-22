import React from 'react';
import { CheckCircleIcon, RocketLaunchIcon, ArrowRightIcon, ArrowLeftIcon } from '@heroicons/react/24/solid';
import { CampaignData, CampaignState } from '../../pages/CampaignCreate';

interface CampaignWizardProps {
  step: string;
  data: CampaignData;
  state: CampaignState;
  onChange: (data: Partial<CampaignData>) => void;
  onNext: () => void;
  onBack: () => void;
  loading: boolean;
}

const THEMES = {
  luxury_gold: { name: 'Luxury Gold', color: '#D4AF37', description: 'Elegant gold and champagne tones' },
  festive_red: { name: 'Festive Red', color: '#C41E3A', description: 'Vibrant red for celebrations' },
  modern_black: { name: 'Modern Black', color: '#1a1a1a', description: 'Sleek and sophisticated' },
  classic_emerald: { name: 'Classic Emerald', color: '#228B22', description: 'Deep emerald with amber gold' }
};

const AUDIENCES = [
  'Platinum members',
  'Diamond members',
  'Gold members',
  'High-spend customers',
  'New members',
  'All VIP customers'
];

export default function CampaignWizard({ step, data, state, onChange, onNext, onBack, loading }: CampaignWizardProps) {
  const renderDetailsStep = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Campaign Details</h2>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Campaign Name *</label>
        <input
          type="text"
          value={data.campaign_name}
          onChange={(e) => onChange({ campaign_name: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          placeholder="e.g., Chinese New Year VIP Celebration"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Description *</label>
        <textarea
          value={data.campaign_description}
          onChange={(e) => onChange({ campaign_description: e.target.value })}
          rows={3}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          placeholder="Describe the campaign offer and benefits..."
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Hotel/Casino Name</label>
        <input
          type="text"
          value={data.hotel_name}
          onChange={(e) => onChange({ hotel_name: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">Target Audience *</label>
        <select
          value={data.target_audience}
          onChange={(e) => onChange({ target_audience: e.target.value })}
          className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
        >
          <option value="">Select audience...</option>
          {AUDIENCES.map((audience) => (
            <option key={audience} value={audience}>{audience}</option>
          ))}
        </select>
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Start Date *</label>
          <input
            type="date"
            value={data.start_date}
            onChange={(e) => onChange({ start_date: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">End Date *</label>
          <input
            type="date"
            value={data.end_date}
            onChange={(e) => onChange({ end_date: e.target.value })}
            className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary focus:border-transparent"
          />
        </div>
      </div>

      <div className="flex justify-end">
        <button
          onClick={onNext}
          disabled={!data.campaign_name || !data.campaign_description || !data.target_audience || !data.start_date || !data.end_date}
          className="px-6 py-2 bg-primary text-secondary font-medium rounded-lg hover:bg-yellow-500 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Continue <ArrowRightIcon className="inline h-4 w-4 ml-1" />
        </button>
      </div>
    </div>
  );

  const renderThemeStep = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Select Theme</h2>
      <p className="text-gray-600">Choose a visual style for your campaign landing page</p>

      <div className="grid grid-cols-2 gap-4">
        {Object.entries(THEMES).map(([key, theme]) => (
          <button
            key={key}
            onClick={() => onChange({ theme: key })}
            className={`p-4 border-2 rounded-lg text-left transition-all ${
              data.theme === key
                ? 'border-primary bg-primary/5'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            <div
              className="w-full h-16 rounded-md mb-3"
              style={{ backgroundColor: theme.color }}
            />
            <h3 className="font-semibold text-gray-900">{theme.name}</h3>
            <p className="text-sm text-gray-500">{theme.description}</p>
          </button>
        ))}
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          <ArrowLeftIcon className="inline h-4 w-4 mr-1" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={loading}
          className="px-6 py-2 bg-primary text-secondary font-medium rounded-lg hover:bg-yellow-500 disabled:opacity-50 flex items-center"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-secondary mr-2"></div>
              Generating...
            </>
          ) : (
            <>Generate Landing Page <ArrowRightIcon className="inline h-4 w-4 ml-1" /></>
          )}
        </button>
      </div>
    </div>
  );

  const renderLandingStep = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Landing Page Preview</h2>
      <p className="text-gray-600">Review your campaign landing page</p>

      {state.preview_url ? (
        <div className="border border-gray-200 rounded-lg overflow-hidden">
          <iframe
            src={state.preview_url}
            className="w-full h-96"
            title="Landing Page Preview"
          />
        </div>
      ) : (
        <div className="h-96 bg-gray-100 rounded-lg flex items-center justify-center">
          <p className="text-gray-500">Preview not available</p>
        </div>
      )}

      {state.preview_url && (
        <a
          href={state.preview_url}
          target="_blank"
          rel="noopener noreferrer"
          className="text-blue-600 hover:text-blue-800 text-sm"
        >
          Open in new tab <ArrowRightIcon className="inline h-3 w-3 ml-1" />
        </a>
      )}

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          <ArrowLeftIcon className="inline h-4 w-4 mr-1" /> Edit Theme
        </button>
        <button
          onClick={onNext}
          disabled={loading || !state.preview_url}
          className="px-6 py-2 bg-primary text-secondary font-medium rounded-lg hover:bg-yellow-500 disabled:opacity-50 flex items-center"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-secondary mr-2"></div>
              Preparing...
            </>
          ) : (
            <>Preview Email <ArrowRightIcon className="inline h-4 w-4 ml-1" /></>
          )}
        </button>
      </div>
    </div>
  );

  const renderEmailStep = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Email Preview</h2>
      <p className="text-gray-600">Review email content and recipients before going live</p>

      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
        <p className="text-blue-800 font-medium">
          {state.customer_count || 0} recipients will receive this email
        </p>
      </div>

      <div className="space-y-4">
        <div>
          <h3 className="font-semibold text-gray-900 mb-2">English Version</h3>
          <div className="border border-gray-200 rounded-lg p-4 bg-white">
            <p className="text-sm text-gray-500 mb-1">Subject:</p>
            <p className="font-medium mb-3">{state.email_subject_en || 'Loading...'}</p>
            <p className="text-sm text-gray-500 mb-1">Body:</p>
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: state.email_body_en || 'Loading...' }}
            />
          </div>
        </div>

        <div>
          <h3 className="font-semibold text-gray-900 mb-2">Chinese Version</h3>
          <div className="border border-gray-200 rounded-lg p-4 bg-white">
            <p className="text-sm text-gray-500 mb-1">Subject:</p>
            <p className="font-medium mb-3">{state.email_subject_zh || 'Loading...'}</p>
            <p className="text-sm text-gray-500 mb-1">Body:</p>
            <div
              className="prose prose-sm max-w-none"
              dangerouslySetInnerHTML={{ __html: state.email_body_zh || 'Loading...' }}
            />
          </div>
        </div>
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          <ArrowLeftIcon className="inline h-4 w-4 mr-1" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={loading || !state.email_subject_en}
          className="px-6 py-2 bg-primary text-secondary font-medium rounded-lg hover:bg-yellow-500 disabled:opacity-50"
        >
          Continue to Confirmation <ArrowRightIcon className="inline h-4 w-4 ml-1" />
        </button>
      </div>
    </div>
  );

  const renderConfirmStep = () => (
    <div className="space-y-6">
      <h2 className="text-2xl font-bold text-gray-900">Confirmation</h2>
      <p className="text-gray-600">Review all details before going live</p>

      <div className="bg-gray-50 rounded-lg p-6 space-y-4">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <p className="text-sm text-gray-500">Campaign Name</p>
            <p className="font-medium">{data.campaign_name}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Target Audience</p>
            <p className="font-medium">{data.target_audience}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Campaign Period</p>
            <p className="font-medium">{data.start_date} to {data.end_date}</p>
          </div>
          <div>
            <p className="text-sm text-gray-500">Recipients</p>
            <p className="font-medium">{state.customer_count || 0} people</p>
          </div>
        </div>

        {state.preview_url && (
          <div>
            <p className="text-sm text-gray-500">Preview URL</p>
            <a href={state.preview_url} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:text-blue-800 text-sm">
              {state.preview_url}
            </a>
          </div>
        )}
      </div>

      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <p className="text-yellow-800 text-sm">
          <strong>Note:</strong> Going live will deploy the campaign to production and send emails to all {state.customer_count || 0} recipients (simulated).
        </p>
      </div>

      <div className="flex justify-between">
        <button
          onClick={onBack}
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          <ArrowLeftIcon className="inline h-4 w-4 mr-1" /> Back
        </button>
        <button
          onClick={onNext}
          disabled={loading}
          className="px-6 py-2 bg-accent text-white font-medium rounded-lg hover:bg-red-700 disabled:opacity-50 flex items-center"
        >
          {loading ? (
            <>
              <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
              Going Live...
            </>
          ) : (
            <><RocketLaunchIcon className="inline h-4 w-4 mr-1" /> Go Live</>
          )}
        </button>
      </div>
    </div>
  );

  const renderSuccessStep = () => (
    <div className="text-center space-y-6 py-8">
      <div className="mx-auto flex items-center justify-center h-20 w-20 rounded-full bg-green-100">
        <CheckCircleIcon className="h-12 w-12 text-green-600" />
      </div>
      <h2 className="text-3xl font-bold text-gray-900">Campaign is Live!</h2>
      <p className="text-gray-600">Your campaign has been deployed and emails have been sent.</p>

      <div className="bg-green-50 border border-green-200 rounded-lg p-6 text-left max-w-md mx-auto">
        <p className="text-green-800 font-medium mb-2">Campaign Details:</p>
        <ul className="text-green-700 text-sm space-y-1">
          <li className="flex items-center"><CheckCircleIcon className="h-4 w-4 mr-2 text-green-600" /> Landing page deployed to production</li>
          <li className="flex items-center"><CheckCircleIcon className="h-4 w-4 mr-2 text-green-600" /> {state.customer_count || 0} emails sent (simulated)</li>
        </ul>

        {state.production_url && (
          <div className="mt-4">
            <p className="text-sm text-green-600">Production URL:</p>
            <a href={state.production_url} target="_blank" rel="noopener noreferrer" className="text-green-800 font-medium hover:underline">
              {state.production_url}
            </a>
          </div>
        )}
      </div>

      <div className="flex justify-center space-x-4">
        <a
          href="/"
          className="px-6 py-2 border border-gray-300 text-gray-700 font-medium rounded-lg hover:bg-gray-50"
        >
          Back to Dashboard
        </a>
        <a
          href="/create"
          className="px-6 py-2 bg-primary text-secondary font-medium rounded-lg hover:bg-yellow-500"
        >
          Create Another Campaign
        </a>
      </div>
    </div>
  );

  switch (step) {
    case 'details':
      return renderDetailsStep();
    case 'theme':
      return renderThemeStep();
    case 'landing':
      return renderLandingStep();
    case 'email':
      return renderEmailStep();
    case 'confirm':
      return renderConfirmStep();
    case 'success':
      return renderSuccessStep();
    default:
      return renderDetailsStep();
  }
}
