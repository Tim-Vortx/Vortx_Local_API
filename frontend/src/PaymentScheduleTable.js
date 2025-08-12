import React from 'react';
import { Table, TableHead, TableBody, TableRow, TableCell, Typography } from '@mui/material';

function fmt(v) {
  if (v === undefined || v === null) return '—';
  return `$${Number(v).toLocaleString(undefined, { maximumFractionDigits: 0 })}`;
}

export default function PaymentScheduleTable({ data = [] }) {
  if (!data.length) return null;
  return (
    <>
      <Typography variant="subtitle1" sx={{ mt: 2 }}>Developer Payments</Typography>
      <Table size="small">
        <TableHead>
          <TableRow>
            <TableCell>Year</TableCell>
            <TableCell align="right">Payment</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {data.map((row, idx) => (
            <TableRow key={row.year} sx={{ backgroundColor: idx % 2 ? 'action.hover' : 'inherit' }}>
              <TableCell>{row.year}</TableCell>
              <TableCell align="right">{fmt(row.amount)}</TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </>
  );
}

