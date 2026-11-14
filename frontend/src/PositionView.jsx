import { useEffect, useState } from "react";
import { getPosition, gbp } from "./api.js";

export default function PositionView({ portfolioId, instrumentId, onBack }) {
  const [position, setPosition] = useState(null);
  const [problem, setProblem] = useState(null);

  useEffect(() => {
    getPosition(portfolioId, instrumentId).then((result) => {
      if (result.ok) setPosition(result.body);
      else setProblem(result.body?.detail ?? "Could not load this position.");
    });
  }, [portfolioId, instrumentId]);

  return (
    <section>
      <button className="link" onClick={onBack}>
        ← Back to {portfolioId}
      </button>
      {problem && <p className="banner bad">{problem}</p>}
      {position && (
        <>
          <h2>
            {position.ticker} · {position.name} <span className="hint">{position.currency}</span>{" "}
            {position.closed && <span className="pill">closed</span>}
          </h2>
          {position.error && <p className="banner bad">This position cannot be valued: {position.error}.</p>}

          <h3>Trades, in execution order</h3>
          <div className="scroll">
            <table>
              <thead>
                <tr>
                  <th>Trade ID</th>
                  <th>Time (UTC)</th>
                  <th>Side</th>
                  <th className="num">Quantity</th>
                  <th className="num">Price ({position.currency})</th>
                  <th className="num">FX on trade day</th>
                  <th>FX date</th>
                  <th className="num">Signed cost</th>
                  <th className="num">Running quantity</th>
                </tr>
              </thead>
              <tbody>
                {position.trades.map((trade) => (
                  <tr key={trade.trade_id}>
                    <td>{trade.trade_id}</td>
                    <td>{trade.timestamp}</td>
                    <td>{trade.side}</td>
                    <td className="num">{trade.quantity}</td>
                    <td className="num">{trade.price}</td>
                    <td className="num">{trade.fx_rate}</td>
                    <td>{trade.fx_date}</td>
                    <td className="num">{gbp(trade.signed_cost_gbp)}</td>
                    <td className="num">{trade.running_quantity}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {!position.error && (
            <>
              <h3>How the figures are produced</h3>
              <dl className="explain">
                <dt>Net trade cost</dt>
                <dd>Sum of the signed cost column (buys add, sells subtract) = {gbp(position.net_cost_gbp)}</dd>
                <dt>Market value</dt>
                <dd>
                  {position.quantity} × {position.price ?? "no price"} (price dated {position.price_date ?? "none"}
                  {position.price_carried_forward ? ", carried forward" : ""}) × {position.fx_rate ?? "no rate"} (FX
                  dated {position.fx_date ?? "none"}) = {gbp(position.market_value_gbp)}
                </dd>
                <dt>Cumulative P&amp;L</dt>
                <dd>
                  Market value − net trade cost = {gbp(position.pnl_gbp)}
                </dd>
              </dl>
              <p className="hint">
                Each cost row is rounded for display. The totals are calculated from unrounded values.
              </p>
            </>
          )}
        </>
      )}
    </section>
  );
}
