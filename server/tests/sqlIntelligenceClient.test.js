const SqlIntelligenceClient = require("../src/services/SqlIntelligenceClient");

function response(body = {}, ok = true, status = 200) {
  return {
    ok,
    status,
    async json() {
      return body;
    },
  };
}

test("SQL intelligence client sends the internal API key header", async () => {
  const fetchImpl = jest.fn().mockResolvedValue(response({queryOptions: []}));
  const client = new SqlIntelligenceClient({
    baseUrl: "http://sql-service.test",
    apiKey: "internal-test-key",
    fetchImpl,
  });

  await client.generate({prompt: "show tables"});

  expect(fetchImpl).toHaveBeenCalledWith(
    "http://sql-service.test/internal/generate",
    expect.objectContaining({
      method: "POST",
      headers: expect.objectContaining({
        "x-internal-api-key": "internal-test-key",
      }),
    }),
  );
});

test("SQL intelligence client refuses to call FastAPI without internal service configuration", async () => {
  const fetchImpl = jest.fn();
  const client = new SqlIntelligenceClient({baseUrl: "", apiKey: "", fetchImpl});

  await expect(client.generate({prompt: "show tables"})).rejects.toThrow("SQL intelligence service is not configured.");
  expect(fetchImpl).not.toHaveBeenCalled();
});

test("SQL intelligence client retries transient Render-style 502 responses", async () => {
  const fetchImpl = jest
    .fn()
    .mockResolvedValueOnce(response({}, false, 502))
    .mockResolvedValueOnce(response({allowedTables: []}));
  const client = new SqlIntelligenceClient({
    baseUrl: "http://sql-service.test",
    apiKey: "internal-test-key",
    fetchImpl,
    retryDelayMs: 1,
    sleep: jest.fn().mockResolvedValue(),
  });

  await expect(client.schema({})).resolves.toEqual({allowedTables: []});
  expect(fetchImpl).toHaveBeenCalledTimes(2);
});

test("SQL intelligence client does not retry permanent validation errors", async () => {
  const fetchImpl = jest.fn().mockResolvedValue(response({detail: "Invalid internal API key."}, false, 403));
  const client = new SqlIntelligenceClient({
    baseUrl: "http://sql-service.test",
    apiKey: "wrong-key",
    fetchImpl,
    sleep: jest.fn().mockResolvedValue(),
  });

  await expect(client.schema({})).rejects.toThrow("Invalid internal API key.");
  expect(fetchImpl).toHaveBeenCalledTimes(1);
});
