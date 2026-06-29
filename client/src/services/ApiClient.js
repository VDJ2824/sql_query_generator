import axios from "axios";

const http = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:5000/api",
});

let unauthorizedHandler = null;

function authHeader() {
  const token = sessionStorage.getItem("mern_sql_token");
  return token ? {Authorization: `Bearer ${token}`} : {};
}

async function request(config) {
  try {
    const response = await http.request({
      ...config,
      headers: {
        ...authHeader(),
        ...(config.headers || {}),
      },
    });
    return response.data;
  } catch (error) {
    const status = error.response?.status;
    const message = error.response?.data?.message || "Request failed. Please try again.";
    if (status === 401 && unauthorizedHandler) {
      unauthorizedHandler();
    }
    const safeError = new Error(message);
    safeError.status = status;
    throw safeError;
  }
}

export const ApiClient = {
  onUnauthorized(handler) {
    unauthorizedHandler = handler;
  },

  register(payload) {
    return request({method: "POST", url: "/auth/register", data: payload});
  },

  login(payload) {
    return request({method: "POST", url: "/auth/login", data: payload});
  },

  verifyLoginOtp(payload) {
    return request({method: "POST", url: "/auth/verify-login-otp", data: payload});
  },

  me() {
    return request({method: "GET", url: "/auth/me"});
  },

  listDatabaseConnections() {
    return request({method: "GET", url: "/database-connections"});
  },

  listDatabaseTables(databaseConnectionId) {
    return request({method: "GET", url: `/database-connections/${databaseConnectionId}/tables`});
  },

  createDatabaseConnection(payload) {
    return request({method: "POST", url: "/database-connections", data: payload});
  },

  selectQuery(databaseConnectionId, payload) {
    return request({method: "POST", url: "/queries/select", data: payload});
  },

  generateQueryOptions(payload) {
    return request({method: "POST", url: "/queries/generate", data: payload});
  },

  previewSelectedQuery(payload) {
    return request({method: "POST", url: "/queries/preview", data: payload});
  },

  executeSelectedQuery(payload) {
    return request({method: "POST", url: "/queries/execute", data: payload});
  },

  history() {
    return request({method: "GET", url: "/history"});
  },

  auditLogs() {
    return request({method: "GET", url: "/admin/audit-logs"});
  },
};
