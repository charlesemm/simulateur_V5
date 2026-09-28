// Monte React et les styles globaux.
// Le provider KPI est monté dans App.tsx, à l'intérieur d'AuthProvider :
// il lit le jeton pour authentifier la connexion Socket.IO.
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { initialiserTheme } from "./hooks/useTheme";
// Ordre voulu : les jetons d'abord, les composants « ui- » en dernier.
import "./styles/tokens.css";
import "./styles/base.css";
import "./styles/shell.css";
import "./styles/patterns.css";
import "./styles/saisie.css";
import "./styles/supervision.css";
import "./styles/administration.css";
import "./styles/components.css";

// Le thème se pose avant le premier rendu : pas d'éclair blanc en mode sombre.
initialiserTheme();

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode><App /></React.StrictMode>,
);
