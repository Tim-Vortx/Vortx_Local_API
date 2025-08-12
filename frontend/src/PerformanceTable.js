import React from 'react';
import { Table, TableHead, TableBody, TableRow, TableCell, Typography } from '@mui/material';

function fmt(val) {
  if (val === undefined || val === null) return '—';
  return `$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function PerformanceTable({ data = [] }) {
  if (!Array.isArray(data) || !data.length) return null;
  return (
    <>
      <Typography variant="subtitle1" sx={{ mt: 2 }}>Performance</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Year</TableCell>
            <TableCell align="right">Utility Savings</TableCell>
            <TableCell align="right">Demand Savings</TableCell>
            <TableCell align="right">Capacity Savings</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row, idx) => (
            <TableRow key={row.year} sx={{ backgroundColor: idx % 2 ? 'action.hover' : 'inherit' }}>
              <TableCell>{row.year}</TableCell>
              <TableCell align="right">{fmt(row.utility_savings)}</TableCell>
              <TableCell align="right">{fmt(row.demand_savings)}</TableCell>
              <TableCell align="right">{fmt(row.capacity_savings)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

