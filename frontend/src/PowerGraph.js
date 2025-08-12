import React, { useState, useMemo } from 'react';
import {
  Box,
  Typography,
  FormGroup,
  FormControlLabel,
  Checkbox
} from '@mui/material';
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer
} from 'recharts';

// Positive stack (serving load) bottom->top
const POS_STACK = [
  { key: 'utility_residual', label: 'Grid', color: '#CCCCCC' },
  { key: 'bess_discharge', label: 'BESS Discharge', color: '#BBDEFB' },
  { key: 'solar_to_load', label: 'Solar to Load', color: '#C8E6C9' },
  { key: 'genset', label: 'Generator', color: '#FFE0B2' }
];

// Negative stack (charging BESS) shown below zero (values already negative)
// Use base colors matching the source; patterns differentiate charging flows.
const NEG_STACK = [
  { key: 'bess_charge_solar', label: 'Solar -> BESS', baseColor: '#C8E6C9', stroke: '#2E7D32', pattern: 'patSolarCharge' },
  { key: 'bess_charge_grid', label: 'Grid -> BESS', baseColor: '#CCCCCC', stroke: '#555555', pattern: 'patGridCharge' },
  { key: 'bess_charge_gen', label: 'Gen -> BESS', baseColor: '#FFE0B2', stroke: '#EF6C00', pattern: 'patGenCharge' }
];

export default function PowerGraph({ data = [] }) {
  // Determine which series are present in the data
  const presentKeys = new Set();
  if (data.length > 0) {
    Object.keys(data[0]).forEach((k) => {
      if (data.some((row) => row[k] !== undefined && row[k] !== 0)) {
        presentKeys.add(k);
      }
    });
  }

  const [show, setShow] = useState(() => ({
    load: presentKeys.has('load'),
    net_utility: presentKeys.has('net_utility') || presentKeys.has('utility'),
    utility_residual: true,
    bess_discharge: presentKeys.has('bess_discharge') || presentKeys.has('bess'),
    solar_to_load: presentKeys.has('solar_to_load') || presentKeys.has('solar'),
    genset: presentKeys.has('genset'),
    bess_charge_solar: presentKeys.has('bess_charge_solar'),
    bess_charge_grid: presentKeys.has('bess_charge_grid'),
    bess_charge_gen: presentKeys.has('bess_charge_gen')
  }));

  const handleToggle = (key) => (e) => {
    setShow({ ...show, [key]: e.target.checked });
  };

  const startTime = data[0]?.timestamp || 0;
  const endTime = data[data.length - 1]?.timestamp || 0;

  // Build derived residual so stacked areas sum to load.
  const displayedData = useMemo(() => {
    return data.map(row => {
      const load = row.load || 0;
      const solar_to_load = show.solar_to_load ? (row.solar_to_load || 0) : 0;
      const bess_discharge = show.bess_discharge ? (row.bess_discharge || 0) : 0;
      const genset = show.genset ? (row.genset || 0) : 0;
      const other = solar_to_load + bess_discharge + genset;
      let utility_residual = Math.max(load - other, 0);
      if (!show.utility_residual) utility_residual = 0;
      // Negative charges
      const bess_charge_solar = show.bess_charge_solar ? (row.bess_charge_solar || 0) : 0;
      const bess_charge_grid = show.bess_charge_grid ? (row.bess_charge_grid || 0) : 0;
      const bess_charge_gen = show.bess_charge_gen ? (row.bess_charge_gen || 0) : 0;
      return {
        ...row,
        solar_to_load,
        bess_discharge,
        genset,
        utility_residual,
        bess_charge_solar,
        bess_charge_grid,
        bess_charge_gen
      };
    });
  }, [data, show.solar_to_load, show.bess_discharge, show.genset, show.utility_residual, show.bess_charge_solar, show.bess_charge_grid, show.bess_charge_gen]);

  return (
    <Box sx={{ width: '100%', height: 400 }}>
      <Typography variant="subtitle1" mb={1}>Power</Typography>
      <Box display="flex" height={300}>
        <Box flexGrow={1}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={displayedData} margin={{ top: 10, right: 30, bottom: 10, left: 20 }}>
              <defs>
                <pattern id="patSolarCharge" patternUnits="userSpaceOnUse" width="8" height="8">
                  <rect width="8" height="8" fill="#C8E6C9" />
                  <path d="M0 8 L8 0" stroke="#2E7D32" strokeWidth="1" />
                </pattern>
                <pattern id="patGridCharge" patternUnits="userSpaceOnUse" width="8" height="8">
                  <rect width="8" height="8" fill="#CCCCCC" />
                  <path d="M0 8 L8 0" stroke="#555555" strokeWidth="1" />
                </pattern>
                <pattern id="patGenCharge" patternUnits="userSpaceOnUse" width="8" height="8">
                  <rect width="8" height="8" fill="#FFE0B2" />
                  <path d="M0 8 L8 0" stroke="#EF6C00" strokeWidth="1" />
                </pattern>
              </defs>
              <CartesianGrid stroke="#eee" verticalLines={true} />
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={[startTime, endTime]}
                tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
              />
              <YAxis label={{ value: 'kW', angle: -90, position: 'insideLeft' }} />
              <Tooltip
                formatter={(value, name) => [`${Number(value).toFixed(0)} kW`, name]}
                labelFormatter={(t) => new Date(t).toLocaleString()}
              />
              {POS_STACK.map(({ key, color }) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stackId="pos"
                  stroke={color}
                  fill={color}
                  isAnimationActive={false}
                  hide={!show[key]}
                />
              ))}
        {NEG_STACK.map(({ key, baseColor, stroke, pattern }) => (
                <Area
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stackId="neg"
          stroke={stroke}
          fill={`url(#${pattern})`}
                  isAnimationActive={false}
                  hide={!show[key]}
                />
              ))}
              {show.load && (
                <Line
                  type="monotone"
                  dataKey="load"
                  stroke="#000"
                  strokeWidth={3}
                  dot={false}
                  strokeDasharray="8 4"
                  name="Site Demand"
                />
              )}
              {show.net_utility && (
                <Line
                  type="monotone"
                  dataKey="net_utility"
                  stroke="#FFD600"
                  strokeWidth={3}
                  dot={false}
                  strokeDasharray="8 4"
                  name="Net Utility"
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </Box>
        <Box width={180} ml={2}>
          <FormGroup>
            {presentKeys.has('load') && (
              <FormControlLabel
                control={<Checkbox checked={show.load} onChange={handleToggle('load')} />}
                label={
                  <Box display="flex" alignItems="center">
                    <Box sx={{ width: 16, height: 10, border: '2px solid #000', backgroundColor: 'transparent', mr: 1 }} />
                    Site Demand
                  </Box>
                }
              />
            )}
            <FormControlLabel
              control={<Checkbox checked={show.net_utility} onChange={handleToggle('net_utility')} />}
              label={
                <Box display="flex" alignItems="center">
                  <Box sx={{ width: 16, height: 10, border: '2px dashed #FFD600', backgroundColor: 'transparent', mr: 1 }} />
                  Net Utility (Line)
                </Box>
              }
            />
            <FormControlLabel
              control={<Checkbox checked={show.utility_residual} onChange={handleToggle('utility_residual')} />}
              label={
                <Box display="flex" alignItems="center">
                  <Box sx={{ width: 16, height: 10, backgroundColor: '#CCCCCC', mr: 1 }} />
                  Grid (Residual)
                </Box>
              }
            />
            {[...POS_STACK.filter(s=>s.key!=='utility_residual'), ...NEG_STACK].map((cfg) => {
              const { key, label } = cfg;
              const swatchStyle = (() => {
                if (cfg.pattern) {
                  const base = cfg.baseColor || cfg.color || '#eee';
                  const stroke = cfg.stroke || '#444';
                  return {
                    backgroundColor: base,
                    backgroundImage: `repeating-linear-gradient(135deg, ${stroke} 0 1px, transparent 1px 6px)`
                  };
                }
                return { backgroundColor: cfg.color || cfg.baseColor };
              })();
              return (
                <FormControlLabel
                  key={key}
                  control={<Checkbox checked={show[key]} onChange={handleToggle(key)} />}
                  label={
                    <Box display="flex" alignItems="center">
                      <Box sx={{ width: 16, height: 10, mr: 1, ...swatchStyle }} />
                      {label}
                    </Box>
                  }
                />
              );
            })}
          </FormGroup>
        </Box>
      </Box>
    </Box>
  );
}

