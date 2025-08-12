import React from 'react';
import { Table, TableHead, TableBody, TableRow, TableCell, Typography } from '@mui/material';

function format(val, label) {
  if (val === undefined || val === null) return '—';
  if (label.toLowerCase().includes('payback')) {
    return Number(val).toLocaleString(undefined, { maximumFractionDigits: 1 });
  }
  return `$${Number(val).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function EconomicsTable({ data }) {
  if (!data) return null;
  const rows = [
    { label: 'Upfront Cost', year1: data.upfront_cost, lifetime: data.upfront_cost },
    { label: 'Net Savings', year1: data.net_savings, lifetime: data.net_savings },
    { label: 'NPV', year1: data.npv, lifetime: data.npv },
    { label: 'Payback (yrs)', year1: data.payback, lifetime: data.payback },
    { label: 'Lifecycle Cost', year1: data.lcc, lifetime: data.lcc },
  ];
  return (
    <>
      <Typography variant="subtitle1" sx={{ mt: 2 }}>Economics</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell />
            <TableCell align="right">Year 1</TableCell>
            <TableCell align="right">Lifetime</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {rows.map((r, idx) => (
            <TableRow key={r.label} sx={{ backgroundColor: idx % 2 ? 'action.hover' : 'inherit' }}>
              <TableCell>{r.label}</TableCell>
              <TableCell align="right">{format(r.year1, r.label)}</TableCell>
              <TableCell align="right">{format(r.lifetime, r.label)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

