import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { Provider } from "react-redux";
import { store } from "./store/store";
import "./i18n";
import "leaflet/dist/leaflet.css";
import "./index.css";
import App from "./App";
import ErrorBoundary from "./components/common/ErrorBoundary";
createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <ErrorBoundary>
      <Provider store={store}>
        <App />
      </Provider>
    </ErrorBoundary>
  </StrictMode>
);
