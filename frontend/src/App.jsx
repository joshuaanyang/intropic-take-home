import { useEffect, useState } from "react";
import { getMeta } from "./api.js";
import UploadView from "./UploadView.jsx";
import PortfolioView from "./PortfolioView.jsx";
import PositionView from "./PositionView.jsx";

// One page, three views. `view` says which one is showing:
//   { name: "upload" }
//   { name: "portfolio" }
//   { name: "position", instrumentId }
export default function App() {
  const [meta, setMeta] = useState(null);
  const [view, setView] = useState({ name: "upload" });
  const [portfolioId, setPortfolioId] = useState("");

  useEffect(() => {
    getMeta().then((result) => result.ok && setMeta(result.body));
  }, []);

  const onPortfolioTab = view.name !== "upload";

  return (
    <div className="page">
      <header>
        <h1>Portfolio Investigation Tool</h1>
        {meta && (
          <p className="meta">
            Valued as of {meta.as_of} · dataset {meta.dataset_id}
          </p>
        )}
        <nav>
          <button className={!onPortfolioTab ? "tab on" : "tab"} onClick={() => setView({ name: "upload" })}>
            Upload
          </button>
          <button className={onPortfolioTab ? "tab on" : "tab"} onClick={() => setView({ name: "portfolio" })}>
            Portfolio
          </button>
        </nav>
      </header>

      {view.name === "upload" && <UploadView />}
      {view.name === "portfolio" && (
        <PortfolioView
          portfolioId={portfolioId}
          onSelectPortfolio={setPortfolioId}
          onOpenPosition={(instrumentId) => setView({ name: "position", instrumentId })}
        />
      )}
      {view.name === "position" && (
        <PositionView
          portfolioId={portfolioId}
          instrumentId={view.instrumentId}
          onBack={() => setView({ name: "portfolio" })}
        />
      )}
    </div>
  );
}
