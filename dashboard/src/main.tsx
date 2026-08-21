// Monte React et les styles globaux.
// Le provider KPI est monté dans App.tsx, à l'intérieur d'AuthProvider :
// il lit le jeton pour authentifier la connexion Socket.IO.
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
