// Monte React, le provider KPI unique et les styles globaux.
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { KpiSocketProvider } from "./hooks/useKpiSocket";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><KpiSocketProvider><App /></KpiSocketProvider></React.StrictMode>,
);