class SqlIntelligenceClient {
  constructor({
    baseUrl = process.env.SQL_SERVICE_URL,
    apiKey = process.env.SQL_SERVICE_API_KEY,
    fetchImpl = global.fetch,
  } = {}) {
    this.baseUrl = baseUrl ? baseUrl.replace(/\/$/, "") : "";
    this.apiKey = apiKey || "";
    this.fetchImpl = fetchImpl;
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

    const response = await this.fetchImpl(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-internal-api-key": this.apiKey,
      },
      body: JSON.stringify(payload),
    });

    const body = await this.parseJson(response);
    if (!response.ok) {
      const error = new Error(body.message || body.detail || "SQL intelligence service request failed.");
      error.statusCode = response.status;
      error.serviceResponse = body;
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
}

module.exports = SqlIntelligenceClient;
