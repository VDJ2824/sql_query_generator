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
