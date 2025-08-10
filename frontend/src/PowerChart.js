import React, { useState, useEffect } from 'react';
import {
  Box,
  Typography,
  Select,
  MenuItem,
  IconButton,
  Button,
  FormGroup,
  FormControlLabel,
  Checkbox,
} from '@mui/material';
import ShareIcon from '@mui/icons-material/Share';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowDropDownIcon from '@mui/icons-material/ArrowDropDown';
import {
  AreaChart,
  Area,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ReferenceLine,
  ResponsiveContainer,
  Brush,
} from 'recharts';

const supplyKeys = [
  { key: 'utility_to_load', stroke: '#000000', fill: '#DDDDDD' },
  { key: 'solar_to_load', stroke: '#388E3C', fill: '#C8E6C9' },
  { key: 'bess_to_load', stroke: '#1976D2', fill: '#BBDEFB' },
  { key: 'diesel_to_load', stroke: '#F57C00', fill: '#FFE0B2' },
  { key: 'ng_to_load', stroke: '#8D6E63', fill: '#D7CCC8' },
];

const overlayKeys = [
  { key: 'solar_to_bess', stroke: '#388E3C', fill: '#C8E6C9' },
  { key: 'utility_to_bess', stroke: '#000000', fill: '#DDDDDD' },
  { key: 'solar_export', stroke: '#388E3C', fill: '#C8E6C9' },
  { key: 'bess_export', stroke: '#1976D2', fill: '#BBDEFB' },
  { key: 'diesel_export', stroke: '#F57C00', fill: '#FFE0B2' },
  { key: 'ng_export', stroke: '#8D6E63', fill: '#D7CCC8' },
];

const events = [];

export default function PowerChart({ data = [] }) {
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
    missing: false,
    alarms: false,
  });
  const [range, setRange] = useState({
    startIndex: 0,
    endIndex: Math.max(0, data.length - 1),
  });

  useEffect(() => {
    setRange({ startIndex: 0, endIndex: Math.max(0, data.length - 1) });
  }, [data]);

  const handleLegend = (key) => (e) => {
    setShow({ ...show, [key]: e.target.checked });
  };

  const resetZoom = () => {
    setRange({ startIndex: 0, endIndex: Math.max(0, data.length - 1) });
  };

  const filtered = data.slice(range.startIndex, range.endIndex + 1);

  const startTime = data[range.startIndex]?.timestamp || 0;
  const endTime = data[range.endIndex]?.timestamp || 0;
  const ticks =
    startTime && endTime
      ? Array.from({ length: 4 }, (_, i) => startTime + (i * (endTime - startTime)) / 3)
      : [];

  const weatherData = data;

  return (
    <Box sx={{ width: '100%', height: 400 }}>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={1}>
        <Box display="flex" alignItems="center" gap={1}>
          <Typography variant="subtitle1">Power</Typography>
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          <Select size="small" value={7}>
            <MenuItem value={7}>Last 7 Days</MenuItem>
          </Select>
          <IconButton size="small"><ShareIcon fontSize="small" /></IconButton>
        </Box>
        <Box flexGrow={1} mx={2}>
          <ResponsiveContainer width="100%" height={40}>
            <LineChart data={weatherData} margin={{ top: 5, bottom: 5 }}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} />
              <Line type="monotone" dataKey="ghi" stroke="#FFEB3B" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="temp" stroke="#9E9E9E" dot={false} strokeWidth={1} />
              <Line type="monotone" dataKey="wind" stroke="#2196F3" dot={false} strokeWidth={1} />
              <XAxis hide dataKey="timestamp" type="number" domain={[startTime, endTime]} />
              <YAxis hide />
            </LineChart>
          </ResponsiveContainer>
        </Box>
        <Box display="flex" alignItems="center" gap={1}>
          <Button endIcon={<ArrowDropDownIcon />}>Total: 16.63 MWh</Button>
          <Button variant="outlined" startIcon={<DownloadIcon />}>Download</Button>
        </Box>
      </Box>

      <Box display="flex" height={300}>
        <Box flexGrow={1}>
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={filtered} margin={{ top: 10, right: 20, bottom: 30, left: 20 }}>
              <CartesianGrid stroke="#eee" verticalLines={true} />
              <XAxis
                dataKey="timestamp"
                type="number"
                domain={[startTime, endTime]}
                tickFormatter={(t) =>
                  new Date(t).toLocaleDateString('en-US', {
                    month: 'short',
                    day: 'numeric',
                    year: 'numeric',
                  })
                }
                ticks={ticks}
              />
              <YAxis
                label={{ value: 'kW', angle: -90, position: 'insideLeft' }}
                domain={[-600, 1200]}
                ticks={[-600, 0, 600, 1200]}
              />
              <Tooltip
                formatter={(value, name) => [`${value.toFixed(0)} kW`, name]}
                labelFormatter={(t) => new Date(t).toLocaleString()}
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
              <Brush
                dataKey="timestamp"
                height={20}
                stroke="#8884d8"
                startIndex={range.startIndex}
                endIndex={range.endIndex}
                onChange={(e) => {
                  if (e && e.startIndex !== undefined) {
                    setRange({ startIndex: e.startIndex, endIndex: e.endIndex });
                  }
                }}
              />
            </AreaChart>
          </ResponsiveContainer>
          <Box position="relative" mt={1} height={20} sx={{ backgroundColor: '#eee' }}>
            {events.map((ev, idx) => {
              const pos =
                ((ev.date - startTime) / (endTime - startTime)) * 100;
              return (
                <Box key={idx} position="absolute" left={`calc(${pos}% - 10px)`} top={2}>
                  <Box
                    sx={{
                      width: 16,
                      height: 16,
                      borderRadius: '50%',
                      backgroundColor: ev.color,
                      color: '#000',
                      fontSize: 10,
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                    }}
                  >
                    {ev.count}
                  </Box>
                </Box>
              );
            })}
          </Box>
          {range.startIndex !== 0 || range.endIndex !== data.length - 1 ? (
            <Box textAlign="right">
              <Button size="small" onClick={resetZoom} sx={{ mt: 1 }}>
                Cancel Zoom
              </Button>
            </Box>
          ) : null}
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
            <FormControlLabel
              control={<Checkbox checked={show.missing} onChange={handleLegend('missing')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#FFCC80', mr: 1 }} />Missing Data</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.alarms} onChange={handleLegend('alarms')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#EF5350', mr: 1 }} />Alarms</Box>}
            />
          </FormGroup>
        </Box>
      </Box>
    </Box>
  );
}

