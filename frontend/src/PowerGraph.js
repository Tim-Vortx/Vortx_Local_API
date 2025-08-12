import React, { useState } from 'react';
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

// Stacked supply series with colors and labels
const supplySeries = [
  { key: 'utility', label: 'Utility', color: '#DDDDDD' },
  { key: 'bess', label: 'BESS', color: '#BBDEFB' },
  { key: 'solar', label: 'Solar', color: '#C8E6C9' },
  { key: 'genset', label: 'Generator', color: '#FFE0B2' }
];

export default function PowerGraph({ data = [] }) {
  const [show, setShow] = useState(() => ({
    load: true,
    utility: true,
    bess: true,
    solar: true,
    genset: true
  }));

  const handleToggle = (key) => (e) => {
    setShow({ ...show, [key]: e.target.checked });
  };

  const startTime = data[0]?.timestamp || 0;
  const endTime = data[data.length - 1]?.timestamp || 0;

  return (
    <Box sx={{ width: '100%', height: 400 }}>
      <Typography variant="subtitle1" mb={1}>Power</Typography>
      <Box display="flex" height={300}>
        <Box flexGrow={1}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={data} margin={{ top: 10, right: 30, bottom: 10, left: 20 }}>
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
              {supplySeries.map(({ key, color }) =>
                show[key] ? (
                  <Area
                    key={key}
                    type="monotone"
                    dataKey={key}
                    stackId="supply"
                    stroke={color}
                    fill={color}
                  />
                ) : null
              )}
              {show.load && (
                <Line
                  type="monotone"
                  dataKey="load"
                  stroke="#000"
                  strokeWidth={1.5}
                  dot={false}
                />
              )}
            </AreaChart>
          </ResponsiveContainer>
        </Box>
        <Box width={160} ml={2}>
          <FormGroup>
            <FormControlLabel
              control={<Checkbox checked={show.load} onChange={handleToggle('load')} />}
              label="Load"
            />
            {supplySeries.map(({ key, label, color }) => (
              <FormControlLabel
                key={key}
                control={<Checkbox checked={show[key]} onChange={handleToggle(key)} />}
                label={
                  <Box display="flex" alignItems="center">
                    <Box sx={{ width: 16, height: 10, backgroundColor: color, mr: 1 }} />
                    {label}
                  </Box>
                }
              />
            ))}
          </FormGroup>
        </Box>
      </Box>
    </Box>
  );
}

