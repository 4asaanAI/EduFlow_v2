import React from 'react';
import { ArrowRight, BookOpen, Building2, Bus, Database, GraduationCap, IndianRupee, LayoutDashboard, ShieldCheck, Users } from 'lucide-react';
import { useUser } from '../../contexts/UserContext';
import { hubItemsForUser, MANAGEMENT_HUBS } from '../../lib/managementHubs';
import { ToolPage } from './ToolPage';

const icons = {
  'overview-hub': LayoutDashboard,
  'school-database-hub': Database,
  'finance-commercial-hub': IndianRupee,
  'admissions-communication-hub': GraduationCap,
  'academics-activities-hub': BookOpen,
  'people-operations-hub': Users,
  'campus-library-hub': Building2,
  'transport-hub': Bus,
  'governance-ai-hub': ShieldCheck,
};

export default function ManagementHub({ hubId }) {
  const { currentUser } = useUser();
  const hub = MANAGEMENT_HUBS.find(item => item.id === hubId);
  if (!hub) return null;
  const Icon = icons[hub.id] || LayoutDashboard;
  const items = hubItemsForUser(hub, currentUser);
  const open = toolId => window.dispatchEvent(new CustomEvent('open-tool', { detail: toolId }));

  return <ToolPage title={hub.name} subtitle={hub.subtitle}>
    {/* The hub's own icon, and nothing else. This row used to carry
        "N connected workspaces. Choose what you need." - one shared component, so
        the same sentence appeared on all nine hubs. It told a person nothing they
        could not see (the cards are right below it, and they can count), and it
        cost a line of vertical space on every hub on a phone. Removed at the
        owner's request, 2026-08-06. */}
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: hub.color, marginBottom: 16 }}>
      <Icon size={22} aria-hidden="true" />
    </div>
    <div className="responsive-form-grid" data-testid={`management-hub-${hub.id}`} style={grid}>
      {items.map(([id, name, description]) => <button
        key={id}
        type="button"
        onClick={() => open(id)}
        aria-label={`Open ${name}`}
        style={card}
      >
        <span style={{ minWidth: 0, textAlign: 'left' }}>
          <span style={title}>{name}</span>
          <span style={descriptionStyle}>{description}</span>
        </span>
        <ArrowRight size={17} color={hub.color} aria-hidden="true" />
      </button>)}
    </div>
  </ToolPage>;
}

const grid = {
  display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(min(240px, 100%), 1fr))',
  gap: 12, alignItems: 'stretch',
};
const card = {
  width: '100%', minWidth: 0, minHeight: 88, padding: 16, display: 'flex', alignItems: 'center',
  justifyContent: 'space-between', gap: 12, border: '1px solid var(--color-border)', borderRadius: 12,
  background: 'var(--color-surface-raised)', color: 'var(--color-text-primary)', cursor: 'pointer',
};
const title = { display: 'block', fontSize: 14, fontWeight: 700, marginBottom: 5 };
const descriptionStyle = { display: 'block', color: 'var(--color-text-secondary)', fontSize: 12, lineHeight: 1.45 };
