import React from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import AuthGate from "./AuthGate.jsx";
import "./index.css";
import { applyTheme, getInitialTheme } from "./theme.js";

applyTheme(getInitialTheme());

createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <AuthGate><App /></AuthGate>
    </BrowserRouter>
  </React.StrictMode>
);
