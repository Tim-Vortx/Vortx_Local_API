import React from 'react';
import { Box, Typography } from '@mui/material';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function EmissionsPanel({ data }) {
  if (!data) return null;
  const chartData = [
    { name: 'Baseline', value: data.baseline_co2e_tons ?? 0 },
    { name: 'Project', value: data.post_co2e_tons ?? 0 },
  ];
  const reduction =
    data.baseline_co2e_tons != null && data.post_co2e_tons != null
      ? data.baseline_co2e_tons - data.post_co2e_tons
      : null;
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle1">Emissions</Typography>
      <Box sx={{ width: '100%', height: 200 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData}>
            <XAxis dataKey="name" />
            <YAxis label={{ value: 'tCO₂e', angle: -90, position: 'insideLeft' }} />
            <Tooltip formatter={(v) => Number(v).toLocaleString()} />
            <Bar dataKey="value" fill="#90CAF9" />
          </BarChart>
        </ResponsiveContainer>
      </Box>
      {reduction != null && (
        <Typography>
          Lifetime Reduction: <b>{reduction.toLocaleString(undefined, { maximumFractionDigits: 0 })}</b> tCO₂e
        </Typography>
      )}
    </Box>
  );
}

