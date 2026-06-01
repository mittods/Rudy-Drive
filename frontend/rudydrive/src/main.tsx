import React from 'react';
import ReactDOM from 'react-dom/client';
import { ChakraProvider, defaultSystem } from '@chakra-ui/react';
import App from './App';
import { BrowserRouter } from 'react-router-dom';
import { Toaster } from './components/ui/toaster';

ReactDOM.createRoot(document.getElementById('root') as HTMLElement).render(
  <React.StrictMode>
    <ChakraProvider value={defaultSystem}>
      <BrowserRouter>
        <App />
        <Toaster />
      </BrowserRouter>
    </ChakraProvider>
  </React.StrictMode>
);