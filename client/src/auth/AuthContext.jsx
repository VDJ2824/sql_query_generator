import {createContext, useContext, useEffect, useMemo, useState} from "react";
import {ApiClient} from "../services/ApiClient";
import {normalizeUser} from "../utils/roles";

const AuthContext = createContext(null);

export function AuthProvider({children}) {
  const [user, setUser] = useState(() => {
    const stored = sessionStorage.getItem("mern_sql_user");
    return stored ? normalizeUser(JSON.parse(stored)) : null;
  });
  const [loading, setLoading] = useState(false);

  async function login(email, password) {
    setLoading(true);
    try {
      return await ApiClient.login({email, password});
    } finally {
      setLoading(false);
    }
  }

  async function verifyLoginOtp(email, otp) {
    setLoading(true);
    try {
      const response = await ApiClient.verifyLoginOtp({email, otp});
      const freshUser = normalizeUser(response.user);
      sessionStorage.setItem("mern_sql_token", response.accessToken);
      sessionStorage.setItem("mern_sql_user", JSON.stringify(freshUser));
      setUser(freshUser);
      return freshUser;
    } finally {
      setLoading(false);
    }
  }

  function logout() {
    sessionStorage.removeItem("mern_sql_token");
    sessionStorage.removeItem("mern_sql_user");
    setUser(null);
  }

  useEffect(() => {
    ApiClient.onUnauthorized(logout);
    const token = sessionStorage.getItem("mern_sql_token");
    if (!token) return;
    ApiClient.me()
      .then((response) => {
        const freshUser = normalizeUser(response.user);
        setUser(freshUser);
        sessionStorage.setItem("mern_sql_user", JSON.stringify(freshUser));
      })
      .catch(() => logout());
  }, []);

  async function signup(payload) {
    setLoading(true);
    try {
      return await ApiClient.register(payload);
    } finally {
      setLoading(false);
    }
  }

  const value = useMemo(
    () => ({user, loading, login, logout, signup, verifyLoginOtp}),
    [user, loading],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
