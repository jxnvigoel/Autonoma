import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import { ThemeProvider } from "./context/ThemeContext";
import { ConversationProvider } from "./context/ConversationContext";
import "./index.css";

const rootElement = document.getElementById("root");

if (rootElement) {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ThemeProvider>
        <ConversationProvider>
          <App />
        </ConversationProvider>
      </ThemeProvider>
    </React.StrictMode>
  );
}

