import React from "react";
import { Routes, Route} from "react-router-dom";
import FileSys from "./pages/fileSys/FileSys";

const App: React.FC = () => {
  return (
    <Routes>
      {/* Rutas públicas */}
      <Route path="/" element={<FileSys/>} />
    </Routes> 
  );
};

export default App;
