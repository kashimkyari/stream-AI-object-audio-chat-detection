import React from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import { Analytics } from "@vercel/analytics/react"

const root = createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
    <Analytics />
  </React.StrictMode>
);