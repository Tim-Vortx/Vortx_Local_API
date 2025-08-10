import React, { useState } from 'react';
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

// generate hourly data from Aug 5 to Aug 8, 2025
const start = new Date('2025-08-05T00:00:00').getTime();
const hours = 24 * 4;
const defaultData = Array.from({ length: hours }, (_, i) => {
  const t = new Date(start + i * 3600 * 1000);
  const h = t.getHours();
  const load = 600 + 600 * Math.max(0, Math.sin(((h - 6) / 24) * Math.PI * 2));
  const solar = h >= 6 && h <= 18 ? -800 * Math.sin(((h - 6) / 12) * Math.PI) : 0;
  const bess =
    h >= 0 && h <= 5 ? 200 : h >= 12 && h <= 15 ? -200 : 0;
  const utility = load + bess + solar;
  return { timestamp: t.getTime(), load, solar, bess, utility };
});

// weather mini-chart data
const defaultWeatherData = defaultData.map((d, idx) => {
  const ghi = 500 + 200 * Math.sin((idx / hours) * Math.PI * 2);
  const temp = 25 + 10 * Math.sin((idx / hours) * Math.PI * 4 + 1);
  const wind = 5 + 2 * Math.sin((idx / hours) * Math.PI * 8 + 2);
  return { timestamp: d.timestamp, ghi, temp, wind };
});

const defaultEvents = [
  { date: new Date('2025-08-06T12:00:00').getTime(), color: '#EF5350', count: 1 },
  { date: new Date('2025-08-07T12:00:00').getTime(), color: '#FFCC80', count: 1 },
  { date: new Date('2025-08-08T12:00:00').getTime(), color: '#FFCC80', count: 1 },
];

export default function PowerChart({ data = defaultData }) {
  const [show, setShow] = useState({
    utility: true,
    solar: true,
    bess: true,
    load: true,
    missing: false,
    alarms: false,
  });
  const [range, setRange] = useState({
    startIndex: 0,
    endIndex: data.length - 1,
  });

  const handleLegend = (key) => (e) => {
    setShow({ ...show, [key]: e.target.checked });
  };

  const resetZoom = () => {
    setRange({ startIndex: 0, endIndex: data.length - 1 });
  };

  const filtered = data.slice(range.startIndex, range.endIndex + 1);
  const startTime = filtered[0]?.timestamp || 0;
  const endTime = filtered[filtered.length - 1]?.timestamp || 0;
  const weatherData = data === defaultData ? defaultWeatherData : [];
  const events = data === defaultData ? defaultEvents : [];

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
                tickFormatter={(t) => new Date(t).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}
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
              {show.utility && (
                <Area
                  type="monotone"
                  dataKey="utility"
                  stroke="#000000"
                  fill="#DDDDDD"
                  stackId="1"
                />
              )}
              {show.solar && (
                <Area
                  type="monotone"
                  dataKey="solar"
                  stroke="#388E3C"
                  fill="#C8E6C9"
                  stackId="1"
                />
              )}
              {show.bess && (
                <Area
                  type="monotone"
                  dataKey="bess"
                  stroke="#1976D2"
                  fill="#BBDEFB"
                  stackId="1"
                />
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
              control={<Checkbox checked={show.utility} onChange={handleLegend('utility')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#DDDDDD', mr: 1 }} />Utility</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.bess} onChange={handleLegend('bess')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#BBDEFB', mr: 1 }} />BESS</Box>}
            />
            <FormControlLabel
              control={<Checkbox checked={show.solar} onChange={handleLegend('solar')} />}
              label={<Box display="flex" alignItems="center"><Box sx={{ width: 16, height: 10, backgroundColor: '#C8E6C9', mr: 1 }} />Solar_PV</Box>}
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

