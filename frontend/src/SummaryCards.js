import React from 'react';
import { Box, Card, CardContent, Typography } from '@mui/material';

function formatValue(val, type) {
  if (val === undefined || val === null) return '—';
  if (type === 'currency') {
    return `$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
  }
  if (type === 'number') {
    return Number(val).toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
  return val;
}

export default function SummaryCards({ data }) {
  if (!data) return null;
  const metrics = [
    { key: 'upfront_cost', label: 'Upfront Cost', type: 'currency' },
    { key: 'net_savings', label: 'Net Savings', type: 'currency' },
    { key: 'npv', label: 'NPV', type: 'currency' },
    { key: 'payback', label: 'Payback (yrs)', type: 'number' },
  ];
  return (
    <Box display="flex" flexWrap="wrap" gap={2}>
      {metrics.map((m) => (
        <Card key={m.key} sx={{ minWidth: 140 }}>
          <CardContent>
            <Typography variant="subtitle2">{m.label}</Typography>
            <Typography variant="h6" fontWeight="bold">
              {formatValue(data[m.key], m.type)}
            </Typography>
          </CardContent>
        </Card>
      ))}
    </Box>
  );
}

