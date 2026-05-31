import React, { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import Layout from '../components/Layout/Layout';
import { authFetch } from '../auth/authFetch';
import { useAuth } from '../auth/KeycloakProvider';
import { useVerticalConfig } from '../config/VerticalConfigProvider';

export interface CampaignData {
  campaign_name: string;
  campaign_description: string;
  hotel_name: string;
  target_audience: string;
  theme: string;
  start_date: string;
  end_date: string;
}

export interface CampaignState {
  id?: string;
  status: string;
  preview_url?: string;
  production_url?: string;
  email_subject_en?: string;
  email_body_en?: string;
  email_subject_zh?: string;
  email_body_zh?: string;
  customer_count?: number;
  customer_list?: Array<{customer_id?: string; name: string; name_en?: string; email: string; tier: string}>;
  error?: string;
  guardrailError?: GuardrailResult;
}

interface GuardrailResult {
  passed: boolean;
  layer?: {
    id: string;
    name: string;
  } | null;
  title?: string;
  reason?: string;
  guidance?: string;
  details?: Record<string, string | number | boolean | null | undefined>;
}

const THEMES: Record<string, { name: string; tag: string; color: string; desc: string; img: string }> = {
  luxury_gold: {
    name: 'Luxury Gold', tag: 'Premium Tier', color: 'bg-tertiary-fixed-dim',
    desc: 'Evoke exclusivity with deep charcoal foundations and radiant gold accents.',
    img: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCVtreuO31fX9oee5ZFebTVpl0ELBDv1IowQzkSDteHoTVchGpkQQJ1ev-h9VitW8ye1adXBS1XSOrYiFKgFV0rWKakh2unS5szPtlagjllI5DNVopEqzFrT68dtRzYktVDDa2mtvjj0i8utkuerffNrvGlGn96FJsAykJIIIHZrW-1aRNt7DqXFj-tlnpM3C9wJGlPCKqlJ7uxd_LOB3CHTJeCHqiX7jiPj5sOISdOif0gJjwKIZf7sbOhs-VdCfUb-V57ncARqm0'
  },
  festive_red: {
    name: 'Festive Red', tag: 'Seasonal', color: 'bg-red-500',
    desc: 'Warm crimson tones paired with sparkling light. Perfect for holiday launches.',
    img: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAFj3s1Lg-nB_uRfAPZ6uLDRTgkoSnw0_japaDC68mxVPALBv-ANKzjFZLoDEnsudst6sdKJJpn2G0EsbfStbWo8EIgz_GVh1wdIxCYIxQQ1bJJ_OKEnpkULU7PFeGvuI-k-f281uMxrgUmZMOwaA0Rj9U49w5Pzx3wkU5hV5QACeox5ZX-li71xYZOT06g2KLaHMuxyl0T0nydxtqSnPaOT54N-h9fcrXR3g1nfime1jI9gkQO6S-2TBD5pdpql7HFAr9jip1Bh08'
  },
  modern_black: {
    name: 'Modern Minimal', tag: 'Minimalist', color: 'bg-slate-400',
    desc: 'Architectural and crisp. Sharp midnight typography on pure white surfaces.',
    img: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBDBP4BrTyi2GcMPBop8amdkt4v-nIeZrjS6-XLaEAF-UfcGSr-QzBO4OJHx4CvAOTNYY3JrM9cA_FILjRpTxRmxpGzk0N0SVZrVQEVUlQdqrzRT_xZsUMJ92pOCle6OFvWVGVHEiG47llaaujFUvkuBDOcUAqbSYi1hHFKQEpMVL83ofmlspEPk8sUM-Of37AxWYBC6atL35ESMaaNbHoZf0WgpgZjg-L2yKE21l2ApPZsRKcyrozZpbzwKlsp8S0bbXeFtCDo80Y'
  },
  classic_emerald: {
    name: 'Classic Emerald', tag: 'Traditional', color: 'bg-emerald-500',
    desc: 'Deep emerald green with amber gold accents. Timeless prestige.',
    img: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCU4kOdI4foPxzBZPaJWeU4e6hgpb1ob2ELtVg_0vSv-_f1j9pA2_7_M-KiZHBQZQbUWmXjvVyoBbMxzdNcIOy-GFE6vxya-o-yNe6gH0LOF52hHIkxVjPcuYCg7m46wtFSLdK6YnVVC2N29HsTwPrSuxK9HoNvrzzO5TnpSVpJLK6EEAIaQ-vHFxZmzDXlZxS8Jm6YOYOWbQoA6MfbBnQHLVTec7iDytDDtxxYBVZU0LIjInSiM0UQgFxMewJLa06nErZ-0FMZyfs'
  }
};

const DEFAULT_AUDIENCES = [
  'Platinum members',
  'Diamond members',
  'Gold members',
  'High-spend customers',
  'New members',
  'All VIP customers'
];

const SIDE_NAV_MAP: Record<number, string> = {
  0: 'strategy',
  1: 'assets',
  2: 'preview',
  3: 'preview',
  4: 'launch',
  5: 'launch'
};

function statusToStep(status: string): number {
  switch (status) {
    case 'draft': return 1;
    case 'generating': return 1;
    case 'preview_ready': return 2;
    case 'email_ready': return 3;
    case 'approved': return 4;
    case 'deploying': return 4;
    case 'live': return 5;
    case 'failed': return 1;
    default: return 0;
  }
}

function getUserRoles(token: string | null): string[] {
  if (!token) return [];
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload?.realm_access?.roles || [];
  } catch { return []; }
}

export default function CampaignCreate() {
  const navigate = useNavigate();
  const { campaignId: urlCampaignId } = useParams<{ campaignId?: string }>();
  const { token } = useAuth();
  const userRoles = getUserRoles(token);
  const hasPlatinumAccess = userRoles.includes('platinum-access');
  const vcfg = useVerticalConfig();
  const [currentStep, setCurrentStep] = useState(0);
  const [initialLoading, setInitialLoading] = useState(!!urlCampaignId);
  const [campaignData, setCampaignData] = useState<CampaignData>({
    campaign_name: '',
    campaign_description: '',
    hotel_name: vcfg.properties[0] || 'Simon Casino Resort',
    target_audience: '',
    theme: 'luxury_gold',
    start_date: new Date().toISOString().split('T')[0],
    end_date: new Date(Date.now() + 7 * 86400000).toISOString().split('T')[0]
  });
  const [campaignState, setCampaignState] = useState<CampaignState>({
    status: 'draft'
  });
  const [loading, setLoading] = useState(false);
  const [agentStatus, setAgentStatus] = useState<string>('');
  const [emailLang, setEmailLang] = useState<'en' | 'zh'>('en');
  const [selectedVip, setSelectedVip] = useState<string>('');
  const [personalizationReady, setPersonalizationReady] = useState(false);
  const [progress, setProgress] = useState(0);
  const [agentEvents, setAgentEvents] = useState<Array<{agent: string; task: string; type: string; time: string}>>([]);
  const eventSourceRef = useRef<EventSource | null>(null);
  const progressTimerRef = useRef<NodeJS.Timeout | null>(null);
  const busyRef = useRef(false);

  useEffect(() => {
    if (!urlCampaignId) return;
    (async () => {
      try {
        const resp = await authFetch(`/api/campaigns/${urlCampaignId}`);
        if (!resp.ok) { navigate('/'); return; }
        const data = await resp.json();
        setCampaignData({
          campaign_name: data.campaign_name || '',
          campaign_description: data.campaign_description || '',
          hotel_name: data.hotel_name || 'Simon Casino Resort',
          target_audience: data.target_audience || '',
          theme: data.theme || 'luxury_gold',
          start_date: data.start_date || '',
          end_date: data.end_date || ''
        });
        setCampaignState({
          id: urlCampaignId,
          status: data.status || 'draft',
          preview_url: data.preview_url,
          production_url: data.production_url,
          email_subject_en: data.email_subject_en,
          email_body_en: data.email_body_en,
          email_subject_zh: data.email_subject_zh,
          email_body_zh: data.email_body_zh,
          customer_count: data.customer_count,
          customer_list: data.customer_list,
          error: data.error_message
        });
        const step = statusToStep(data.status);
        setCurrentStep(step);

        if (data.status === 'generating' || data.status === 'preparing_email' || data.status === 'deploying') {
          setLoading(true);
          setAgentStatus('Resuming - agents are still working...');
          startSSE(urlCampaignId);
          startProgressSimulation();
          const targetStatuses = data.status === 'generating' ? ['preview_ready'] :
                                 data.status === 'preparing_email' ? ['email_ready'] : ['live'];
          try {
            const result = await pollCampaignStatus(urlCampaignId, targetStatuses);
            stopProgressSimulation(100);
            stopSSE();
            setCampaignState(prev => ({ ...prev, ...result, status: result.status, error: result.error_message }));
            setCurrentStep(statusToStep(result.status));
          } catch (e) {
            stopProgressSimulation(0);
            stopSSE();
            setCampaignState(prev => ({ ...prev, error: e instanceof Error ? e.message : 'Unknown error' }));
          } finally {
            setLoading(false);
          }
        }
      } catch {
        navigate('/');
      } finally {
        setInitialLoading(false);
      }
    })();
  }, [urlCampaignId]); // eslint-disable-line react-hooks/exhaustive-deps

  const startSSE = useCallback((campaignId: string) => {
    if (eventSourceRef.current) eventSourceRef.current.close();

    const es = new EventSource(`/events/${campaignId}`);
    eventSourceRef.current = es;

    es.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.event_type === 'connected') return;

        setAgentEvents(prev => [...prev.slice(-10), {
          agent: data.agent || 'System',
          task: data.task || data.event_type,
          type: data.event_type,
          time: new Date().toLocaleTimeString()
        }]);

        if (data.event_type === 'agent_started') {
          setAgentStatus(`${data.agent}: ${data.task}...`);
        } else if (data.event_type === 'agent_completed') {
          setAgentStatus(`${data.agent}: ${data.task}`);
          setProgress(prev => Math.min(prev + 25, 95));
        } else if (data.event_type === 'workflow_status') {
          setAgentStatus(`${data.agent}: ${data.task}...`);
          setProgress(prev => Math.min(prev + 10, 90));
        }
      } catch (e) {}
    };

    es.onerror = () => {};
  }, []);

  const stopSSE = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
    }
  }, []);

  const startProgressSimulation = useCallback(() => {
    setProgress(5);
    if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    progressTimerRef.current = setInterval(() => {
      setProgress(prev => {
        if (prev >= 90) return prev;
        return prev + (90 - prev) * 0.03;
      });
    }, 1000);
  }, []);

  const stopProgressSimulation = useCallback((final_pct: number) => {
    if (progressTimerRef.current) {
      clearInterval(progressTimerRef.current);
      progressTimerRef.current = null;
    }
    setProgress(final_pct);
  }, []);

  useEffect(() => {
    return () => {
      stopSSE();
      if (progressTimerRef.current) clearInterval(progressTimerRef.current);
    };
  }, [stopSSE]);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'smooth' });
  }, [currentStep]);

  const handleDataChange = (data: Partial<CampaignData>) => {
    setCampaignData(prev => ({ ...prev, ...data }));
    setCampaignState(prev => ({ ...prev, error: undefined, guardrailError: undefined }));
  };

  const totalSteps = 4;
  const displayStep = Math.min(currentStep, 3);
  const stepProgress = ((displayStep + 1) / totalSteps) * 100;

  const pollCampaignStatus = async (campaignId: string, targetStatuses: string[]): Promise<any> => {
    const maxAttempts = 120;
    for (let i = 0; i < maxAttempts; i++) {
      await new Promise(r => setTimeout(r, 3000));
      try {
        const resp = await authFetch(`/api/campaigns/${campaignId}`);
        if (!resp.ok) continue;
        const data = await resp.json();
        if (targetStatuses.includes(data.status)) return data;
        if (data.status === 'failed') {
          throw new Error(data.error_message || 'Workflow failed');
        }
      } catch (err) {
        if (err instanceof Error && err.message.includes('failed')) throw err;
      }
    }
    throw new Error('Operation timed out');
  };

  const createCampaign = async () => {
    setLoading(true);
    setAgentStatus('Campaign Director: Initializing campaign...');
    try {
      const response = await authFetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(campaignData)
      });
      if (!response.ok) throw new Error('Failed to create campaign');
      const result = await response.json();
      setCampaignState(prev => ({ ...prev, id: result.campaign_id, status: 'draft' }));
      return result.campaign_id;
    } catch (err) {
      setCampaignState(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Unknown error' }));
      throw err;
    } finally {
      setLoading(false);
      setAgentStatus('');
    }
  };

  const generateLandingPage = async (campaignId: string) => {
    setLoading(true);
    setProgress(0);
    setAgentEvents([]);
    setAgentStatus('Creative Producer: Generating landing page...');
    startSSE(campaignId);
    startProgressSimulation();
    await new Promise(r => setTimeout(r, 1500));
    try {
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        response = await authFetch(`/api/campaigns/${campaignId}/generate`, { method: 'POST' });
        if (response.ok || response.status < 500) break;
        await new Promise(r => setTimeout(r, 2000));
      }
      if (!response?.ok) {
        const errBody = await response?.json().catch(() => ({})) || {};
        throw new Error(errBody.error || 'Failed to start generation');
      }

      const result = await pollCampaignStatus(campaignId, ['preview_ready']);
      stopProgressSimulation(100);
      stopSSE();
      setCampaignState(prev => ({
        ...prev,
        status: result.status,
        preview_url: result.preview_url,
        error: result.error_message
      }));
      if (result.status === 'preview_ready') setCurrentStep(2);
    } catch (err) {
      stopProgressSimulation(0);
      stopSSE();
      setCampaignState(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Unknown error' }));
    } finally {
      setLoading(false);
    }
  };

  const prepareEmailPreview = async () => {
    if (!campaignState.id) return;
    setLoading(true);
    setProgress(0);
    setAgentEvents([]);
    setAgentStatus('Customer Analyst: Retrieving customers...');
    startSSE(campaignState.id);
    startProgressSimulation();
    await new Promise(r => setTimeout(r, 1500));
    try {
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        response = await authFetch(`/api/campaigns/${campaignState.id}/preview-email`, { method: 'POST' });
        if (response.ok || response.status < 500) break;
        await new Promise(r => setTimeout(r, 2000));
      }
      if (!response?.ok) {
        const errBody = await response?.json().catch(() => ({})) || {};
        throw new Error(errBody.error || 'Failed to start email preview');
      }

      const result = await pollCampaignStatus(campaignState.id, ['email_ready']);
      stopProgressSimulation(100);
      stopSSE();
      setCampaignState(prev => ({
        ...prev,
        status: result.status,
        customer_count: result.customer_count,
        customer_list: result.customer_list,
        email_subject_en: result.email_subject_en,
        email_body_en: result.email_body_en,
        email_subject_zh: result.email_subject_zh,
        email_body_zh: result.email_body_zh,
        error: result.error_message
      }));
      if (result.status === 'email_ready') {
        setCurrentStep(3);
        setPersonalizationReady(true);
        // Auto-select first customer for consistent personalization
        if (result.customer_list && result.customer_list.length > 0 && result.customer_list[0].customer_id) {
          setSelectedVip(result.customer_list[0].customer_id);
        }
      }
    } catch (err) {
      stopProgressSimulation(0);
      stopSSE();
      setCampaignState(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Unknown error' }));
    } finally {
      setLoading(false);
    }
  };

  const goLive = async () => {
    if (!campaignState.id) return;
    setLoading(true);
    setProgress(0);
    setAgentEvents([]);
    setAgentStatus('Delivery Manager: Deploying to production...');
    startSSE(campaignState.id);
    startProgressSimulation();
    await new Promise(r => setTimeout(r, 1500));
    try {
      let response: Response | undefined;
      for (let attempt = 0; attempt < 3; attempt++) {
        response = await authFetch(`/api/campaigns/${campaignState.id}/approve`, { method: 'POST' });
        if (response.ok || response.status < 500) break;
        await new Promise(r => setTimeout(r, 2000));
      }
      if (!response?.ok) {
        const errBody = await response?.json().catch(() => ({})) || {};
        throw new Error(errBody.error || 'Failed to start deployment');
      }

      const result = await pollCampaignStatus(campaignState.id, ['live']);
      stopProgressSimulation(100);
      stopSSE();
      setCampaignState(prev => ({
        ...prev,
        status: result.status,
        production_url: result.production_url,
        error: result.error_message
      }));
      if (result.status === 'live') setCurrentStep(5);
    } catch (err) {
      stopProgressSimulation(0);
      stopSSE();
      setCampaignState(prev => ({ ...prev, error: err instanceof Error ? err.message : 'Unknown error' }));
    } finally {
      setLoading(false);
    }
  };

  const handleNext = async () => {
    if (busyRef.current) return;
    window.scrollTo({ top: 0, behavior: 'smooth' });
    if (currentStep === 0) {
      setCampaignState(prev => ({ ...prev, error: undefined, guardrailError: undefined }));

      // Role-based audience restriction (instant, no API call)
      if (!hasPlatinumAccess && /platinum/i.test(campaignData.target_audience)) {
        setCampaignState(prev => ({
          ...prev,
          error: 'Access restriction',
          guardrailError: {
            passed: false,
            layer: { id: 'role_restriction', name: 'Role Restriction' },
            title: 'Access Restriction',
            reason: 'Your role does not permit targeting Platinum-tier members.',
            guidance: 'Select a different target audience (e.g., Gold members, all VIP customers) or contact your administrator for elevated access.',
          }
        }));
        return;
      }

      // Validate through guardrails before proceeding
      setLoading(true);
      setAgentStatus('Validating campaign through safety checks...');
      try {
        const validateResp = await authFetch('/api/campaigns/validate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(campaignData)
        });
        const validateResult = await validateResp.json();
        if (validateResult.valid === false) {
          setCampaignState(prev => ({
            ...prev,
            error: validateResult.reason,
            guardrailError: validateResult.guardrail
          }));
          setLoading(false);
          setAgentStatus('');
          window.scrollTo({ top: 0, behavior: 'smooth' });
          return;
        }
      } catch {
        // Validation service unavailable — proceed anyway
      }
      setLoading(false);
      setAgentStatus('');
      setCurrentStep(1);
    } else if (currentStep === 1) {
      busyRef.current = true;
      try {
        const id = campaignState.id || await createCampaign();
        await generateLandingPage(id);
      } catch (err) {
        console.error('Error:', err);
      } finally {
        busyRef.current = false;
      }
    } else if (currentStep === 2) {
      busyRef.current = true;
      try { await prepareEmailPreview(); } finally { busyRef.current = false; }
    } else if (currentStep === 3) {
      setCurrentStep(4);
    } else if (currentStep === 4) {
      busyRef.current = true;
      try { await goLive(); } finally { busyRef.current = false; }
    }
  };

  const handleBack = () => {
    if (currentStep > 0) setCurrentStep(currentStep - 1);
  };

  const isStep1Valid = !!(campaignData.campaign_name && campaignData.campaign_description && campaignData.target_audience && campaignData.start_date && campaignData.end_date);

  // ── Step 1: Strategy (Campaign Details + Venue) ──
  const renderStep1 = () => (
    <>
      <header className="mb-12 flex flex-col md:flex-row md:items-end justify-between gap-6">
        <div>
          <span className="inline-flex items-center px-3 py-1 rounded-[0.75rem] bg-primary text-on-primary text-[0.6875rem] uppercase tracking-[0.05em] font-bold mb-4">Step 1 of 4</span>
          <h1 className="text-[3.5rem] leading-tight font-headline font-extrabold text-on-surface -ml-1">Define Campaign Identity</h1>
          <p className="text-on-surface-variant max-w-2xl mt-4 leading-relaxed font-body">Define the foundational details for your upcoming luxury initiative. Our AI agents will use these parameters to generate themes and assets.</p>
        </div>
        <ProgressBar progress={stepProgress} />
      </header>

      <div className="grid grid-cols-12 gap-10 items-start">
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-12">
          {/* Quick Start Preset */}
          <section className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/20">
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant whitespace-nowrap">
                <span className="material-symbols-outlined text-sm text-tertiary-fixed-dim">auto_awesome</span>
                Quick Start
              </div>
              <select
                className="flex-grow bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary py-2.5 px-4 text-sm font-medium transition-all"
                defaultValue=""
                onChange={(e) => {
                  const idx = parseInt(e.target.value);
                  const allPresets = [...vcfg.quick_start_presets, ...vcfg.guardrail_presets];
                  const p = allPresets[idx];
                  if (p) {
                    handleDataChange({ campaign_name: p.name, campaign_description: p.desc, target_audience: p.audience, hotel_name: p.property || vcfg.properties[0] || '' });
                  }
                  e.target.value = '';
                }}
              >
                <option value="">Select a template to auto-fill...</option>
                {vcfg.quick_start_presets.length > 0 && (
                  <optgroup label="Campaign Templates">
                    {vcfg.quick_start_presets.map((p, i) => (
                      <option key={`qs-${i}`} value={i}>{p.name} — {p.audience}</option>
                    ))}
                  </optgroup>
                )}
                {vcfg.guardrail_presets.length > 0 && (
                  <optgroup label="Guardrails Tests (should be rejected)">
                    {vcfg.guardrail_presets.map((p, i) => (
                      <option key={`gr-${i}`} value={vcfg.quick_start_presets.length + i}>⛔ {p.name}</option>
                    ))}
                  </optgroup>
                )}
              </select>
            </div>
          </section>

          {/* Campaign Details Card */}
          <section className="bg-surface-container-lowest p-10 rounded-xl shadow-[0_24px_48px_-12px_rgba(0,0,0,0.04)]">
            <h3 className="text-lg font-headline font-bold mb-8 flex items-center gap-3">
              <span className="material-symbols-outlined text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>edit_note</span>
              Campaign Details
            </h3>
            <div className="space-y-10">
              <div>
                <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Campaign Name</label>
                <input
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 py-4 px-4 font-headline text-2xl placeholder:text-slate-400 font-bold"
                  placeholder="e.g., Q4 Luxury Retreat"
                  type="text"
                  value={campaignData.campaign_name}
                  onChange={(e) => handleDataChange({ campaign_name: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-surface-variant mb-3">Strategic Description</label>
                <textarea
                  className="w-full bg-slate-50 border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all duration-300 py-4 px-4 font-body text-lg placeholder:text-slate-400 min-h-[160px]"
                  placeholder="e.g., A high-end getaway for top-tier members seeking exclusive experiences..."
                  rows={6}
                  value={campaignData.campaign_description}
                  onChange={(e) => handleDataChange({ campaign_description: e.target.value })}
                />
              </div>
            </div>
          </section>

          {/* Venue & Logistics Card */}
          <section className="bg-surface-container-low p-10 rounded-xl">
            <h3 className="text-lg font-headline font-bold mb-8 flex items-center gap-3">
              <span className="material-symbols-outlined text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>location_on</span>
              {vcfg.property_label} & Logistics
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-10">
              <div className="md:col-span-2">
                <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-surface-variant mb-2">{vcfg.property_label}</label>
                <select
                  className="w-full bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary py-3 px-4 font-medium transition-all"
                  value={campaignData.hotel_name}
                  onChange={(e) => handleDataChange({ hotel_name: e.target.value })}
                >
                  {vcfg.properties.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-surface-variant mb-2">Start Date</label>
                <input
                  className="w-full bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary py-3 px-4 font-medium transition-all"
                  type="date"
                  value={campaignData.start_date}
                  onChange={(e) => handleDataChange({ start_date: e.target.value })}
                />
              </div>
              <div>
                <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-surface-variant mb-2">End Date</label>
                <input
                  className="w-full bg-white border border-slate-200 rounded-lg focus:ring-2 focus:ring-primary/20 focus:border-primary py-3 px-4 font-medium transition-all"
                  type="date"
                  value={campaignData.end_date}
                  onChange={(e) => handleDataChange({ end_date: e.target.value })}
                />
              </div>
            </div>
          </section>

          {/* Navigation */}
          <div className="flex items-center justify-between pt-6">
            <button onClick={() => navigate('/')} className="px-8 py-4 text-sm font-bold text-on-surface-variant hover:text-on-surface transition-colors flex items-center gap-2">
              <span className="material-symbols-outlined text-base">arrow_back</span>Save Draft
            </button>
            <button
              onClick={handleNext}
              disabled={!isStep1Valid}
              className="bg-primary text-on-primary px-10 py-5 rounded-xl font-headline font-bold flex items-center gap-4 hover:opacity-90 transition-all active:scale-95 shadow-xl shadow-primary/10 disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next: Select Theme <span className="material-symbols-outlined">arrow_forward</span>
            </button>
          </div>
        </div>

        {/* Right Sidebar - Target Audience */}
        <div className="col-span-12 lg:col-span-4 flex flex-col gap-8">
          <section className="bg-primary-container text-on-primary-container p-8 rounded-xl relative overflow-hidden">
            <div className="relative z-10">
              <label className="block text-[0.6875rem] font-bold uppercase tracking-widest text-on-primary-container/60 mb-4">Target Audience</label>
              <div className="space-y-3 mb-6">
                {(vcfg.audience_suggestions.length > 0 ? vcfg.audience_suggestions : DEFAULT_AUDIENCES).map((audience) => (
                  <button
                    key={audience}
                    onClick={() => handleDataChange({ target_audience: audience })}
                    className={`w-full text-left flex items-center gap-4 text-sm p-4 rounded-lg backdrop-blur-sm transition-all ${
                      campaignData.target_audience === audience
                        ? 'bg-white/20 text-white font-semibold ring-1 ring-white/30'
                        : 'bg-white/5 text-white/80 hover:bg-white/10'
                    }`}
                  >
                    <span className="material-symbols-outlined text-tertiary-fixed-dim text-[20px]">
                      {campaignData.target_audience === audience ? 'check_circle' : 'radio_button_unchecked'}
                    </span>
                    {audience}
                  </button>
                ))}
              </div>
              {campaignData.target_audience && (
                <div className="flex items-center gap-4 text-sm bg-white/5 p-4 rounded-lg backdrop-blur-sm text-white">
                  <span className="material-symbols-outlined text-tertiary-fixed-dim">groups</span>
                  <span>Selected: {campaignData.target_audience}</span>
                </div>
              )}
            </div>
            <div className="absolute -right-10 -bottom-10 w-40 h-40 bg-tertiary-fixed-dim/10 rounded-full blur-3xl"></div>
          </section>
        </div>
      </div>
    </>
  );

  // ── Step 2: Assets (Theme Selection) ──
  const renderStep2 = () => (
    <>
      <div className="mb-12">
        <div className="flex items-center justify-between mb-4">
          <span className="text-[0.6875rem] text-tertiary-fixed-dim font-bold uppercase tracking-widest">Step 2 of 4</span>
          <span className="text-[0.6875rem] text-on-surface-variant font-medium">Visual Identity Definition</span>
        </div>
        <StepProgressBar step={1} totalSteps={4} />
      </div>

      <div className="mb-16">
        <h1 className="font-headline text-5xl font-extrabold text-on-surface tracking-tight mb-4">Select Your Campaign Theme.</h1>
        <p className="text-on-surface-variant text-lg max-w-2xl leading-relaxed">Choose a visual identity that resonates with your target audience. Our AI will adapt all generated assets to match this aesthetic perfectly.</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8 mb-16">
        {Object.entries(THEMES).map(([key, theme]) => {
          const isActive = campaignData.theme === key;
          return (
            <div
              key={key}
              onClick={() => handleDataChange({ theme: key })}
              className={`group relative overflow-hidden rounded-xl h-[480px] cursor-pointer ring-2 transition-all duration-500 ${isActive ? 'ring-primary' : 'ring-transparent hover:ring-tertiary-fixed-dim'} bg-surface-container-lowest`}
            >
              <div className="absolute inset-0 bg-slate-950">
                <img alt={theme.name} className="w-full h-full object-cover mix-blend-overlay opacity-60 transition-transform duration-700 group-hover:scale-110" src={theme.img} />
              </div>
              <div className="theme-card-overlay absolute inset-0 flex flex-col justify-end p-8">
                <div className="flex items-center gap-2 mb-2">
                  <span className={`w-3 h-3 rounded-full ${theme.color}`}></span>
                  <span className="text-white/60 text-[10px] uppercase tracking-widest font-bold">{theme.tag}</span>
                </div>
                <h3 className="font-headline text-2xl text-white font-bold mb-2">{theme.name}</h3>
                <p className={`text-white/70 text-sm leading-relaxed mb-6 transition-opacity duration-300 ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'}`}>{theme.desc}</p>
                <div className={`h-1 transition-all duration-500 ${isActive ? 'w-full bg-white' : 'w-0 bg-tertiary-fixed-dim group-hover:w-full'}`}></div>
              </div>
              <div className={`absolute top-4 right-4 p-2 rounded-full shadow-lg transition-opacity duration-300 ${isActive ? 'bg-white text-primary opacity-100' : 'bg-tertiary-fixed-dim text-on-tertiary-fixed opacity-0 group-hover:opacity-100'}`}>
                <span className="material-symbols-outlined" style={{fontVariationSettings: "'FILL' 1"}}>{isActive ? 'check_circle' : 'check'}</span>
              </div>
            </div>
          );
        })}
      </div>

      <div className="flex items-center justify-between border-t border-slate-200 pt-12">
        <button onClick={handleBack} className="flex items-center gap-2 px-8 py-4 text-on-surface-variant font-bold hover:text-primary transition-colors">
          <span className="material-symbols-outlined">arrow_back</span>Back
        </button>
        <div className="flex items-center gap-6">
          {loading && <p className="text-on-surface-variant text-sm font-medium">{agentStatus || 'Processing...'}</p>}
          <button
            onClick={handleNext}
            disabled={loading}
            className="bg-primary text-on-primary px-10 py-4 rounded-xl font-headline font-bold text-lg hover:bg-slate-800 transition-all scale-[1.02] hover:scale-105 active:scale-[0.98] shadow-xl flex items-center gap-3 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                Generating...
              </>
            ) : (
              <>Next: Generate Assets <span className="material-symbols-outlined">auto_awesome</span></>
            )}
          </button>
        </div>
      </div>

      {/* Agent Activity Floating Card */}
      {agentStatus && (
        <div className="fixed bottom-8 right-8 bg-white/90 backdrop-blur shadow-2xl rounded-[0.75rem] px-6 py-3 flex items-center gap-4 z-50 border border-outline-variant/30">
          <div className="flex -space-x-2">
            <div className="w-8 h-8 rounded-full border-2 border-surface bg-tertiary-fixed-dim flex items-center justify-center text-[10px] font-bold">AI</div>
          </div>
          <div className="text-xs">
            <p className="font-bold text-on-surface">Agent Processing</p>
            <p className="text-on-surface-variant opacity-60">{agentStatus}</p>
          </div>
        </div>
      )}
    </>
  );

  // ── Step 3: Preview (Landing Page + Email) ──
  const renderStep3 = () => (
    <>
      <div className="flex justify-between items-end mb-10">
        <div>
          <h1 className="text-4xl font-headline font-extrabold text-on-surface tracking-tight mb-2">Review Your Campaign Assets</h1>
          <p className="text-on-surface-variant max-w-2xl">Finalize the high-fidelity outputs generated by your creative agents. Review the {THEMES[campaignData.theme]?.name || 'campaign'} experience across channels.</p>
        </div>
        <div className="flex gap-4">
          <button onClick={handleBack} className="px-6 py-3 rounded-xl font-semibold text-on-surface-variant hover:bg-surface-container-high transition-all flex items-center gap-2">
            <span className="material-symbols-outlined">arrow_back</span>Back to Edits
          </button>
          {currentStep === 2 && !loading && (
            <button
              onClick={async () => {
                if (!campaignState.id || busyRef.current) return;
                busyRef.current = true;
                try { await generateLandingPage(campaignState.id); } finally { busyRef.current = false; }
              }}
              className="px-6 py-3 rounded-xl font-semibold text-on-surface-variant border border-outline-variant/30 hover:bg-surface-container-high transition-all flex items-center gap-2"
            >
              <span className="material-symbols-outlined">refresh</span>Regenerate
            </button>
          )}
          <button
            onClick={handleNext}
            disabled={loading || (!state_has_emails && currentStep === 3)}
            className="px-8 py-3 rounded-xl bg-primary text-on-primary font-bold shadow-lg shadow-primary/10 hover:scale-[1.02] active:scale-[0.98] transition-all flex items-center gap-2 disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                {agentStatus ? 'Processing...' : 'Loading...'}
              </>
            ) : currentStep === 2 ? (
              <>Prepare Emails <span className="material-symbols-outlined">mail</span></>
            ) : (
              <>Review & Go Live <span className="material-symbols-outlined">rocket_launch</span></>
            )}
          </button>
        </div>
      </div>

      <div className="grid grid-cols-12 gap-6 items-start">
        {/* Main Content */}
        <div className="col-span-12 lg:col-span-8 flex flex-col gap-8">
          {/* Landing Page Preview */}
          <section className="bg-surface-container-lowest p-10 rounded-2xl shadow-sm border border-outline-variant/20">
            <div className="flex flex-col items-center text-center gap-8 py-6">
              {state.preview_url && !state.preview_url.startsWith('local://') ? (
                <>
                  <div className="p-4 bg-primary-container rounded-full shadow-2xl shadow-primary/20">
                    <span className="material-symbols-outlined text-[48px] text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>verified</span>
                  </div>
                  <div>
                    <h3 className="font-headline font-extrabold text-2xl mb-4">Landing Page Generated</h3>
                    <p className="text-on-surface-variant max-w-md mx-auto leading-relaxed">Your campaign environment is ready. Access it via the link below.</p>
                  </div>
                  <div className="w-full max-w-xl space-y-6">
                    {/* VIP Personalization Dropdown */}
                    {(campaignState.customer_list || []).length > 0 && (
                      <div className="bg-primary-container/10 border border-primary/20 rounded-xl p-4 space-y-3">
                        <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                          <span className="material-symbols-outlined text-sm text-tertiary-fixed-dim">person_search</span>
                          Preview Personalized Experience
                          {!personalizationReady && (
                            <span className="ml-2 flex items-center gap-1 text-tertiary-fixed-dim">
                              <span className="animate-spin material-symbols-outlined text-xs">progress_activity</span>
                              Syncing...
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-3">
                          <select
                            value={selectedVip}
                            onChange={(e) => setSelectedVip(e.target.value)}
                            disabled={!personalizationReady}
                            className={`flex-grow border rounded-lg px-4 py-2.5 text-sm font-medium focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all ${personalizationReady ? 'bg-surface-container-lowest border-outline-variant/30' : 'bg-surface-dim border-outline-variant/20 opacity-60 cursor-not-allowed'}`}
                          >
                            <option value="">Generic View (no personalization)</option>
                            {(campaignState.customer_list || []).map((customer) => (
                              <option key={customer.email} value={customer.customer_id || ''}>
                                {customer.name_en || customer.name} — {(customer.tier || '').charAt(0).toUpperCase() + (customer.tier || '').slice(1)} ({customer.email})
                              </option>
                            ))}
                          </select>
                          <button
                            onClick={() => window.open((state.preview_url || '') + (selectedVip ? `?c=${selectedVip}` : ''), '_blank')}
                            disabled={!personalizationReady && selectedVip !== ''}
                            className={`px-4 py-2.5 rounded-lg font-bold text-sm transition-all flex items-center gap-2 whitespace-nowrap ${personalizationReady || selectedVip === '' ? 'bg-primary text-on-primary hover:opacity-90' : 'bg-surface-dim text-on-surface-variant opacity-60 cursor-not-allowed'}`}
                          >
                            <span className="material-symbols-outlined text-sm">open_in_new</span>
                            Preview
                          </button>
                        </div>
                        {selectedVip && (
                          <p className="text-xs text-on-surface-variant">QR code below is personalized for the selected customer.</p>
                        )}
                      </div>
                    )}

                    <div className="flex items-center gap-3 p-4 bg-surface rounded-xl border border-outline-variant/30">
                      <span className="material-symbols-outlined text-primary">link</span>
                      <span className="font-mono text-sm flex-grow text-left truncate">{state.preview_url}</span>
                      <a href={state.preview_url} target="_blank" rel="noopener noreferrer" className="p-2 hover:bg-primary hover:text-white rounded-lg transition-all">
                        <span className="material-symbols-outlined text-sm">open_in_new</span>
                      </a>
                    </div>
                    <div className="flex flex-col items-center gap-4 pt-4">
                      <div className="p-4 bg-white rounded-2xl shadow-xl border border-outline-variant/10">
                        <img
                          alt="Campaign QR Code"
                          className="w-40 h-40"
                          src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent((state.preview_url || '') + (selectedVip ? `?c=${selectedVip}` : ''))}`}
                        />
                      </div>
                      <span className="text-[10px] font-bold uppercase tracking-widest text-on-surface-variant">Scan for Mobile Access</span>
                    </div>
                  </div>
                </>
              ) : (
                <>
                  <div className="p-4 bg-surface-container rounded-full">
                    <span className="material-symbols-outlined text-[48px] text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>verified</span>
                  </div>
                  <div>
                    <h3 className="font-headline font-extrabold text-2xl mb-4">Assets Generated Successfully</h3>
                    <p className="text-on-surface-variant max-w-md mx-auto leading-relaxed">
                      Preview not yet available. Complete the generation step first.
                    </p>
                  </div>
                </>
              )}
            </div>
          </section>

          {/* Email Preview (shown after step 3) */}
          {state_has_emails && (
            <section className="bg-surface-container-low rounded-2xl p-8 space-y-6">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className="material-symbols-outlined text-on-surface-variant">mail</span>
                  <h3 className="font-headline font-bold text-lg">Email Campaign Previews</h3>
                </div>
                <div className="flex p-1 bg-surface-container-highest rounded-lg gap-1">
                  <button
                    onClick={() => setEmailLang('en')}
                    className={`px-4 py-1.5 text-xs font-bold rounded transition-all ${emailLang === 'en' ? 'bg-surface-container-lowest shadow-sm' : 'text-on-surface-variant hover:text-on-surface'}`}
                  >
                    EN
                  </button>
                  <button
                    onClick={() => setEmailLang('zh')}
                    className={`px-4 py-1.5 text-xs font-bold rounded transition-all ${emailLang === 'zh' ? 'bg-surface-container-lowest shadow-sm' : 'text-on-surface-variant hover:text-on-surface'}`}
                  >
                    ZH
                  </button>
                </div>
              </div>
              <div className="space-y-4">
                <div className="bg-surface-container-lowest p-5 rounded-xl border border-outline-variant/10">
                  <p className="text-[10px] font-label text-on-surface-variant uppercase mb-1 tracking-wider">Subject Line</p>
                  <p className="text-base font-semibold leading-relaxed">
                    {personalizeEmail(emailLang === 'en' ? (campaignState.email_subject_en || 'Loading...') : (campaignState.email_subject_zh || 'Loading...'))}
                  </p>
                </div>
                <div className="bg-surface-container-lowest p-6 rounded-xl border border-outline-variant/10">
                  <p className="text-[10px] font-label text-on-surface-variant uppercase mb-3 tracking-wider">Email Body</p>
                  <div
                    className="text-sm text-on-surface leading-relaxed prose prose-sm max-w-none"
                    dangerouslySetInnerHTML={{ __html: personalizeEmail(emailLang === 'en' ? (campaignState.email_body_en || 'Loading...') : (campaignState.email_body_zh || 'Loading...')) }}
                  />
                </div>
              </div>
            </section>
          )}
        </div>

        {/* Right Sidebar */}
        <aside className="col-span-12 lg:col-span-4 space-y-6">
          {/* Recipient Pool */}
          {campaignState.customer_count !== undefined && campaignState.customer_count > 0 && (
            <div className="bg-surface-container-low rounded-2xl p-6 space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="font-headline font-bold text-lg">Recipient Pool</h3>
                <span className="bg-primary-container text-on-primary-container px-3 py-1 rounded-[0.75rem] text-xs font-bold">{campaignState.customer_count} Total</span>
              </div>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {(campaignState.customer_list || []).slice(0, 10).map((customer, i) => (
                  <div key={i} className={`flex items-center justify-between p-3 bg-surface-container-lowest rounded-xl border border-outline-variant/10 ${i >= 5 ? 'opacity-70' : ''}`}>
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-slate-100 flex items-center justify-center text-xs font-bold">
                        {(customer.name_en || customer.name || '?').charAt(0).toUpperCase()}
                      </div>
                      <div>
                        <p className="text-xs font-bold">{customer.name_en || customer.name}</p>
                        <p className="text-[10px] text-on-surface-variant">{customer.email}</p>
                      </div>
                    </div>
                    <span className={`text-[10px] font-bold px-2 py-0.5 rounded uppercase tracking-tighter ${
                      customer.tier === 'platinum' ? 'text-tertiary-fixed-dim bg-primary-container' :
                      customer.tier === 'diamond' ? 'text-blue-500 bg-blue-50' :
                      'text-slate-500 bg-slate-200'
                    }`}>{customer.tier}</span>
                  </div>
                ))}
                {(campaignState.customer_count || 0) > 10 && (
                  <p className="text-center text-[10px] text-on-surface-variant pt-1">+{(campaignState.customer_count || 0) - 10} more recipients</p>
                )}
              </div>
            </div>
          )}

          {/* Agent Activity */}
          <div className="bg-primary-container rounded-2xl p-6 space-y-4 shadow-xl shadow-primary-container/20">
            <h3 className="font-headline font-bold text-lg text-white flex items-center gap-2">
              <span className="material-symbols-outlined text-tertiary-fixed-dim">hub</span>Agent Activity
            </h3>
            <div className="space-y-4">
              {[
                { name: 'Creative Producer', status: campaignState.preview_url ? 'Landing page generated' : 'Waiting...', icon: 'brush', active: !!campaignState.preview_url },
                { name: 'Customer Analyst', status: campaignState.customer_count ? `${campaignState.customer_count} profiles retrieved` : 'Waiting...', icon: 'groups', active: !!campaignState.customer_count },
                { name: 'Delivery Manager', status: campaignState.email_subject_en ? 'Email content ready' : 'Waiting...', icon: 'translate', active: !!campaignState.email_subject_en }
              ].map((act, i) => (
                <div key={i} className="flex gap-3 relative">
                  {i < 2 && <div className="w-[1px] bg-white/10 rounded-full h-full absolute left-3 top-6"></div>}
                  <div className={`w-6 h-6 rounded-full flex items-center justify-center z-10 ${act.active ? 'bg-tertiary-fixed-dim text-on-tertiary-fixed' : 'bg-slate-700 text-slate-400'}`}>
                    <span className="material-symbols-outlined text-xs">{act.icon}</span>
                  </div>
                  <div className="space-y-1">
                    <p className={`text-xs font-bold ${act.active ? 'text-white' : 'text-slate-300'}`}>{act.name}</p>
                    <p className={`text-[11px] ${act.active ? 'text-slate-400' : 'text-slate-500'}`}>{act.status}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Campaign Summary */}
          <div className="bg-surface-container-low rounded-2xl p-6 space-y-3">
            <h3 className="font-headline font-bold text-base">Campaign Summary</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-on-surface-variant">Name</span><span className="font-medium text-right">{campaignData.campaign_name}</span></div>
              <div className="flex justify-between"><span className="text-on-surface-variant">Audience</span><span className="font-medium">{campaignData.target_audience}</span></div>
              <div className="flex justify-between"><span className="text-on-surface-variant">Theme</span><span className="font-medium">{THEMES[campaignData.theme]?.name}</span></div>
              <div className="flex justify-between"><span className="text-on-surface-variant">Period</span><span className="font-medium text-right">{campaignData.start_date} — {campaignData.end_date}</span></div>
              {campaignData.campaign_description && (
                <div className="pt-2 border-t border-outline-variant/20 mt-2">
                  <span className="text-on-surface-variant text-xs">Description</span>
                  <p className="font-medium text-xs leading-relaxed mt-1 text-on-surface/80">{campaignData.campaign_description}</p>
                </div>
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Fixed Go Live Button (only on step 4: confirmation) */}
      {currentStep === 4 && (
        <div className="fixed bottom-10 right-12 z-50">
          <button
            onClick={handleNext}
            disabled={loading}
            className="flex items-center gap-3 px-10 py-5 bg-primary text-on-primary rounded-[0.75rem] font-headline font-extrabold text-lg shadow-2xl hover:scale-105 active:scale-95 transition-all group disabled:opacity-50"
          >
            {loading ? (
              <>
                <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white"></div>
                Going Live...
              </>
            ) : (
              <>
                <span className="material-symbols-outlined group-hover:rotate-12 transition-transform" style={{fontVariationSettings: "'FILL' 1"}}>rocket_launch</span>
                Go Live Now
              </>
            )}
          </button>
        </div>
      )}
    </>
  );

  // ── Step 4: Launch (Success) ──
  const renderStep4Success = () => (
    <div className="max-w-6xl mx-auto">
      <section className="mb-12">
        <div className="inline-flex items-center gap-3 px-4 py-2 rounded-[0.75rem] bg-tertiary-fixed text-on-tertiary-fixed-variant mb-6">
          <span className="material-symbols-outlined text-lg" style={{fontVariationSettings: "'FILL' 1"}}>check_circle</span>
          <span className="text-xs font-bold tracking-widest uppercase">Deployment Successful</span>
        </div>
        <h1 className="text-6xl md:text-7xl font-headline font-extrabold text-on-surface tracking-tighter mb-4 leading-tight">Campaign is Live</h1>
        <p className="text-xl text-on-surface-variant font-body max-w-2xl leading-relaxed">Your global assets are deployed, verified, and active across all targeted nodes. The broadcast has been finalized.</p>
      </section>

      <div className="grid grid-cols-12 gap-8 items-start xl:gap-12">
        <div className="col-span-12 lg:col-span-7 space-y-8">
          {/* Production URLs */}
          <div className="bg-surface-container-lowest p-8 rounded-xl ring-1 ring-black/[0.03]">
            <h3 className="text-sm font-bold text-on-surface-variant uppercase tracking-widest mb-6 font-headline">Production Environments</h3>
            <div className="space-y-6">

              {campaignState.production_url && (
                <div className="flex items-center justify-between p-4 bg-surface rounded-lg">
                  <div className="flex flex-col">
                    <span className="text-[10px] uppercase font-bold text-on-surface-variant/60 mb-1">Live Campaign</span>
                    <span className="font-mono text-sm text-primary">{campaignState.production_url}</span>
                  </div>
                  <a href={campaignState.production_url} target="_blank" rel="noopener noreferrer" className="p-2 hover:bg-surface-container-high rounded transition-colors">
                    <span className="material-symbols-outlined text-on-surface-variant">open_in_new</span>
                  </a>
                </div>
              )}
            </div>
          </div>

          {/* Broadcast Stats */}
          <div className="bg-surface-container-low p-8 rounded-xl border-l-4 border-tertiary-fixed-dim">
            <div className="flex items-start gap-6">
              <div className="w-14 h-14 rounded-full bg-surface-container-lowest flex items-center justify-center text-primary shadow-sm">
                <span className="material-symbols-outlined text-3xl">forward_to_inbox</span>
              </div>
              <div>
                <h4 className="text-lg font-headline font-bold mb-1">Emails Successfully Sent</h4>
                <p className="text-on-surface-variant text-sm mb-4">All campaign emails have been delivered to your target audience.</p>
                <div className="flex items-center gap-3">
                  <span className="text-lg font-headline font-bold text-primary">Sent to {campaignState.customer_count || 0} customers</span>
                </div>
              </div>
            </div>
          </div>

          <div className="flex flex-wrap gap-4 pt-4">
            {campaignState.production_url && (
              <a
                href={campaignState.production_url}
                target="_blank"
                rel="noopener noreferrer"
                className="px-8 py-4 bg-primary text-on-primary rounded-xl font-headline font-bold text-sm flex items-center gap-3 hover:scale-[0.98] transition-transform shadow-lg shadow-primary/10"
              >
                <span className="material-symbols-outlined">open_in_new</span>View Live Page
              </a>
            )}
            <button onClick={() => navigate('/')} className="px-8 py-4 bg-secondary-container text-on-secondary-container rounded-xl font-headline font-bold text-sm flex items-center gap-3 hover:bg-secondary-container/80 transition-colors">
              <span className="material-symbols-outlined">arrow_back</span>Return to Dashboard
            </button>
          </div>
        </div>

        {/* Right side - VIP Preview + QR Code + Achievement */}
        <div className="col-span-12 lg:col-span-5 space-y-8">
          {/* VIP Personalization Dropdown */}
          {(campaignState.customer_list || []).length > 0 && campaignState.production_url && (
            <div className="bg-surface-container-lowest p-6 rounded-xl ring-1 ring-black/[0.03] space-y-3">
              <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-widest text-on-surface-variant">
                <span className="material-symbols-outlined text-sm text-tertiary-fixed-dim">person_search</span>
                Preview Personalized Experience
              </div>
              <select
                value={selectedVip}
                onChange={(e) => setSelectedVip(e.target.value)}
                className="w-full bg-surface border border-outline-variant/30 rounded-lg px-4 py-2.5 text-sm font-medium focus:ring-2 focus:ring-primary/20 focus:border-primary transition-all"
              >
                <option value="">Generic View (no personalization)</option>
                {(campaignState.customer_list || []).map((customer) => (
                  <option key={customer.email} value={customer.customer_id || ''}>
                    {customer.name_en || customer.name} — {(customer.tier || '').charAt(0).toUpperCase() + (customer.tier || '').slice(1)} ({customer.email})
                  </option>
                ))}
              </select>
              <button
                onClick={() => window.open((campaignState.production_url || '') + (selectedVip ? `?c=${selectedVip}` : ''), '_blank')}
                className="w-full px-4 py-2.5 bg-primary text-on-primary rounded-lg font-bold text-sm hover:opacity-90 transition-all flex items-center justify-center gap-2"
              >
                <span className="material-symbols-outlined text-sm">open_in_new</span>
                Open Personalized Page
              </button>
            </div>
          )}
          {campaignState.production_url && (
            <div className="bg-surface-container-lowest p-8 rounded-xl ring-1 ring-black/[0.03] flex flex-col items-center justify-center">
              <h3 className="text-sm font-bold text-on-surface-variant uppercase tracking-widest mb-6 font-headline">Campaign QR Code</h3>
              <div className="bg-white p-4 rounded-xl shadow-sm mb-4">
                <img
                  alt="Production QR Code"
                  className="w-48 h-48"
                  src={`https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(campaignState.production_url + (selectedVip ? `?c=${selectedVip}` : ''))}`}
                />
              </div>
              <p className="text-sm text-center text-on-surface-variant font-medium leading-relaxed max-w-[200px]">Scan for instant mobile access</p>
            </div>
          )}
          <div className="bg-surface-container-high p-8 rounded-xl text-center">
            <span className="text-[10px] font-bold uppercase text-on-surface-variant/60 tracking-widest block mb-4">Milestone Achieved</span>
            <div className="flex justify-center mb-4">
              <span className="material-symbols-outlined text-5xl text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>workspace_premium</span>
            </div>
            <h4 className="text-xl font-headline font-bold text-on-surface mb-2">Campaign Launch Complete</h4>
            <p className="text-sm text-on-surface-variant">This campaign was generated, reviewed, and deployed using AI-powered agents.</p>
          </div>
        </div>
      </div>

      <footer className="mt-20 pt-8 border-t border-outline-variant/20 flex justify-between items-center text-on-surface-variant">
        <div className="flex items-center gap-4">
          <span className="text-[10px] font-bold uppercase tracking-widest">System Log</span>
          <span className="text-xs font-mono">Campaign ID: {campaignState.id || 'N/A'}</span>
        </div>
        <div className="flex items-center gap-2 text-xs">
          <span className="w-1.5 h-1.5 rounded-full bg-green-500"></span>Operational Efficiency: 100%
        </div>
      </footer>
    </div>
  );

  const state = campaignState;
  const state_has_emails = !!(state.email_subject_en || state.email_subject_zh);
  const personalizeEmail = (text: string) => {
    if (!text || !selectedVip) return text;
    const customer = (campaignState.customer_list || []).find(c => c.customer_id === selectedVip);
    if (!customer) return text;
    const name = customer.name_en || customer.name || 'Valued Guest';
    const link = (campaignState.preview_url || campaignState.production_url || '') + '?c=' + selectedVip;
    return text
      .replace(/\{\{customer_name\}\}/gi, name)
      .replace(/\{\{campaign_link\}\}/gi, link);
  };



  const activeNav = SIDE_NAV_MAP[currentStep] || 'strategy';

  const guardrailSummary = campaignState.guardrailError;

  const renderStatusBanner = () => (
    <>
      {guardrailSummary && (
        <div className="mb-8 rounded-2xl border border-error/20 bg-error-container p-6 shadow-sm">
          <div className="flex items-start gap-4">
            <div className="mt-0.5 flex h-11 w-11 items-center justify-center rounded-2xl bg-error text-on-error shadow-sm">
              <span className="material-symbols-outlined">shield_locked</span>
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-3">
                <p className="text-sm font-bold uppercase tracking-widest text-error">Campaign blocked</p>
                {guardrailSummary.layer?.name && (
                  <span className="rounded-full bg-white/80 px-3 py-1 text-[11px] font-bold uppercase tracking-wider text-on-error-container">
                    {guardrailSummary.layer.name}
                  </span>
                )}
              </div>
              <h3 className="mt-3 text-lg font-headline font-bold text-on-error-container">
                {guardrailSummary.title || 'Guardrail rejection'}
              </h3>
              <p className="mt-2 text-sm font-medium leading-relaxed text-on-error-container">
                {guardrailSummary.reason || campaignState.error}
              </p>
              {guardrailSummary.guidance && (
                <p className="mt-3 rounded-xl bg-white/60 px-4 py-3 text-sm text-on-error-container">
                  <span className="font-bold">How to fix:</span> {guardrailSummary.guidance}
                </p>
              )}

            </div>
            <button onClick={() => setCampaignState(prev => ({ ...prev, error: undefined, guardrailError: undefined }))} className="text-on-error-container/60 hover:text-on-error-container">
              <span className="material-symbols-outlined text-sm">close</span>
            </button>
          </div>
        </div>
      )}

      {campaignState.error && !guardrailSummary && (
        <div className="mb-8 p-4 bg-error-container border border-error/20 rounded-xl flex items-center gap-3">
          <span className="material-symbols-outlined text-error">error</span>
          <span className="text-on-error-container text-sm font-medium">{campaignState.error}</span>
          <button onClick={() => setCampaignState(prev => ({ ...prev, error: undefined }))} className="ml-auto text-on-error-container/60 hover:text-on-error-container">
            <span className="material-symbols-outlined text-sm">close</span>
          </button>
        </div>
      )}

      {loading && (
        <div className="mb-8 bg-primary-container rounded-2xl p-6 shadow-xl shadow-primary-container/20 overflow-hidden">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              <div className="w-8 h-8 rounded-full bg-tertiary-fixed-dim flex items-center justify-center">
                <span className="material-symbols-outlined text-on-tertiary-fixed text-sm animate-spin">progress_activity</span>
              </div>
              <div>
                <p className="text-white font-headline font-bold text-sm">{agentStatus || 'Processing...'}</p>
                <p className="text-white/50 text-xs">{Math.round(progress)}% complete</p>
              </div>
            </div>
            <span className="text-tertiary-fixed-dim text-[10px] font-bold uppercase tracking-widest">AI Agents Working</span>
          </div>

          {/* Progress Bar */}
          <div className="w-full h-2 bg-white/10 rounded-full overflow-hidden mb-4">
            <div
              className="h-full bg-gradient-to-r from-tertiary-fixed-dim to-white rounded-full transition-all duration-1000 ease-out"
              style={{ width: `${progress}%` }}
            />
          </div>

          {/* Agent Event Log */}
          {agentEvents.length > 0 && (
            <div className="space-y-2 max-h-32 overflow-y-auto">
              {agentEvents.map((evt, i) => (
                <div key={i} className="flex items-center gap-2 text-xs">
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    evt.type === 'agent_completed' ? 'bg-emerald-400' :
                    evt.type === 'agent_error' ? 'bg-red-400' :
                    'bg-tertiary-fixed-dim animate-pulse'
                  }`} />
                  <span className="text-white/70 font-mono">{evt.time}</span>
                  <span className="text-white/90 font-medium">{evt.agent}:</span>
                  <span className="text-white/60">{evt.task}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  );

  if (initialLoading) {
    return (
      <Layout activeStep="strategy">
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="text-on-surface-variant text-sm">Loading campaign...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout activeStep={activeNav} campaignName={campaignData.campaign_name || undefined}>
      {renderStatusBanner()}
      {currentStep === 0 && renderStep1()}
      {currentStep === 1 && renderStep2()}
      {(currentStep === 2 || currentStep === 3 || currentStep === 4) && renderStep3()}
      {currentStep === 5 && renderStep4Success()}
    </Layout>
  );
}

// ── Shared UI Components ──

function ProgressBar({ progress }: { progress: number }) {
  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex gap-1 h-1 w-48 bg-surface-dim overflow-hidden rounded-[0.75rem]">
        <div className="h-full bg-primary transition-all duration-500" style={{ width: `${progress}%` }}></div>
      </div>
      <span className="text-[0.6875rem] font-bold text-on-surface-variant uppercase tracking-widest">Setup Progress</span>
    </div>
  );
}

function StepProgressBar({ step, totalSteps }: { step: number; totalSteps: number }) {
  return (
    <div className="flex h-1 gap-2">
      {Array.from({ length: totalSteps }).map((_, i) => (
        <div key={i} className={`flex-1 rounded-[0.75rem] relative ${i <= step ? 'bg-tertiary-fixed-dim' : 'bg-surface-dim'}`}>
          {i === step && (
            <div className="absolute -top-1 -right-1 w-3 h-3 bg-tertiary-fixed-dim rounded-full ring-4 ring-surface"></div>
          )}
        </div>
      ))}
    </div>
  );
}
