import { useEffect, useState } from "react";
import { getPortfolio, getPortfolios, gbp } from "./api.js";

export default function PortfolioView({ portfolioId, onSelectPortfolio, onOpenPosition }) {
  const [portfolios, setPortfolios] = useState([]);
  const [summary, setSummary] = useState(null);
  const [problem, setProblem] = useState(null);

  // Fill the dropdown once.
  useEffect(() => {
    getPortfolios().then((result) => {
      if (result.ok) setPortfolios(result.body);
      else setProblem(result.body?.detail ?? "Could not load portfolios.");
    });
  }, []);

  // Load the summary whenever a different portfolio is chosen.
  useEffect(() => {
    setSummary(null);
    setProblem(null);
    if (!portfolioId) return;
    getPortfolio(portfolioId).then((result) => {
      if (result.ok) setSummary(result.body);
      else setProblem(result.body?.detail ?? "Could not load this portfolio.");
    });
  }, [portfolioId]);

  return (
    <section>
      <h2>Portfolio</h2>
      <label htmlFor="portfolio-select">Portfolio </label>
      <select id="portfolio-select" value={portfolioId} onChange={(event) => onSelectPortfolio(event.target.value)}>
        <option value="">Choose a portfolio</option>
        {portfolios.map((portfolio) => (
          <option key={portfolio.portfolio_id} value={portfolio.portfolio_id}>
            {portfolio.portfolio_id} · {portfolio.name}
          </option>
        ))}
      </select>

      {problem && <p className="banner bad">{problem}</p>}
      {summary && summary.positions.length === 0 && (
        <p className="banner">No trades have been imported for this portfolio yet. Upload a trade file first.</p>
      )}
      {summary && summary.positions.length > 0 && (
        <>
          {summary.unavailable.length > 0 && (
            <p className="banner bad">
              Totals are unavailable because {summary.unavailable.join(", ")} cannot be valued. See the row for the
              reason.
            </p>
          )}
          <div className="tiles">
            <div className="tile">
              <span>Holdings market value</span>
              <strong>{gbp(summary.market_value_gbp)}</strong>
            </div>
            <div className="tile">
              <span>Cumulative P&amp;L</span>
              <strong>{gbp(summary.pnl_gbp)}</strong>
            </div>
          </div>
          <p className="hint">
            {summary.trade_count} trades on or before {summary.as_of}. Totals are summed before rounding, so they can
            differ from the rows by a penny or two. Select an instrument to see its trades.
          </p>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Instrument</th>
                  <th className="num">Quantity</th>
                  <th className="num">Price</th>
                  <th>Price date</th>
                  <th className="num">FX to GBP</th>
                  <th>FX date</th>
                  <th className="num">Market value</th>
                  <th className="num">P&amp;L</th>
                </tr>
              </thead>
              <tbody>
                {summary.positions.map((position) => (
                  <tr key={position.instrument_id}>
                    <td>
                      <button className="link" onClick={() => onOpenPosition(position.instrument_id)}>
                        {position.ticker}
                      </button>{" "}
                      {position.name} <span className="hint">{position.currency}</span>{" "}
                      {position.closed && <span className="pill">closed</span>}
                    </td>
                    <td className="num">{position.quantity}</td>
                    <td className="num">{position.price ?? "none"}</td>
                    <td>
                      {position.price_date ?? "none"}{" "}
                      {position.price_carried_forward && <span className="pill warn">carried forward</span>}
                    </td>
                    <td className="num">{position.fx_rate ?? "none"}</td>
                    <td>{position.fx_date ?? "none"}</td>
                    <td className="num">{position.error ? "unavailable" : gbp(position.market_value_gbp)}</td>
                    <td className="num">{position.error ? position.error : gbp(position.pnl_gbp)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
