import React, { useState, useEffect } from "react";
import { Box, TextField, Button } from "@mui/material";

function LocationInput({ value, onValueCommit, onFindTariffs }) {
  const [local, setLocal] = useState(value || "");
  useEffect(() => {
    setLocal(value || "");
  }, [value]);

  return (
    <Box display="flex" gap={1} alignItems="start">
      <TextField
        label="Address or Zip Code"
        fullWidth
        value={local}
        onChange={(e) => setLocal(e.target.value)}
        onBlur={() => onValueCommit?.(local)}
      />
      <Button variant="outlined" onClick={() => onFindTariffs?.(local)} style={{ alignSelf: 'center' }}>
        Find Tariffs
      </Button>
    </Box>
  );
}

export default LocationInput;
