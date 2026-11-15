import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { AuthGate } from "./components/AuthGate";
import "./styles/tokens.css";
import "./styles/app.css";
import "./styles/viewer.css";
import "./styles/plan.css";
import "./styles/ask.css";
import "./styles/responsive.css";
import "./styles/login.css";

const root = document.getElementById("root");
if (!root) throw new Error("#root missing from index.html");

createRoot(root).render(
  <StrictMode>
    <AuthGate>
      <App />
    </AuthGate>
  </StrictMode>,
);
