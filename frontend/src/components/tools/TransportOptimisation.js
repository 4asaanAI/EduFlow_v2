import { useState } from 'react';
import { MapPin, Navigation, AlertTriangle, CheckCircle, Search, RefreshCw } from 'lucide-react';
import {
  geocodeAddress,
  setStudentCoordinates,
  setZoneCentroid,
  fetchRouteSuggestion,
  fetchClusterAnalysis,
  updateStudent,
} from '@/lib/api';

const TABS = ['Geocode', 'Suggest Route', 'Cluster Analysis'];

function ReassignButton({ studentId, zoneId }) {
  const [state, setState] = useState('idle');
  const handleReassign = async () => {
    setState('loading');
    try {
      const res = await updateStudent(studentId, { route_zone_id: zoneId });
      setState(res.success ? 'done' : 'error');
    } catch {
      setState('error');
    }
  };
  if (state === 'done') return <span className="text-green-400 text-xs">Reassigned</span>;
  if (state === 'error') return <span className="text-red-400 text-xs">Failed</span>;
  return (
    <button
      onClick={handleReassign}
      disabled={state === 'loading'}
      className="px-2 py-1 bg-green-600/20 text-green-400 border border-green-600/30 rounded text-xs hover:bg-green-600/30 disabled:opacity-50"
    >
      {state === 'loading' ? '…' : 'Reassign'}
    </button>
  );
}

function StatusBadge({ label, color }) {
  const colors = {
    green: 'bg-green-500/10 text-green-400 border-green-500/20',
    yellow: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
    blue: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs border ${colors[color] || colors.blue}`}>
      {label}
    </span>
  );
}

function GeocodeTab() {
  const [address, setAddress] = useState('');
  const [studentId, setStudentId] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [saved, setSaved] = useState('');

  const handleGeocode = async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setSaved('');
    try {
      const data = await geocodeAddress(address.trim());
      if (data.success) setResult(data.data);
      else setError(data.detail || 'Geocoding failed');
    } catch {
      setError('Request failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveToStudent = async () => {
    if (!result || !studentId.trim()) return;
    setError('');
    setSaved('');
    setLoading(true);
    try {
      const data = await setStudentCoordinates(studentId.trim(), result.lat, result.lng);
      if (data.success) setSaved(`Saved coordinates to student ${studentId}`);
      else setError(data.detail || 'Save failed');
    } catch {
      setError('Save failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveToZone = async () => {
    if (!result || !zoneId.trim()) return;
    setError('');
    setSaved('');
    setLoading(true);
    try {
      const data = await setZoneCentroid(zoneId.trim(), result.lat, result.lng);
      if (data.success) setSaved(`Saved centroid to zone ${zoneId}`);
      else setError(data.detail || 'Save failed');
    } catch {
      setError('Save failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text-secondary)]">
        Convert a text address to GPS coordinates using Google Maps Geocoding API.
      </p>
      <div className="flex gap-2">
        <input
          data-testid="geocode-address-input"
          className="flex-1 bg-[var(--bg-input)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          placeholder="Enter address, e.g. Joya Bus Stand, Amroha, UP"
          value={address}
          onChange={e => setAddress(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleGeocode()}
        />
        <button
          data-testid="geocode-btn"
          onClick={handleGeocode}
          disabled={loading || !address.trim()}
          className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Search size={14} />}
          Geocode
        </button>
      </div>

      {error && <p className="text-red-400 text-sm">{error}</p>}

      {result && (
        <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-lg p-4 space-y-3">
          <div className="flex items-center gap-2">
            <MapPin size={16} className="text-[var(--accent)]" />
            <span className="text-sm font-medium text-[var(--text-primary)]">{result.formatted_address}</span>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs text-[var(--text-secondary)]">
            <span>Latitude: <strong className="text-[var(--text-primary)]">{result.lat}</strong></span>
            <span>Longitude: <strong className="text-[var(--text-primary)]">{result.lng}</strong></span>
          </div>
          <div className="border-t border-[var(--border)] pt-3 space-y-2">
            <p className="text-xs text-[var(--text-muted)]">Assign these coordinates:</p>
            <div className="flex gap-2">
              <input
                data-testid="student-id-input"
                className="flex-1 bg-[var(--bg-input)] border border-[var(--border)] rounded px-2 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
                placeholder="Student ID"
                value={studentId}
                onChange={e => setStudentId(e.target.value)}
              />
              <button
                data-testid="save-to-student-btn"
                onClick={handleSaveToStudent}
                disabled={loading || !studentId.trim()}
                className="px-3 py-1.5 bg-blue-600/20 text-blue-400 border border-blue-600/30 rounded text-xs hover:bg-blue-600/30 disabled:opacity-50"
              >
                Save to Student
              </button>
            </div>
            <div className="flex gap-2">
              <input
                data-testid="zone-id-input"
                className="flex-1 bg-[var(--bg-input)] border border-[var(--border)] rounded px-2 py-1.5 text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none"
                placeholder="Zone ID (set as centroid)"
                value={zoneId}
                onChange={e => setZoneId(e.target.value)}
              />
              <button
                data-testid="save-to-zone-btn"
                onClick={handleSaveToZone}
                disabled={loading || !zoneId.trim()}
                className="px-3 py-1.5 bg-green-600/20 text-green-400 border border-green-600/30 rounded text-xs hover:bg-green-600/30 disabled:opacity-50"
              >
                Set as Zone Centroid
              </button>
            </div>
          </div>
          {saved && (
            <div className="flex items-center gap-2 text-green-400 text-xs">
              <CheckCircle size={12} /> {saved}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function SuggestRouteTab() {
  const [studentId, setStudentId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSuggest = async () => {
    if (!studentId.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    try {
      const data = await fetchRouteSuggestion(studentId.trim());
      if (data.success) setResult(data);
      else setError(data.detail || 'Failed to fetch suggestion');
    } catch {
      setError('Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <p className="text-sm text-[var(--text-secondary)]">
        Rank all active route zones by proximity to a student's stored coordinates.
      </p>
      <div className="flex gap-2">
        <input
          data-testid="suggest-student-id-input"
          className="flex-1 bg-[var(--bg-input)] border border-[var(--border)] rounded-lg px-3 py-2 text-sm text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--accent)]"
          placeholder="Student ID"
          value={studentId}
          onChange={e => setStudentId(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSuggest()}
        />
        <button
          data-testid="suggest-route-btn"
          onClick={handleSuggest}
          disabled={loading || !studentId.trim()}
          className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
        >
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <Navigation size={14} />}
          Suggest
        </button>
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {result && (
        <div className="space-y-2">
          <p className="text-xs text-[var(--text-muted)]">
            Zones ranked by distance for <strong>{result.meta?.student_name || studentId}</strong>:
          </p>
          {(!Array.isArray(result.data) || result.data.length === 0) && (
            <p className="text-sm text-[var(--text-secondary)]">No zones with centroids found.</p>
          )}
          {(Array.isArray(result.data) ? result.data : []).map((zone, idx) => (
            <div
              key={zone.zone_id}
              className={`flex items-center justify-between p-3 rounded-lg border ${
                zone.is_current
                  ? 'border-[var(--accent)]/40 bg-[var(--accent)]/5'
                  : 'border-[var(--border)] bg-[var(--bg-card)]'
              }`}
            >
              <div className="flex items-center gap-3">
                <span className="text-sm font-bold text-[var(--text-muted)] w-5">{idx + 1}</span>
                <div>
                  <p className="text-sm font-medium text-[var(--text-primary)]">{zone.zone_name}</p>
                  {zone.is_current && <StatusBadge label="Current Zone" color="blue" />}
                </div>
              </div>
              <span className="text-sm text-[var(--text-secondary)]">{zone.distance_km} km</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function ClusterAnalysisTab() {
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAnalyse = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchClusterAnalysis();
      if (data.success) setResult(data);
      else setError(data.detail || 'Failed to load cluster analysis');
    } catch {
      setError('Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-start justify-between">
        <p className="text-sm text-[var(--text-secondary)]">
          Students currently assigned to a zone that is not their nearest zone.
        </p>
        <button
          data-testid="cluster-analysis-btn"
          onClick={handleAnalyse}
          disabled={loading}
          className="px-4 py-2 bg-[var(--accent)] text-white rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 flex items-center gap-2 shrink-0"
        >
          {loading ? <RefreshCw size={14} className="animate-spin" /> : <AlertTriangle size={14} />}
          Run Analysis
        </button>
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {result && (
        <div className="space-y-3">
          <div className="flex gap-4 text-xs text-[var(--text-secondary)]">
            <span>Students with coordinates: <strong className="text-[var(--text-primary)]">{result.meta?.total_with_coords}</strong></span>
            <span>Suboptimal assignments: <strong className="text-yellow-400">{result.meta.total_suboptimal}</strong></span>
          </div>
          {(!Array.isArray(result.data) || result.data.length === 0) ? (
            <div className="flex items-center gap-2 text-green-400 text-sm p-3 bg-green-500/5 border border-green-500/20 rounded-lg">
              <CheckCircle size={16} /> All students with coordinates are in their nearest zone.
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-xs">
                <thead>
                  <tr className="text-[var(--text-muted)] border-b border-[var(--border)]">
                    <th className="text-left py-2 pr-3">Student</th>
                    <th className="text-left py-2 pr-3">Current Zone</th>
                    <th className="text-right py-2 pr-3">Dist (km)</th>
                    <th className="text-left py-2 pr-3">Nearest Zone</th>
                    <th className="text-right py-2 pr-3">Dist (km)</th>
                    <th className="text-right py-2 pr-3">Saving</th>
                    <th className="text-right py-2">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {result.data.map(row => (
                    <tr
                      key={row.student_id}
                      className="border-b border-[var(--border)]/50 hover:bg-[var(--bg-card)]"
                    >
                      <td className="py-2 pr-3 text-[var(--text-primary)]">{row.student_name}</td>
                      <td className="py-2 pr-3 text-[var(--text-secondary)]">{row.current_zone_name}</td>
                      <td className="py-2 pr-3 text-right text-[var(--text-secondary)]">{row.current_distance_km}</td>
                      <td className="py-2 pr-3 text-green-400">{row.nearest_zone_name}</td>
                      <td className="py-2 pr-3 text-right text-green-400">{row.nearest_distance_km}</td>
                      <td className="py-2 pr-3 text-right">
                        <StatusBadge label={`-${row.savings_km} km`} color="yellow" />
                      </td>
                      <td className="py-2 text-right">
                        <ReassignButton studentId={row.student_id} zoneId={row.nearest_zone_id} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function TransportOptimisation() {
  const [activeTab, setActiveTab] = useState(0);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2 mb-1">
        <MapPin size={18} className="text-[var(--accent)]" />
        <h3 className="text-base font-semibold text-[var(--text-primary)]">Route Optimisation</h3>
      </div>
      <div className="flex gap-1 p-1 bg-[var(--bg-input)] rounded-lg w-fit">
        {TABS.map((tab, idx) => (
          <button
            key={tab}
            data-testid={`transport-opt-tab-${idx}`}
            onClick={() => setActiveTab(idx)}
            className={`px-3 py-1.5 rounded-md text-xs font-medium transition-colors ${
              activeTab === idx
                ? 'bg-[var(--accent)] text-white'
                : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>
      <div className="bg-[var(--bg-card)] border border-[var(--border)] rounded-xl p-4">
        {activeTab === 0 && <GeocodeTab />}
        {activeTab === 1 && <SuggestRouteTab />}
        {activeTab === 2 && <ClusterAnalysisTab />}
      </div>
    </div>
  );
}
