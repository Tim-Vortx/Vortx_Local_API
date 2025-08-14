import React, { createContext, useContext, useState } from 'react';

// Create a context for the selected tariff
const TariffContext = createContext();

export const TariffProvider = ({ children }) => {
  const [selectedTariff, setSelectedTariff] = useState(null);

  return (
    <TariffContext.Provider value={{ selectedTariff, setSelectedTariff }}>
      {children}
    </TariffContext.Provider>
  );
};

export const useTariff = () => useContext(TariffContext);
