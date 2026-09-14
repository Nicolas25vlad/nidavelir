import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";

import { App } from "./App";
import { AuthGate } from "./components/AuthGate";
import "./styles.css";
import "./review.css";

const root = document.getElementById("root");

if (!root) {
  throw new Error("Nidavelir root element was not found");
}

createRoot(root).render(
  <StrictMode>
    <AuthGate>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </AuthGate>
  </StrictMode>,
);
