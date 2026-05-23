import React from 'react';
import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../../auth/KeycloakProvider';
import { useVerticalConfig } from '../../config/VerticalConfigProvider';


interface LayoutProps {
  children: React.ReactNode;
  activeStep?: string;
  campaignName?: string;
}

const TopNavBar: React.FC = () => {
  const location = useLocation();
  const { authenticated, user, login, logout, enabled } = useAuth();
  const { brand } = useVerticalConfig();
  const isOnCampaigns = location.pathname === '/' || location.pathname.startsWith('/campaign');

  return (
    <header className="bg-slate-50/80 dark:bg-slate-950/80 backdrop-blur-xl font-headline antialiased fixed top-0 z-50 w-full px-12 h-20 border-b border-slate-200/50 dark:border-slate-800/50 flex justify-between items-center">
      <div className="flex items-center gap-8">
        <Link to="/" className="flex items-center gap-2 text-lg font-bold tracking-tight text-slate-900 dark:text-slate-50">
          <img src="/logo.png" alt={brand.logo_alt} className="h-9 w-9 rounded-lg shadow-sm object-contain" />
          {brand.company_name}
        </Link>
        <nav className="hidden md:flex gap-6">
          <Link
            to="/"
            className={`font-medium transition-colors ${isOnCampaigns ? 'text-slate-900 dark:text-slate-50 font-semibold border-b-2 border-slate-900 dark:border-slate-50 pb-1' : 'text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-50'}`}
          >
            Campaigns
          </Link>
          <span className="text-slate-500 dark:text-slate-400 font-medium hover:text-slate-900 dark:hover:text-slate-50 transition-colors cursor-pointer">
            Settings
          </span>
          <Link
            to="/inbox"
            className="text-slate-500 dark:text-slate-400 font-medium hover:text-slate-900 dark:hover:text-slate-50 transition-colors"
          >
            Inbox
          </Link>
        </nav>
      </div>
      <div className="flex items-center gap-4">
        <button className="p-2 hover:bg-slate-200/50 dark:hover:bg-slate-800/50 rounded-lg transition-all">
          <span className="material-symbols-outlined text-slate-900 dark:text-slate-50">notifications</span>
        </button>
        {enabled && !authenticated ? (
          <button
            onClick={login}
            className="flex items-center gap-2 px-4 py-2 bg-slate-900 dark:bg-white text-white dark:text-slate-900 rounded-lg text-sm font-semibold hover:opacity-90 transition-all"
          >
            <span className="material-symbols-outlined text-[18px]">login</span>
            Sign In
          </button>
        ) : (
          <div className="relative group">
            <button className="flex items-center gap-2 p-1 hover:bg-slate-200/50 dark:hover:bg-slate-800/50 rounded-lg transition-all">
              <span className="material-symbols-outlined text-slate-900 dark:text-slate-50" style={{fontVariationSettings: "'FILL' 1"}}>account_circle</span>
              <span className="hidden lg:block text-sm font-medium text-slate-900 dark:text-slate-50">
                {user?.name || 'Executive Profile'}
              </span>
            </button>
            {enabled && authenticated && (
              <div className="absolute right-0 top-full mt-1 w-48 bg-white dark:bg-slate-900 rounded-lg shadow-lg border border-slate-200 dark:border-slate-700 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all z-50">
                <div className="px-4 py-3 border-b border-slate-100 dark:border-slate-800">
                  <p className="text-xs text-slate-500 dark:text-slate-400">Signed in as</p>
                  <p className="text-sm font-medium text-slate-900 dark:text-slate-50 truncate">{user?.username}</p>
                </div>
                <button
                  onClick={logout}
                  className="w-full px-4 py-2.5 text-left text-sm text-red-600 dark:text-red-400 hover:bg-slate-50 dark:hover:bg-slate-800 rounded-b-lg flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[18px]">logout</span>
                  Sign Out
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};

interface SideNavBarProps {
  activeStep?: string;
  campaignName?: string;
}

const SideNavBar: React.FC<SideNavBarProps> = ({ activeStep = '', campaignName }) => {
  const navItems = [
    { id: 'overview', label: 'Overview', icon: 'dashboard', path: '/' },
    { id: 'strategy', label: 'Campaign Brief', icon: 'edit_note', path: '/campaign/create', step: 0 },
    { id: 'assets', label: 'Theme & Design', icon: 'auto_awesome', path: '/campaign/create', step: 1 },
    { id: 'preview', label: 'Review', icon: 'visibility', path: '/campaign/create', step: 2 },
    { id: 'launch', label: 'Go Live', icon: 'rocket_launch', path: '/campaign/create', step: 3 },
  ];

  return (
    <aside className="fixed left-0 top-0 h-full w-72 bg-slate-100 dark:bg-slate-900 border-r border-slate-200/50 dark:border-slate-800/50 flex flex-col p-6 gap-8 z-40 pt-28">
      <div className="flex flex-col gap-1">
        <h2 className="text-slate-900 dark:text-slate-50 font-bold text-xl leading-none font-headline">Campaign Wizard</h2>
        <p className="text-slate-500 dark:text-slate-400 text-xs font-medium uppercase tracking-wider">
          {campaignName ? `Current: ${campaignName}` : 'Campaign Manager'}
        </p>
      </div>
      <nav className="flex flex-col gap-2">
        {navItems.map((item) => {
          const isActive = activeStep === item.id;
          return (
            <Link
              key={item.id}
              to={item.path}
              className={`flex items-center gap-3 rounded-xl px-4 py-3 transition-all duration-300 ${isActive ? 'bg-white dark:bg-slate-950 text-slate-900 dark:text-slate-50 shadow-sm font-semibold' : 'text-slate-500 dark:text-slate-400 hover:bg-slate-200/50 dark:hover:bg-slate-800/50'}`}
            >
              <span className="material-symbols-outlined" style={isActive ? {fontVariationSettings: "'FILL' 1"} : {}}>{item.icon}</span>
              <span className="text-sm">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto flex flex-col gap-2 border-t border-slate-200/50 dark:border-slate-800/50 pt-6">
        <div className="px-4 py-2 mb-2 bg-slate-900/5 dark:bg-white/5 rounded-lg">
          <div className="flex items-center gap-2 text-primary dark:text-white font-bold text-xs uppercase tracking-widest">
            <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse"></span>
            Agent Status: Active
          </div>
        </div>
        <span className="flex items-center gap-3 text-slate-500 dark:text-slate-400 px-4 py-2 hover:text-slate-900 text-sm cursor-pointer">
          <span className="material-symbols-outlined text-[20px]">help</span> Help
        </span>
        <span className="flex items-center gap-3 text-slate-500 dark:text-slate-400 px-4 py-2 hover:text-slate-900 text-sm cursor-pointer">
          <span className="material-symbols-outlined text-[20px]">description</span> Documentation
        </span>
      </div>
    </aside>
  );
};

const Layout: React.FC<LayoutProps> = ({ children, activeStep, campaignName }) => (
  <div className="min-h-screen bg-background text-on-surface">
    <TopNavBar />
    <SideNavBar activeStep={activeStep} campaignName={campaignName} />
    <main className="ml-72 pt-28 px-12 pb-20 max-w-[1600px]">
      {children}
    </main>
  </div>
);

export default Layout;
