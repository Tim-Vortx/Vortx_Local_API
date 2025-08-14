import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { TariffProvider } from './TariffContext';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <TariffProvider>
    <App />
  </TariffProvider>
);
