import React, { useState, useEffect } from 'react';
import axios from 'axios';
import loads from './loads8760.json';
import { useTariff } from './TariffContext';

// Basic inline styles for MVP
const baseCardStyle = {
  border: '1px solid #ddd',
  borderRadius: 6,
  padding: 12,
  marginBottom: 8,
  cursor: 'pointer',
  background: '#fff'
};

const detailPanelStyle = {
  border: '1px solid #e0e0e0',
  borderRadius: 8,
  padding: 12,
  marginTop: 12,
  background: '#fafafa'
};

function safeNumber(v, fallback = 0) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

const TariffCard = ({ tariff, onSelect, selected }) => {
  const name = tariff?.name || tariff?.label || 'Tariff';
  const utility_name = tariff?.utility_name || tariff?.utility || '';
  const rate_type = tariff?.rate_type || tariff?.ratestructure || '';
  const monthly_fixed_charge = safeNumber(tariff?.monthly_fixed_charge || tariff?.monthly_charge || tariff?.monthly_fee);
  const estimateHint = monthly_fixed_charge ? `$${monthly_fixed_charge.toFixed(2)}/mo` : '';
  const selectedStyle = selected ? { outline: '2px solid #1976d2' } : {};

  const handleKey = (e) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onSelect && onSelect(tariff);
    }
  };

  return (
    <div
      role="button"
      tabIndex={0}
      aria-pressed={!!selected}
      className="tariff-card"
      onClick={() => onSelect && onSelect(tariff)}
      onKeyDown={handleKey}
      style={{ ...baseCardStyle, ...selectedStyle }}
    >
      <div style={{ fontWeight: 'bold' }}>{name}</div>
      <div style={{ color: '#555', fontSize: 14 }}>{utility_name}{utility_name && rate_type ? ' • ' : ''}{rate_type}</div>
      {estimateHint && (
        <div style={{ marginTop: 6, fontSize: 12, color: '#777' }}>Est. {estimateHint} per month</div>
      )}
    </div>
  );
};


const TariffDetailPanel = ({ tariff }) => {
  if (!tariff) return null;
  const full = { ...(tariff.raw || {}), ...tariff };

  // derive monthly fixed
  const getMonthlyFixed = (obj) => {
    if (!obj) return 0;
    const cand = [obj.fixedchargepermonth, obj.monthly_fixed_charge, obj.monthly_charge, obj.monthly_fee, obj.fixedmonthlycharge];
    for (const v of cand) {
      if (v !== undefined && v !== null && v !== '') {
        const n = Number(String(v).replace(/[^0-9.\-]/g, ''));
        if (Number.isFinite(n)) return n;
      }
    }
    return 0;
  };
  const monthly = safeNumber(getMonthlyFixed(full), 0);

  // TOU candidates
  const touBlocks = full.tou_blocks || full.tou_schedule || full.tou || full.energyschedule || [];
  const weekdayMonthly = Array.isArray(full.energyweekdayschedule) ? full.energyweekdayschedule : (Array.isArray(full.energyweekdays) ? full.energyweekdays : []);
  // normalize weekdayMonthly to months x 24 if possible
  const normalizeMonths = (m) => {
    if (!Array.isArray(m)) return [];
    if (m.length === 24 && m.every(x => typeof x === 'number')) return [m];
    const out = [];
    for (const inner of m) if (Array.isArray(inner) && inner.length === 24) out.push(inner);
    return out.slice(0, 12);
  };
  const weekdayMonths = normalizeMonths(weekdayMonthly);

  // compute hourly average snapshot from loads8760.json (assume hourly calendar order)
  const hourlySums = new Array(24).fill(0);
  const hourlyCounts = new Array(24).fill(0);
  if (Array.isArray(loads) && loads.length > 0) {
    for (let i = 0; i < loads.length; i++) {
      const h = i % 24;
      const v = Number(loads[i]) || 0;
      hourlySums[h] += v;
      hourlyCounts[h]++;
    }
  }
  const hourlyAvg = hourlySums.map((s, i) => (hourlyCounts[i] ? s / hourlyCounts[i] : 0));
  const maxAvg = Math.max(...hourlyAvg, 1);

  // period names
  const touNames = (full.tou_names || full.energyrate_names || full.energyrate_labels || full.rate_names || full.names) || [];

  return (
    <div className="tariff-detail-panel" style={detailPanelStyle}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
        <div style={{ fontSize: 18, fontWeight: 600 }}>{tariff.name || tariff.label || 'Tariff Detail'}</div>
        <span style={{ fontSize: 12, color: '#666' }}>{tariff.utility_name || tariff.utility || ''}{(tariff.utility_name || tariff.utility) && tariff.rate_type ? ' • ' : ''}{tariff.rate_type || tariff.ratestructure || ''}</span>
      </div>

      <div style={{ marginTop: 8 }}>
        <div><strong>Monthly Fixed Charge:</strong> ${monthly.toFixed(2)}</div>
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>TOU Energy Costs</div>
        {Array.isArray(full.energyratestructure) && full.energyratestructure.length > 0 ? (
          <ul style={{ paddingLeft: 20 }}>
            {full.energyratestructure.map((period, periodIndex) => (
              <li key={periodIndex} style={{ marginBottom: 4 }}>
                <strong>Period {periodIndex + 1}:</strong>
                {period.map((tier, tierIndex) => (
                  <div key={tierIndex}>
                    <strong>Tier {tierIndex + 1}:</strong> {tier.rate ? `$${tier.rate.toFixed(2)} per kWh` : 'N/A'}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: '#666' }}>No TOU energy costs available</div>
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Demand Costs</div>
        {Array.isArray(full.demandratestructure) && full.demandratestructure.length > 0 ? (
          <ul style={{ paddingLeft: 20 }}>
            {full.demandratestructure.map((period, periodIndex) => (
              <li key={periodIndex} style={{ marginBottom: 4 }}>
                <strong>Period {periodIndex + 1}:</strong>
                {period.map((tier, tierIndex) => (
                  <div key={tierIndex}>
                    <strong>Tier {tierIndex + 1}:</strong> {tier.rate ? `$${tier.rate.toFixed(2)} per kW` : 'N/A'}
                  </div>
                ))}
              </li>
            ))}
          </ul>
        ) : (
          <div style={{ color: '#666' }}>No demand costs available</div>
        )}
      </div>

      <div style={{ marginTop: 12 }}>
        <div style={{ fontWeight: 600, marginBottom: 6 }}>Fixed Costs</div>
        <div>
          <strong>Monthly Fixed Charge (First Meter):</strong> {full.fixedmonthlycharge ? `$${full.fixedmonthlycharge.toFixed(2)}` : 'N/A'}
        </div>
      </div>
    </div>
  );
};

const TariffSelector = ({ apiKey, location, onTariffSelect }) => {
  const { selectedTariff, setSelectedTariff } = useTariff();
  const [tariffs, setTariffs] = useState([]);
  const [detailedTariff, setDetailedTariff] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    const parseLocation = (loc) => {
      // Accept either { lat, lon } or a string "lat,lon" or an address string
      if (!loc) return null;
      if (typeof loc === 'object' && (loc.lat !== undefined || loc.latitude !== undefined)) {
        return { lat: safeNumber(loc.lat ?? loc.latitude), lon: safeNumber(loc.lon ?? loc.longitude ?? loc.lng) };
      }
      if (typeof loc === 'string') {
        const parts = loc.split(',').map(s => s.trim());
        if (parts.length === 2 && !isNaN(Number(parts[0])) && !isNaN(Number(parts[1]))) {
          return { lat: safeNumber(parts[0]), lon: safeNumber(parts[1]) };
        }
        // Otherwise treat as an address search term (let backend or geocoder handle it)
        return { q: loc };
      }
      return null;
    };

    const fetchTariffs = async () => {
      setError('');
      setLoading(true);
      setTariffs([]);
      try {
        const parsed = parseLocation(location);
        if (!parsed) {
          setLoading(false);
          return;
        }
        // If parsed has q (address string), call the backend API that supports q or just return empty
        if (parsed.q) {
          // We don't currently support server-side address search here; prompt user to provide lat/lon.
          setError('Provide a location as latitude/longitude for tariff lookup.');
          setLoading(false);
          return;
        }
        const params = new URLSearchParams({ lat: String(parsed.lat), lon: String(parsed.lon) }).toString();
        const response = await axios.get(`/api/tariffs?${params}`);
        const items = response.data?.tariffs || response.data?.items || [];
        setTariffs(Array.isArray(items) ? items : []);
      } catch (err) {
        console.error('Tariff fetch failed', err);
        setError(err?.response?.data?.error || err.message || 'Failed to fetch tariffs');
        setTariffs([]);
      } finally {
        setLoading(false);
      }
    };

    fetchTariffs();
  }, [location]);

  // Fetch detailed tariff when a selection is made
  useEffect(() => {
    if (!selectedTariff) {
      setDetailedTariff(null);
      setDetailError('');
      return;
    }
    const label = selectedTariff.label || selectedTariff.id;
    if (!label) return;
    setDetailLoading(true);
    setDetailError('');
    setDetailedTariff(null);
    axios.get(`/urdb/${encodeURIComponent(label)}`)
      .then(res => {
        setDetailedTariff(res.data || selectedTariff);
      })
      .catch(err => {
        console.error('Failed to fetch tariff detail', err);
        setDetailError(err?.response?.data?.error || err.message || 'Failed to fetch tariff detail');
        setDetailedTariff(selectedTariff);
      })
      .finally(() => setDetailLoading(false));
  }, [selectedTariff]);

  // precompute filtered list for rendering
  const allowed = ['commercial', 'industrial'];
  const normalize = (v) => (v === undefined || v === null ? '' : String(v).toLowerCase());
  const includesAny = (hay, needles) => {
    if (!hay) return false;
    const s = normalize(hay);
    return needles.some((n) => s.includes(n));
  };
  const arrayContainsAny = (arr, needles) => {
    if (!arr) return false;
    if (Array.isArray(arr)) return arr.some((v) => includesAny(v, needles));
    return includesAny(arr, needles);
  };
  const isApproved = (t) => {
    if (!t) return false;
    if (t.is_current) return true;
    if (t.approved === true || t.is_approved === true) return true;
    if (String(t.approved) === '1' || String(t.approved).toLowerCase() === 'yes' || String(t.approved).toLowerCase() === 'y') return true;
    return false;
  };
  const isBundled = (t) => {
    const svc = normalize(t.service_type || t.service || t.serviceType || '');
    if (svc && svc.includes('bundl')) return true;
    if (includesAny(t.name, ['bundl']) || includesAny(t.notes, ['bundl'])) return true;
    return false;
  };
  const matchesSector = (t) => {
    const s = t.sectors || t.sector || t.sector_type || t.sector_name || '';
    if (arrayContainsAny(s, allowed)) return true;
    if (includesAny(t.rate_type, allowed)) return true;
    if (includesAny(t.name, allowed)) return true;
    return false;
  };
  const filtered = Array.isArray(tariffs) ? tariffs.filter((t) => { try { return isApproved(t) && matchesSector(t); } catch (e) { return false; } }) : [];
  filtered.sort((a,b) => {
    const ua = normalize(a.utility_name || a.utility || '');
    const ub = normalize(b.utility_name || b.utility || '');
    if (ua < ub) return -1; if (ua > ub) return 1;
    const na = normalize(a.name || a.label || '');
    const nb = normalize(b.name || b.label || '');
    if (na < nb) return -1; if (na > nb) return 1; return 0;
  });

  const handleTariffChange = (e) => {
    const id = e.target.value;
    const found = filtered.find((x) => String(x.id) === String(id));
    setSelectedTariff(found || null);
    if (onTariffSelect) {
      onTariffSelect(found?.label || '');
    }
  };

  return (
    <div>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
        <div style={{ fontWeight: 'bold' }}>Tariff Selector</div>
        {loading && <div style={{ color: '#666', fontSize: 13 }}>Loading…</div>}
      </div>

      {error && <div style={{ color: 'red', marginBottom: 8 }}>{error}</div>}

      {!loading && !error && tariffs.length === 0 && (
        <div style={{ color: '#666', marginBottom: 8 }}>No tariffs available for this location.</div>
      )}

      {/* Filter to approved commercial/industrial tariffs */}
      {tariffs.length > 0 && (filtered.length === 0 ? (
        <div style={{ color: '#666', marginBottom: 8 }}>No approved commercial/industrial tariffs found for this location.</div>
      ) : (
        <div style={{ marginBottom: 12 }}>
          <label htmlFor="tariff-select" style={{ display: 'block', marginBottom: 6, fontSize: 14 }}>Choose tariff</label>
          <select
            id="tariff-select"
            value={selectedTariff?.id || ''}
            onChange={handleTariffChange}
            style={{ padding: '8px 10px', borderRadius: 4, border: '1px solid #ccc', minWidth: 320 }}
          >
            <option value="">-- select a tariff --</option>
            {filtered.map((t) => {
              const bundled = isBundled(t) || (t.raw && typeof t.raw.description === 'string' && t.raw.description.toLowerCase().includes('bundl'));
              const label = `${t.utility_name ? `${t.utility_name} — ` : ''}${t.name || t.label}${bundled ? ' (bundled)' : ''}`;
              return <option key={t.id || t.label || t.name} value={t.id}>{label}</option>;
            })}
          </select>
        </div>
      ))}

  {detailLoading && <div style={{ color: '#666', marginTop: 8 }}>Loading tariff details…</div>}
  {detailError && <div style={{ color: 'red', marginTop: 8 }}>{detailError}</div>}
      {/* Quick load by URDB label for debugging/missing items */}
      <div style={{ marginTop: 8, marginBottom: 8, display: 'flex', gap: 8, alignItems: 'center' }}>
        <input id="urdb-label-input" placeholder="Enter URDB label (e.g. 674f800fcb87...)" style={{ padding: '6px 8px', flex: 1 }} />
        <button type="button" onClick={(e) => {
          const v = document.getElementById('urdb-label-input').value.trim();
          if (!v) return;
          setDetailLoading(true);
          setDetailError('');
          axios.get(`/urdb/${encodeURIComponent(v)}`)
            .then(res => setDetailedTariff(res.data))
            .catch(err => setDetailError(err?.response?.data?.error || err.message || 'Failed to fetch tariff by label'))
            .finally(() => setDetailLoading(false));
        }} style={{ padding: '6px 10px' }}>Load</button>
      </div>
  <TariffDetailPanel tariff={detailedTariff || selectedTariff} />
    </div>
  );
};

export default TariffSelector;

