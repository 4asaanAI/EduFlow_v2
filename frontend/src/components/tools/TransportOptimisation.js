import { useState, useCallback } from 'react';
import { MapPin, Navigation, AlertTriangle, CheckCircle, Search, RefreshCw, Zap } from 'lucide-react';
import {
  geocodeAddress,
  setStudentCoordinates,
  setZoneCentroid,
  fetchRouteSuggestion,
  fetchClusterAnalysis,
  updateStudent,
  getStudents,
} from '@/lib/api';

const TABS = [
  { id: 'geocode', label: 'Geocode Address', icon: MapPin, color: '#4f8ff7' },
  { id: 'route', label: 'Suggest Route', icon: Navigation, color: '#34d399' },
  { id: 'cluster', label: 'Cluster Analysis', icon: AlertTriangle, color: '#fbbf24' },
];

function card(style = {}) {
  return {
    background: 'var(--c-bg)',
    border: '1px solid var(--c-border)',
    borderRadius: 12,
    padding: 16,
    ...style,
  };
}
const inputStyle = {
  width: '100%',
  background: 'var(--c-deep)',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  padding: '9px 12px',
  color: 'var(--c-text)',
  fontSize: 13,
  outline: 'none',
  boxSizing: 'border-box',
};
const btnPrimary = (color = 'var(--tool-hex-4f8ff7)') => ({
  display: 'inline-flex',
  alignItems: 'center',
  gap: 7,
  padding: '9px 18px',
  background: color,
  border: 'none',
  borderRadius: 8,
  color: '#fff',
  fontSize: 13,
  fontWeight: 600,
  cursor: 'pointer',
  flexShrink: 0,
});
const btnSecondary = {
  display: 'inline-flex',
  alignItems: 'center',
  gap: 6,
  padding: '7px 14px',
  background: 'transparent',
  border: '1px solid var(--c-border)',
  borderRadius: 8,
  color: 'var(--c-muted)',
  fontSize: 12,
  fontWeight: 500,
  cursor: 'pointer',
};
const label = { fontSize: 11, fontWeight: 600, color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.05em', display: 'block', marginBottom: 5 };
const sectionTitle = { fontSize: 13, fontWeight: 600, color: 'var(--c-text)', marginBottom: 12 };
const noticeBox = (color) => ({
  display: 'flex', alignItems: 'flex-start', gap: 8, padding: '10px 14px',
  background: `color-mix(in srgb, ${color} 10%, transparent)`,
  border: `1px solid color-mix(in srgb, ${color} 30%, transparent)`,
  borderRadius: 8, fontSize: 12, color, marginBottom: 12,
});
const thStyle = {
  padding: '9px 14px', textAlign: 'left', fontSize: 10, fontWeight: 700,
  color: 'var(--c-faint)', textTransform: 'uppercase', letterSpacing: '0.06em',
  background: 'var(--c-deep)', borderBottom: '1px solid var(--c-border)',
};
const tdStyle = { padding: '10px 14px', fontSize: 12, color: 'var(--c-text)', borderBottom: '1px solid var(--c-border)' };

// Resolve admission number → student_id
async function resolveAdmissionNumber(admNo) {
  try {
    const res = await getStudents(null, { search: admNo.trim(), limit: 5 });
    if (!res.success || !res.data?.length) return null;
    const exact = res.data.find(s => s.admission_number === admNo.trim());
    return (exact || res.data[0]);
  } catch {
    return null;
  }
}

function GeocodeTab() {
  const [address, setAddress] = useState('');
  const [admNo, setAdmNo] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [notice, setNotice] = useState('');

  const handleGeocode = useCallback(async () => {
    if (!address.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setNotice('');
    try {
      const data = await geocodeAddress(address.trim());
      if (data.success) setResult(data.data);
      else setError(data.detail || 'Geocoding failed');
    } catch {
      setError('Request failed');
    } finally {
      setLoading(false);
    }
  }, [address]);

  const handleSaveToStudent = async () => {
    if (!result || !admNo.trim()) return;
    setError('');
    setNotice('');
    setLoading(true);
    try {
      const student = await resolveAdmissionNumber(admNo);
      if (!student) { setError(`No student found with admission number "${admNo}"`); return; }
      const data = await setStudentCoordinates(student.id, result.lat, result.lng);
      if (data.success) setNotice(`Coordinates saved to ${student.name} (${admNo})`);
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
    setNotice('');
    setLoading(true);
    try {
      const data = await setZoneCentroid(zoneId.trim(), result.lat, result.lng);
      if (data.success) setNotice(`Centroid saved to zone "${zoneId}"`);
      else setError(data.detail || 'Save failed');
    } catch {
      setError('Save failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--c-muted)', marginBottom: 16 }}>
        Convert a text address to GPS coordinates using Google Maps Geocoding API, then assign to a student or route zone.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          data-testid="geocode-address-input"
          style={{ ...inputStyle, flex: 1 }}
          placeholder="e.g. Joya Bus Stand, Amroha, UP"
          value={address}
          onChange={e => setAddress(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleGeocode()}
        />
        <button onClick={handleGeocode} disabled={loading || !address.trim()} style={btnPrimary()}>
          {loading ? <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <Search size={14} />}
          Geocode
        </button>
      </div>

      {error && <div style={noticeBox('var(--tool-hex-f87171)')}><AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1 }} />{error}</div>}
      {notice && <div style={noticeBox('var(--tool-hex-34d399)')}><CheckCircle size={13} style={{ flexShrink: 0, marginTop: 1 }} />{notice}</div>}

      {result && (
        <div style={{ ...card(), marginTop: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: 'color-mix(in srgb, var(--tool-hex-4f8ff7) 15%, transparent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
              <MapPin size={15} color="var(--tool-hex-4f8ff7)" />
            </div>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--c-text)' }}>{result.formatted_address}</div>
              <div style={{ fontSize: 11, color: 'var(--c-muted)' }}>
                Lat: <strong>{result.lat}</strong> · Lng: <strong>{result.lng}</strong>
              </div>
            </div>
          </div>

          <div style={{ borderTop: '1px solid var(--c-border)', paddingTop: 14 }}>
            <div style={{ ...sectionTitle, marginBottom: 14 }}>Assign coordinates to:</div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 14 }}>
              <div>
                <label style={label}>Student (Admission No.)</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    data-testid="student-admission-input"
                    style={{ ...inputStyle, marginBottom: 0 }}
                    placeholder="e.g. ARY-2024-001"
                    value={admNo}
                    onChange={e => setAdmNo(e.target.value)}
                  />
                  <button onClick={handleSaveToStudent} disabled={loading || !admNo.trim()} style={btnPrimary('var(--tool-hex-4f8ff7)')}>
                    Save
                  </button>
                </div>
              </div>
              <div>
                <label style={label}>Zone ID (set centroid)</label>
                <div style={{ display: 'flex', gap: 6 }}>
                  <input
                    data-testid="zone-id-input"
                    style={{ ...inputStyle, marginBottom: 0 }}
                    placeholder="Route zone ID"
                    value={zoneId}
                    onChange={e => setZoneId(e.target.value)}
                  />
                  <button onClick={handleSaveToZone} disabled={loading || !zoneId.trim()} style={btnPrimary('var(--tool-hex-34d399)')}>
                    Save
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SuggestRouteTab() {
  const [admNo, setAdmNo] = useState('');
  const [result, setResult] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [resolvedName, setResolvedName] = useState('');

  const handleSuggest = async () => {
    if (!admNo.trim()) return;
    setLoading(true);
    setError('');
    setResult(null);
    setResolvedName('');
    try {
      const student = await resolveAdmissionNumber(admNo);
      if (!student) { setError(`No student found with admission number "${admNo}"`); return; }
      setResolvedName(student.name);
      const data = await fetchRouteSuggestion(student.id);
      if (data.success) setResult(data);
      else setError(data.detail || 'Failed to fetch suggestion');
    } catch {
      setError('Request failed');
    } finally {
      setLoading(false);
    }
  };

  const zones = Array.isArray(result?.data) ? result.data : [];

  return (
    <div>
      <p style={{ fontSize: 13, color: 'var(--c-muted)', marginBottom: 16 }}>
        Rank all active route zones by proximity to a student's stored GPS coordinates.
      </p>
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        <input
          data-testid="suggest-student-admission-input"
          style={{ ...inputStyle, flex: 1 }}
          placeholder="Student Admission No. (e.g. ARY-2024-001)"
          value={admNo}
          onChange={e => setAdmNo(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSuggest()}
        />
        <button onClick={handleSuggest} disabled={loading || !admNo.trim()} style={btnPrimary('var(--tool-hex-34d399)')}>
          {loading ? <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <Navigation size={14} />}
          Suggest
        </button>
      </div>

      {error && <div style={noticeBox('var(--tool-hex-f87171)')}><AlertTriangle size={13} style={{ flexShrink: 0, marginTop: 1 }} />{error}</div>}

      {result && (
        <div>
          <div style={{ fontSize: 12, color: 'var(--c-muted)', marginBottom: 12 }}>
            Zones ranked nearest → farthest for <strong style={{ color: 'var(--c-text)' }}>{resolvedName}</strong> (Adm: {admNo})
          </div>
          {zones.length === 0 ? (
            <div style={noticeBox('var(--tool-hex-fbbf24)')}><AlertTriangle size={13} />No zones with centroids configured yet.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {zones.map((zone, idx) => (
                <div key={zone.zone_id} style={{
                  ...card(),
                  border: zone.is_current ? '1px solid color-mix(in srgb, var(--tool-hex-4f8ff7) 50%, transparent)' : '1px solid var(--c-border)',
                  background: zone.is_current ? 'color-mix(in srgb, var(--tool-hex-4f8ff7) 5%, var(--c-bg))' : 'var(--c-bg)',
                  display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '12px 16px',
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div style={{
                      width: 28, height: 28, borderRadius: '50%', background: idx === 0 ? 'var(--tool-hex-34d399)' : 'var(--c-deep)',
                      display: 'flex', alignItems: 'center', justifyContent: 'center',
                      fontSize: 11, fontWeight: 700, color: idx === 0 ? '#fff' : 'var(--c-faint)', flexShrink: 0,
                    }}>
                      {idx + 1}
                    </div>
                    <div>
                      <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--c-text)' }}>{zone.zone_name}</div>
                      {zone.is_current && (
                        <span style={{ fontSize: 10, fontWeight: 700, padding: '1px 6px', borderRadius: 4, background: 'color-mix(in srgb, var(--tool-hex-4f8ff7) 15%, transparent)', color: 'var(--tool-hex-4f8ff7)' }}>
                          CURRENT ZONE
                        </span>
                      )}
                    </div>
                  </div>
                  <div style={{ fontSize: 13, fontWeight: 600, color: idx === 0 ? 'var(--tool-hex-34d399)' : 'var(--c-muted)' }}>
                    {zone.distance_km} km
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ReassignButton({ studentId, zoneId, onDone }) {
  const [state, setState] = useState('idle');
  const handleReassign = async () => {
    setState('loading');
    try {
      const res = await updateStudent(studentId, { route_zone_id: zoneId });
      setState(res.success ? 'done' : 'error');
      if (res.success && onDone) onDone();
    } catch {
      setState('error');
    }
  };
  if (state === 'done') return <span style={{ fontSize: 11, color: 'var(--tool-hex-34d399)', fontWeight: 600 }}>✓ Reassigned</span>;
  if (state === 'error') return <span style={{ fontSize: 11, color: 'var(--tool-hex-f87171)' }}>Failed</span>;
  return (
    <button onClick={handleReassign} disabled={state === 'loading'} style={{
      padding: '4px 10px', background: 'color-mix(in srgb, var(--tool-hex-34d399) 12%, transparent)',
      border: '1px solid color-mix(in srgb, var(--tool-hex-34d399) 30%, transparent)',
      borderRadius: 6, color: 'var(--tool-hex-34d399)', fontSize: 11, fontWeight: 600, cursor: 'pointer',
      opacity: state === 'loading' ? 0.5 : 1,
    }}>
      {state === 'loading' ? '…' : 'Reassign'}
    </button>
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

  const suboptimal = Array.isArray(result?.data) ? result.data : [];
  const meta = result?.meta || {};

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <div>
          <p style={{ fontSize: 13, color: 'var(--c-muted)', margin: 0 }}>
            Identify students assigned to a zone that is not their nearest zone.
          </p>
          {result && (
            <div style={{ display: 'flex', gap: 16, marginTop: 10 }}>
              <div style={{ fontSize: 12, color: 'var(--c-muted)' }}>
                Students with GPS: <strong style={{ color: 'var(--c-text)' }}>{meta.total_with_coords ?? '—'}</strong>
              </div>
              <div style={{ fontSize: 12, color: 'var(--tool-hex-fbbf24)' }}>
                Suboptimal assignments: <strong>{meta.total_suboptimal ?? '—'}</strong>
              </div>
            </div>
          )}
        </div>
        <button data-testid="cluster-analysis-btn" onClick={handleAnalyse} disabled={loading} style={btnPrimary('var(--tool-hex-fbbf24)')}>
          {loading ? <RefreshCw size={14} style={{ animation: 'spin 0.8s linear infinite' }} /> : <Zap size={14} />}
          Run Analysis
        </button>
      </div>

      {error && <div style={noticeBox('var(--tool-hex-f87171)')}><AlertTriangle size={13} />{error}</div>}

      {result && suboptimal.length === 0 && (
        <div style={noticeBox('var(--tool-hex-34d399)')}>
          <CheckCircle size={13} style={{ flexShrink: 0, marginTop: 1 }} />
          All students with GPS coordinates are already in their nearest zone.
        </div>
      )}

      {suboptimal.length > 0 && (
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', background: 'var(--c-bg)', border: '1px solid var(--c-border)', borderRadius: 10, overflow: 'hidden' }}>
            <thead>
              <tr>
                {['Student', 'Adm. No.', 'Current Zone', 'Dist.', 'Nearest Zone', 'Dist.', 'Saving', 'Action'].map(h => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {suboptimal.map(row => (
                <tr key={row.student_id} style={{ transition: 'background 0.15s' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'var(--c-deep)'}
                  onMouseLeave={e => e.currentTarget.style.background = ''}>
                  <td style={tdStyle}>{row.student_name}</td>
                  <td style={{ ...tdStyle, fontFamily: 'monospace', fontSize: 11, color: 'var(--c-muted)' }}>{row.admission_number || '—'}</td>
                  <td style={tdStyle}>{row.current_zone_name}</td>
                  <td style={{ ...tdStyle, color: 'var(--tool-hex-f87171)', fontWeight: 600 }}>{row.current_distance_km} km</td>
                  <td style={{ ...tdStyle, color: 'var(--tool-hex-34d399)', fontWeight: 600 }}>{row.nearest_zone_name}</td>
                  <td style={{ ...tdStyle, color: 'var(--tool-hex-34d399)' }}>{row.nearest_distance_km} km</td>
                  <td style={tdStyle}>
                    <span style={{ fontSize: 11, fontWeight: 700, padding: '2px 7px', borderRadius: 5, background: 'color-mix(in srgb, var(--tool-hex-fbbf24) 12%, transparent)', color: 'var(--tool-hex-fbbf24)' }}>
                      -{row.savings_km} km
                    </span>
                  </td>
                  <td style={tdStyle}>
                    <ReassignButton studentId={row.student_id} zoneId={row.nearest_zone_id} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default function TransportOptimisation() {
  const [activeTab, setActiveTab] = useState(0);
  const ActiveTab = [GeocodeTab, SuggestRouteTab, ClusterAnalysisTab][activeTab];

  return (
    <div style={{ padding: '20px 0' }}>
      <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>

      {/* Header */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
          <div style={{ width: 36, height: 36, borderRadius: 10, background: 'color-mix(in srgb, var(--tool-hex-4f8ff7) 15%, transparent)', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <MapPin size={18} color="var(--tool-hex-4f8ff7)" />
          </div>
          <div>
            <h2 style={{ fontSize: 18, fontWeight: 700, color: 'var(--c-text)', margin: 0, letterSpacing: '-0.02em' }}>Route Optimisation</h2>
            <p style={{ fontSize: 12, color: 'var(--c-muted)', margin: 0 }}>Geocode addresses · Suggest optimal routes · Identify suboptimal zone assignments</p>
          </div>
        </div>
      </div>

      {/* Tab bar */}
      <div style={{ display: 'flex', gap: 4, padding: 4, background: 'var(--c-deep)', borderRadius: 10, marginBottom: 20, width: 'fit-content' }}>
        {TABS.map((tab, idx) => {
          const Icon = tab.icon;
          const isActive = activeTab === idx;
          return (
            <button
              key={tab.id}
              data-testid={`transport-opt-tab-${idx}`}
              onClick={() => setActiveTab(idx)}
              style={{
                display: 'flex', alignItems: 'center', gap: 6,
                padding: '7px 14px', borderRadius: 7,
                background: isActive ? 'var(--c-bg)' : 'transparent',
                border: isActive ? '1px solid var(--c-border)' : '1px solid transparent',
                color: isActive ? 'var(--c-text)' : 'var(--c-muted)',
                fontSize: 12, fontWeight: isActive ? 600 : 500, cursor: 'pointer',
                transition: 'all 0.15s', boxShadow: isActive ? 'var(--shadow-sm)' : 'none',
              }}
            >
              <Icon size={13} color={isActive ? tab.color : undefined} />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* Tab content */}
      <div style={{ ...card(), minHeight: 200 }}>
        <ActiveTab />
      </div>
    </div>
  );
}
