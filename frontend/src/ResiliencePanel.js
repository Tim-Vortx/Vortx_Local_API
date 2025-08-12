import React from 'react';
import { Box, Typography } from '@mui/material';

export default function ResiliencePanel({ data }) {
  if (!data) return null;
  return (
    <Box sx={{ mt: 2 }}>
      <Typography variant="subtitle1">Resilience</Typography>
      {data.outage_duration_hours != null && (
        <Typography>
          Outage Duration: <b>{data.outage_duration_hours}</b> hrs
        </Typography>
      )}
      {data.percent_load_served != null && (
        <Typography>
          % Load Served: <b>{Number(data.percent_load_served).toLocaleString(undefined, { maximumFractionDigits: 1 })}</b>
        </Typography>
      )}
    </Box>
  );
}

