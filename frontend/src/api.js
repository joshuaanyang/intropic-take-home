// Every call to the backend goes through here.
// Returns { ok, body } and never throws, so each screen can show a
// plain message when something fails.
async function request(path, options) {
  try {
    const response = await fetch(path, options);
    const body = await response.json().catch(() => null);
    return { ok: response.ok, status: response.status, body };
  } catch {
    return { ok: false, status: 0, body: { detail: "Cannot reach the server. Is it running?" } };
  }
}

export const getMeta = () => request("/api/meta");
export const getPortfolios = () => request("/api/portfolios");
export const getPortfolio = (id) => request(`/api/portfolios/${encodeURIComponent(id)}`);
export const getPosition = (id, instrument) =>
  request(`/api/portfolios/${encodeURIComponent(id)}/positions/${encodeURIComponent(instrument)}`);

export function uploadTrades(file) {
  const form = new FormData();
  form.append("file", file);
  return request("/api/imports", { method: "POST", body: form });
}

// Money arrives from the API as an exact decimal string such as "1280.00".
// It is formatted as text. It is never turned into a JavaScript number,
// because that would bring back floating-point error.
export function gbp(value) {
  if (value === null || value === undefined) return "unavailable";
  const negative = value.startsWith("-");
  const [whole, pence] = value.replace("-", "").split(".");
  const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ",");
  return `${negative ? "-" : ""}£${grouped}.${pence}`;
}
