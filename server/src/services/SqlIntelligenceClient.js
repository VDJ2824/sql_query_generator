class SqlIntelligenceClient {
  constructor({
    baseUrl = process.env.SQL_SERVICE_URL,
    apiKey = process.env.SQL_SERVICE_API_KEY,
    fetchImpl = global.fetch,
    timeoutMs = Number.parseInt(process.env.SQL_SERVICE_TIMEOUT_MS || "45000", 10),
    maxRetries = Number.parseInt(process.env.SQL_SERVICE_MAX_RETRIES || "2", 10),
    retryDelayMs = Number.parseInt(process.env.SQL_SERVICE_RETRY_DELAY_MS || "1500", 10),
    sleep = (delayMs) => new Promise((resolve) => setTimeout(resolve, delayMs)),
  } = {}) {
    this.baseUrl = baseUrl ? baseUrl.replace(/\/$/, "") : "";
    this.apiKey = apiKey || "";
    this.fetchImpl = fetchImpl;
    this.timeoutMs = Number.isFinite(timeoutMs) ? timeoutMs : 45000;
    this.maxRetries = Number.isFinite(maxRetries) ? maxRetries : 2;
    this.retryDelayMs = Number.isFinite(retryDelayMs) ? retryDelayMs : 1500;
    this.sleep = sleep;
  }

  async schema(payload) {
    return this.post("/internal/schema", payload);
  }

  async generate(payload) {
    return this.post("/internal/generate", payload);
  }

  async preview(payload) {
    return this.post("/internal/preview", payload);
  }

  async execute(payload) {
    return this.post("/internal/execute", payload);
  }

  async post(path, payload) {
    if (!this.baseUrl || !this.apiKey) {
      const error = new Error("SQL intelligence service is not configured.");
      error.statusCode = 503;
      throw error;
    }

    const attempts = Math.max(1, this.maxRetries + 1);
    let lastError;

    for (let attempt = 1; attempt <= attempts; attempt += 1) {
      try {
        return await this.requestOnce(path, payload, attempt);
      } catch (error) {
        lastError = error;
        if (attempt >= attempts || !this.isRetryable(error)) {
          throw error;
        }
        await this.sleep(this.retryDelayMs * attempt);
      }
    }

    throw lastError;
  }

  async requestOnce(path, payload, attempt) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

    let response;
    try {
      response = await this.fetchImpl(`${this.baseUrl}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-internal-api-key": this.apiKey,
        },
        body: JSON.stringify(payload),
        signal: controller.signal,
      });
    } catch (error) {
      const wrappedError = new Error(
        error.name === "AbortError"
          ? "SQL intelligence service request timed out."
          : "SQL intelligence service is unreachable.",
      );
      wrappedError.statusCode = 503;
      wrappedError.cause = error;
      wrappedError.attempt = attempt;
      throw wrappedError;
    } finally {
      clearTimeout(timeout);
    }

    const body = await this.parseJson(response);
    if (!response.ok) {
      const error = new Error(body.message || body.detail || "SQL intelligence service request failed.");
      error.statusCode = response.status;
      error.serviceResponse = body;
      error.attempt = attempt;
      throw error;
    }
    return body;
  }

  async parseJson(response) {
    try {
      return await response.json();
    } catch (error) {
      return {};
    }
  }

  isRetryable(error) {
    return [429, 502, 503, 504].includes(error.statusCode);
  }
}

module.exports = SqlIntelligenceClient;
