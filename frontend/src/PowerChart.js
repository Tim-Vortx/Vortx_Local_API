import React, { useState } from 'react';
import {
  Box,
  Typography,
  FormGroup,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import {
  AreaChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  // Brush removed (date slider not needed for single-day view)
} from 'recharts';

// Single-day synthetic default (used only when no real data yet)
const defaultStart = new Date('2025-08-05T00:00:00').getTime();
const defaultData = Array.from({ length: 24 }, (_, h) => {
  const t = new Date(defaultStart + h * 3600 * 1000).getTime();
  const load = 600 + 600 * Math.max(0, Math.sin(((h - 6) / 24) * Math.PI * 2));
  const solar = h >= 6 && h <= 18 ? 800 * Math.sin(((h - 6) / 12) * Math.PI) : 0; // positive generation in daylight
  return { timestamp: t, hour: h, load, solar_to_load: solar * 0.8, utility_to_load: load - solar * 0.8 };
});

// Define the data keys used for stacked supply and overlay areas. Each key maps to
// a stroke and fill color so the chart can dynamically render whichever series are
// toggled on via the legend checkboxes.
const supplyKeys = [
  { key: 'utility_to_load', stroke: '#DDDDDD', fill: '#DDDDDD' },
  { key: 'bess_to_load', stroke: '#BBDEFB', fill: '#BBDEFB' },
  { key: 'solar_to_load', stroke: '#C8E6C9', fill: '#C8E6C9' },
  { key: 'diesel_to_load', stroke: '#FFE0B2', fill: '#FFE0B2' },
  { key: 'ng_to_load', stroke: '#D7CCC8', fill: '#D7CCC8' },
];

const overlayKeys = [
  { key: 'solar_to_bess', stroke: '#C8E6C9', fill: '#C8E6C9' },
  { key: 'utility_to_bess', stroke: '#DDDDDD', fill: '#DDDDDD' },
  { key: 'solar_export', stroke: '#C8E6C9', fill: '#C8E6C9' },
  { key: 'bess_export', stroke: '#BBDEFB', fill: '#BBDEFB' },
  { key: 'diesel_export', stroke: '#FFE0B2', fill: '#FFE0B2' },
  { key: 'ng_export', stroke: '#D7CCC8', fill: '#D7CCC8' },
];

export default function PowerChart({ data = defaultData }) {
  const [show, setShow] = useState({
    load: true,
    utility_to_load: true,
    solar_to_load: true,
    bess_to_load: true,
    diesel_to_load: true,
    ng_to_load: true,
    solar_to_bess: true,
    utility_to_bess: true,
    solar_export: true,
    bess_export: true,
    diesel_export: true,
    ng_export: true,
  });
  // Removed zoom + range logic since we now display a single day at a time
  const handleLegend = (key) => (e) => {
    setShow({ ...show, [key]: e.target.checked });
  };
  const filtered = data; // one-day slice already
  const hasHour = filtered.length && filtered[0].hour !== undefined;
  const startTime = filtered[0]?.timestamp || 0;
  const endTime = filtered[filtered.length - 1]?.timestamp || 0;


  return (
    <Box sx={{ width: '100%', height: 400 }}>
      <Typography variant="subtitle1" mb={1}>Power</Typography>
      <Box display="flex" height={300}>
        <Box flexGrow={1}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filtered} margin={{ top: 10, right: 20, bottom: 10, left: 20 }}>
              <CartesianGrid stroke="#eee" verticalLines={true} />
              {hasHour ? (
                <XAxis
                  dataKey="hour"
                  type="number"
                  domain={[0, 24]}
                  ticks={[0,3,6,9,12,15,18,21,24]}
                  tickFormatter={(h) => `${h}`}
                  label={{ value: 'Hour of Day', position: 'insideBottom', offset: -5 }}
                />
              ) : (
                <XAxis
                  dataKey="timestamp"
                  type="number"
                  domain={[startTime, endTime]}
                  tickFormatter={(t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                />
              )}
              <YAxis
                label={{ value: 'kW', angle: -90, position: 'insideLeft' }}
                domain={['auto', 'auto']}
              />
              <Tooltip
                formatter={(value, name) => [`${Number(value).toFixed(0)} kW`, name]}
                labelFormatter={(v) =>
                  hasHour ? `Hour ${v}` : new Date(v).toLocaleString()
                }
              />
              <ReferenceLine y={0} stroke="#888" strokeDasharray="2 2" />
              {supplyKeys.map(({ key, stroke, fill }) =>
                show[key] ? (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={stroke}
                    fill={fill}
                    stackId="supply"
                  />
                ) : null
              )}
              {overlayKeys.map(({ key, stroke, fill }) =>
                show[key] ? (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stroke={stroke}
                    fill={fill}
                    strokeWidth={1}
                    fillOpacity={0.3}
                  />
                ) : null
              )}
              {show.load && (
                <Line
                  type="monotone"
                  dataKey="load"
                  stroke="#000"
                  strokeWidth={1.5}
                  strokeDasharray="4 4"
                  dot={false}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </Box>
        <Box width={160} ml={2}>
          <FormGroup>
            <FormControlLabel
              control={<Checkbox checked={show.load} onChange={handleLegend('load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 2, borderTop: '2px dotted black', mr: 1 }} />Load</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.utility_to_load} onChange={handleLegend('utility_to_load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#DDDDDD', mr: 1 }} />Utility → Load</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.bess_to_load} onChange={handleLegend('bess_to_load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#BBDEFB', mr: 1 }} />BESS → Load</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.solar_to_load} onChange={handleLegend('solar_to_load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#C8E6C9', mr: 1 }} />Solar → Load</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.diesel_to_load} onChange={handleLegend('diesel_to_load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#FFE0B2', mr: 1 }} />Diesel → Load</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.ng_to_load} onChange={handleLegend('ng_to_load')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#D7CCC8', mr: 1 }} />NG (CHP) → Load</Box>}
            />
          </FormGroup>
        </Box>
      </Box>
    </Box>
  );
}

