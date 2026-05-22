import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import Layout from '../components/Layout/Layout';
import { authFetch } from '../auth/authFetch';
import { useVerticalConfig } from '../config/VerticalConfigProvider';

interface Campaign {
  id: string;
  campaign_name: string;
  status: string;
  target_audience: string;
  theme: string;
  hero_image_url?: string;
  hotel_name?: string;
  start_date?: string;
  end_date?: string;
  created_at: string;
  preview_url?: string;
  production_url?: string;
}

const statusConfig: Record<string, { label: string; color: string }> = {
  draft: { label: 'Draft', color: 'bg-white/90 text-slate-500' },
  generating: { label: 'Generating', color: 'bg-tertiary-fixed-dim text-tertiary' },
  preview_ready: { label: 'Preview', color: 'bg-white/90 text-primary' },
  email_ready: { label: 'Email Ready', color: 'bg-white/90 text-primary' },
  approved: { label: 'Approved', color: 'bg-white/90 text-primary' },
  live: { label: 'Live', color: 'bg-white/90 text-primary' },
  failed: { label: 'Failed', color: 'bg-error text-on-error' }
};

const themeImages: Record<string, string> = {
  luxury_gold: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBRBqHxuMQLl522QOmlGrL9x3bANbx9wDf1mdgGPlgYfTMdmn1lNaTGsGG1IvKA20BW_2j_zp-LRA1Wge2FX8W_9soCXrUg7VCv1JCXtHzkY8iSSCsCdIxX8Sn4f935tB1CpfbgQKauQbxifEmTIL2Zn-xsUtzQuIno_p-aqWpBc4ExahinyWZRRVUZgm6int4wXDKgylFtAL4rlT-zspuYtXPflVXedjMCgX0EI8kskVWElGJHxWmExupW1ffyC8APz6gEXuYwHLI',
  festive_red: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAFj3s1Lg-nB_uRfAPZ6uLDRTgkoSnw0_japaDC68mxVPALBv-ANKzjFZLoDEnsudst6sdKJJpn2G0EsbfStbWo8EIgz_GVh1wdIxCYIxQQ1bJJ_OKEnpkULU7PFeGvuI-k-f281uMxrgUmZMOwaA0Rj9U49w5Pzx3wkU5hV5QACeox5ZX-li71xYZOT06g2KLaHMuxyl0T0nydxtqSnPaOT54N-h9fcrXR3g1nfime1jI9gkQO6S-2TBD5pdpql7HFAr9jip1Bh08',
  modern_black: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBDBP4BrTyi2GcMPBop8amdkt4v-nIeZrjS6-XLaEAF-UfcGSr-QzBO4OJHx4CvAOTNYY3JrM9cA_FILjRpTxRmxpGzk0N0SVZrVQEVUlQdqrzRT_xZsUMJ92pOCle6OFvWVGVHEiG47llaaujFUvkuBDOcUAqbSYi1hHFKQEpMVL83ofmlspEPk8sUM-Of37AxWYBC6atL35ESMaaNbHoZf0WgpgZjg-L2yKE21l2ApPZsRKcyrozZpbzwKlsp8S0bbXeFtCDo80Y',
  classic_emerald: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCU4kOdI4foPxzBZPaJWeU4e6hgpb1ob2ELtVg_0vSv-_f1j9pA2_7_M-KiZHBQZQbUWmXjvVyoBbMxzdNcIOy-GFE6vxya-o-yNe6gH0LOF52hHIkxVjPcuYCg7m46wtFSLdK6YnVVC2N29HsTwPrSuxK9HoNvrzzO5TnpSVpJLK6EEAIaQ-vHFxZmzDXlZxS8Jm6YOYOWbQoA6MfbBnQHLVTec7iDytDDtxxYBVZU0LIjInSiM0UQgFxMewJLa06nErZ-0FMZyfs'
};

export default function Dashboard() {
  const navigate = useNavigate();
  const vcfg = useVerticalConfig();
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchCampaigns();
  }, []);

  const fetchCampaigns = async () => {
    try {
      const response = await authFetch('/api/campaigns');
      if (!response.ok) throw new Error('Failed to fetch campaigns');
      const data = await response.json();
      setCampaigns(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const deleteCampaign = async (campaignId: string, campaignName: string) => {
    if (!window.confirm(`Delete campaign "${campaignName}"?\nThis will remove all preview and production deployments.`)) return;
    try {
      const response = await authFetch(`/api/campaigns/${campaignId}`, { method: 'DELETE' });
      if (!response.ok) {
        const errBody = await response.json().catch(() => ({}));
        throw new Error(errBody.error || 'Failed to delete campaign');
      }
      setCampaigns(prev => prev.filter(c => c.id !== campaignId));
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to delete');
    }
  };

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric'
    });
  };

  if (loading) {
    return (
      <Layout activeStep="overview">
        <div className="flex items-center justify-center h-64">
          <div className="flex flex-col items-center gap-4">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
            <p className="text-on-surface-variant text-sm">Loading campaigns...</p>
          </div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout activeStep="overview">
      {/* Hero Section */}
      <section className="flex flex-col md:flex-row md:items-end justify-between gap-8 mb-16">
        <div className="max-w-2xl">
          <span className="text-tertiary-fixed-dim font-label text-[0.6875rem] uppercase tracking-[0.1em] font-bold mb-4 block">
            Executive Performance Portal
          </span>
          <h1 className="text-[3.5rem] font-extrabold text-on-surface leading-[1.1] tracking-tight mb-4 font-headline">
            Campaign Overview.
          </h1>
          <p className="text-on-surface-variant text-lg leading-relaxed max-w-lg">
            {vcfg.brand.dashboard_tagline || 'Manage and orchestrate high-value marketing campaigns.'}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <button
            onClick={() => navigate('/campaign/create')}
            className="bg-primary text-on-primary px-8 py-4 rounded-xl font-bold flex items-center gap-3 shadow-2xl hover:scale-[1.02] transition-transform active:scale-[0.98] ease-[cubic-bezier(0.2,0,0,1)]"
          >
            <span className="material-symbols-outlined">add</span>
            Create New Campaign
          </button>
        </div>
      </section>

      {/* Stats Section */}
      <section className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-16">
        <div className="md:col-span-2 bg-primary-container p-8 rounded-[2rem] flex flex-col justify-between h-64 overflow-hidden relative group">
          <div className="relative z-10">
            <span className="text-tertiary-fixed-dim font-bold text-xs uppercase tracking-widest">Total Campaigns</span>
            <div className="text-[4rem] font-extrabold text-white mt-2 leading-none">
              {campaigns.length}<span className="text-lg opacity-50 ml-1">active</span>
            </div>
          </div>
          <div className="relative z-10 flex items-center gap-2 text-white/70 font-medium">
            <span className="material-symbols-outlined text-tertiary-fixed-dim" style={{fontVariationSettings: "'FILL' 1"}}>trending_up</span>
            AI-Powered Campaign Generation
          </div>
        </div>
        <div className="bg-surface-container-low p-8 rounded-[2rem] flex flex-col justify-between h-64 border-none">
          <div>
            <span className="text-on-surface-variant font-bold text-xs uppercase tracking-widest">Live Campaigns</span>
            <div className="text-[2rem] font-bold text-on-surface mt-2">
              {campaigns.filter(c => c.status === 'live').length}
            </div>
          </div>
          <div className="flex items-center gap-3">
            {['language', 'mail', 'share'].map(icon => (
              <div key={icon} className="p-2 bg-secondary-container rounded-lg">
                <span className="material-symbols-outlined text-on-secondary-container">{icon}</span>
              </div>
            ))}
          </div>
        </div>
        <div className="bg-surface-container-lowest p-8 rounded-[2rem] flex flex-col justify-between h-64 border-none shadow-sm group hover:bg-white transition-colors duration-300">
          <div>
            <span className="text-on-surface-variant font-bold text-xs uppercase tracking-widest">Draft Campaigns</span>
            <div className="text-[2rem] font-bold text-on-surface mt-2">
              {campaigns.filter(c => c.status === 'draft' || c.status === 'preview_ready').length}
            </div>
          </div>
          <div className="flex items-center gap-2 text-on-surface-variant text-sm">
            <span className="material-symbols-outlined text-[18px]">edit_note</span>
            Ready for review
          </div>
        </div>
      </section>

      {/* Error State */}
      {error && (
        <div className="bg-error-container border border-error/20 rounded-xl p-6 mb-8">
          <div className="flex items-center gap-3">
            <span className="material-symbols-outlined text-error">error</span>
            <p className="text-on-error-container font-medium">{error}</p>
          </div>
          <button
            onClick={fetchCampaigns}
            className="mt-4 text-error font-bold text-sm flex items-center gap-2 hover:underline"
          >
            <span className="material-symbols-outlined text-sm">refresh</span> Retry
          </button>
        </div>
      )}

      {/* Campaign List Header */}
      <div className="flex items-center justify-between mb-8">
        <h2 className="text-[1.75rem] font-bold tracking-tight text-on-surface font-headline">Active Portfolio</h2>
        <div className="flex items-center gap-4 text-on-surface-variant text-sm font-medium">
          <span className="flex items-center gap-1 cursor-pointer hover:text-primary transition-colors">
            <span className="material-symbols-outlined text-[18px]">sort</span> Filter
          </span>
          <span className="w-[1px] h-4 bg-outline-variant/30"></span>
          <span className="flex items-center gap-1 cursor-pointer hover:text-primary transition-colors">
            <span className="material-symbols-outlined text-[18px]">view_column</span> View: Cards
          </span>
        </div>
      </div>

      {/* Campaign Cards */}
      <section className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {campaigns.map((campaign) => {
          const status = statusConfig[campaign.status] || statusConfig.draft;
          const image = campaign.hero_image_url || themeImages[campaign.theme] || themeImages.luxury_gold;

          return (
            <div
              key={campaign.id}
              onClick={() => navigate(`/campaign/${campaign.id}`)}
              className="bg-surface-container-lowest rounded-[2rem] overflow-hidden flex flex-col group transition-all duration-300 hover:scale-[1.01] cursor-pointer shadow-[0_18px_40px_-24px_rgba(15,23,42,0.35)]"
            >
              <div className="relative overflow-hidden bg-[linear-gradient(135deg,#f8fafc_0%,#e2e8f0_100%)] px-6 pt-6">
                <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(255,255,255,0.8),transparent_45%)]" />
                <div className="absolute inset-x-6 top-6 h-[1px] bg-white/70" />
                <div className="relative mx-auto h-52 w-full max-w-[30rem] rotate-[-1.5deg] rounded-[1.75rem] border border-black/5 bg-white p-3 shadow-[0_26px_50px_-30px_rgba(15,23,42,0.45)] transition-transform duration-500 group-hover:rotate-0 group-hover:scale-[1.01]">
                  <div className="absolute left-6 top-4 h-6 w-14 rounded-full bg-white/75 shadow-sm backdrop-blur-sm" />
                  <div className="absolute right-6 top-4 h-6 w-14 rounded-full bg-white/65 shadow-sm backdrop-blur-sm" />
                  <div className="relative h-full w-full overflow-hidden rounded-[1.1rem] bg-slate-950">
                    <img
                      className="h-full w-full object-cover transition-all duration-700 group-hover:scale-105"
                      src={image}
                      alt={campaign.campaign_name}
                    />
                    <div className="absolute inset-0 bg-gradient-to-t from-slate-950/60 via-slate-950/5 to-white/10" />
                  </div>
                </div>
                <div className="absolute top-6 left-6 flex gap-2">
                  <span className={`px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider shadow-sm ${status.color}`}>
                    {status.label}
                  </span>
                  {campaign.status === 'live' && (
                    <span className="bg-tertiary-fixed-dim px-3 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider text-tertiary shadow-sm">
                      Priority
                    </span>
                  )}
                </div>
                <div className="relative px-2 pb-6 pt-4 text-[10px] font-bold uppercase tracking-[0.28em] text-on-surface-variant/70">
                  Campaign Snapshot
                </div>
              </div>
              <div className="p-8 flex flex-col flex-1">
                <div className="flex justify-between items-start mb-6">
                  <div>
                    <h3 className="text-xl font-bold mb-1 group-hover:text-primary transition-colors font-headline">
                      {campaign.campaign_name}
                    </h3>
                    <div className="flex items-center gap-2 text-on-surface-variant text-sm font-medium">
                      <span className="material-symbols-outlined text-[16px]">location_on</span>
                      {campaign.hotel_name || vcfg.properties[0] || ''}
                    </div>
                  </div>
                  <div className="text-right">
                    <div className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest mb-1">AUDIENCE</div>
                    <div className="text-sm font-bold text-on-surface">{campaign.target_audience}</div>
                  </div>
                </div>
                <div className="flex items-center justify-between mt-auto pt-6 border-t border-surface-container-low">
                  <div className="flex flex-col gap-1">
                    <span className="text-[10px] text-on-surface-variant font-bold uppercase tracking-widest">Timeline</span>
                    <span className="text-sm font-medium text-on-surface">
                      {campaign.start_date && campaign.end_date
                        ? `${formatDate(campaign.start_date)} — ${formatDate(campaign.end_date)}`
                        : formatDate(campaign.created_at)
                      }
                    </span>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); navigate(`/campaign/${campaign.id}`); }}
                      className="bg-primary text-on-primary px-4 py-2 rounded-lg font-bold text-sm hover:opacity-90 transition-all active:scale-95"
                    >
                      {campaign.status === 'live' ? 'View Campaign' :
                       campaign.status === 'preview_ready' || campaign.status === 'email_ready' ? 'Continue' :
                       campaign.status === 'generating' ? 'View Progress' : 'Manage'}
                    </button>
                    {campaign.production_url && (
                      <a
                        href={campaign.production_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="bg-surface-container px-4 py-2 rounded-lg font-bold text-sm hover:bg-surface-container-high transition-all active:scale-95 flex items-center gap-1"
                      >
                        <span className="material-symbols-outlined text-[16px]">open_in_new</span> Live
                      </a>
                    )}
                    <button
                      onClick={(e) => { e.stopPropagation(); deleteCampaign(campaign.id, campaign.campaign_name); }}
                      className="bg-surface-container text-error px-3 py-2 rounded-lg text-sm hover:bg-error-container transition-all active:scale-95 flex items-center"
                      title="Delete campaign"
                    >
                      <span className="material-symbols-outlined text-[18px]">delete</span>
                    </button>
                  </div>
                </div>
              </div>
            </div>
          );
        })}

        {/* Create New Campaign Card */}
        <div
          onClick={() => navigate('/campaign/create')}
          className="border-2 border-dashed border-outline-variant/30 rounded-[2rem] h-full min-h-[400px] flex items-center justify-center group cursor-pointer hover:border-primary/40 transition-all bg-surface-container-low/20"
        >
          <div className="flex flex-col items-center gap-4 text-on-surface-variant group-hover:text-primary transition-colors text-center">
            <div className="p-6 rounded-full bg-white shadow-sm group-hover:shadow-md transition-all">
              <span className="material-symbols-outlined text-[48px]">add_circle</span>
            </div>
            <span className="font-bold text-lg font-headline">Initiate New Journey</span>
            <span className="text-sm max-w-[200px] opacity-60">Leverage AI to generate a strategic marketing campaign.</span>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="mt-32 pt-16 border-t border-surface-container flex flex-col md:flex-row items-center justify-between gap-8 opacity-60">
        <div className="text-sm font-medium">{vcfg.brand.footer}</div>
        <div className="flex items-center gap-8 text-sm font-bold uppercase tracking-[0.2em]">
          <span className="hover:text-primary transition-colors cursor-pointer">Integrations</span>
          <span className="hover:text-primary transition-colors cursor-pointer">Network</span>
          <span className="hover:text-primary transition-colors cursor-pointer">Security</span>
        </div>
      </footer>
    </Layout>
  );
}
