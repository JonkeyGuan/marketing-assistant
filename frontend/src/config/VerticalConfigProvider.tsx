import React, { createContext, useContext, useEffect, useState } from 'react';
import { authFetch } from '../auth/authFetch';

interface VerticalBrand {
  company_name: string;
  tagline: string;
  footer: string;
  logo_alt: string;
  page_title: string;
  dashboard_tagline: string;
  email_domain: string;
  email_from_name: string;
}

interface TierConfig {
  id: string;
  label: string;
  role?: string;
}

interface ThemeConfig {
  name: string;
  tag: string;
  desc: string;
  preset_name?: string;
}

interface QuickStartPreset {
  name: string;
  desc: string;
  audience: string;
  property: string;
}

export interface VerticalConfig {
  brand: VerticalBrand;
  properties: string[];
  property_label: string;
  tiers: Record<string, TierConfig>;
  audience_suggestions: string[];
  themes: Record<string, ThemeConfig>;
  quick_start_presets: QuickStartPreset[];
  guardrail_presets: QuickStartPreset[];
  competitors: string[];
}

const DEFAULT_CONFIG: VerticalConfig = {
  brand: {
    company_name: 'Simon Casino Resort',
    tagline: 'Luxury Redefined',
    footer: '© 2026 Simon Casino Resort. Powered by OpenShift AI.',
    logo_alt: 'Simon Casino Resort',
    page_title: 'Campaign Manager',
    dashboard_tagline: 'Manage and orchestrate high-value marketing campaigns.',
    email_domain: 'simoncasino.com',
    email_from_name: 'Simon Casino Resort',
  },
  properties: ['Simon Casino Resort'],
  property_label: 'Property',
  tiers: { top: { id: 'platinum', label: 'Platinum VIP', role: 'platinum-access' } },
  audience_suggestions: ['All customers'],
  themes: {},
  quick_start_presets: [],
  guardrail_presets: [],
  competitors: [],
};

const VerticalConfigContext = createContext<VerticalConfig>(DEFAULT_CONFIG);

export const useVerticalConfig = () => useContext(VerticalConfigContext);

export const VerticalConfigProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [config, setConfig] = useState<VerticalConfig>(DEFAULT_CONFIG);

  useEffect(() => {
    authFetch('/api/config')
      .then(res => res.ok ? res.json() : null)
      .then(data => {
        if (data) {
          setConfig({ ...DEFAULT_CONFIG, ...data });
          if (data.brand?.page_title) document.title = data.brand.page_title;
        }
      })
      .catch(() => {});
  }, []);

  return (
    <VerticalConfigContext.Provider value={config}>
      {children}
    </VerticalConfigContext.Provider>
  );
};
