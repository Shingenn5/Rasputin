import React from "react";
import { createRoot } from "react-dom/client";
import "./styles/bootstrap.scss";
import "./styles/rasputin.css";
import { AppProviders } from "./app/AppProviders.jsx";
import { App } from "./app/App.jsx";

createRoot(document.getElementById("root")).render(
  <AppProviders>
    <App />
  </AppProviders>,
);
