import React from 'react';
import { Typography } from '@mui/material';
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
} from 'recharts';

export default function PowerChart({ data = [] }) {
  if (!data.length) {
    return <Typography>No data available.</Typography>;
  }

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={data} margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
        <CartesianGrid stroke="#eee" />
        <XAxis dataKey="hour" />
        <YAxis label={{ value: 'kW', angle: -90, position: 'insideLeft' }} />
        <Tooltip />
        <ReferenceLine y={0} stroke="#888" strokeDasharray="2 2" />
        <Area type="monotone" dataKey="utility" stroke="#000" fill="#DDDDDD" stackId="1" />
        <Area type="monotone" dataKey="solar" stroke="#388E3C" fill="#C8E6C9" stackId="1" />
        <Area type="monotone" dataKey="bess" stroke="#1976D2" fill="#BBDEFB" stackId="1" />
        <Area type="monotone" dataKey="load" stroke="#000" fill="none" />
      </AreaChart>
    </ResponsiveContainer>
  );
}
