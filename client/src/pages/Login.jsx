import {useState} from "react";
import {useNavigate} from "react-router-dom";
import {useAuth} from "../auth/AuthContext";

export function Login() {
  const [mode, setMode] = useState("login");
  const [loginForm, setLoginForm] = useState({email: "", password: ""});
  const [otpForm, setOtpForm] = useState({email: "", otp: "", debugOtp: ""});
  const [signupForm, setSignupForm] = useState({
    username: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const {login, signup, loading, verifyLoginOtp} = useAuth();
  const navigate = useNavigate();

  async function handleLogin(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      const response = await login(loginForm.email, loginForm.password);
      setOtpForm({
        email: response.email || loginForm.email,
        otp: "",
        debugOtp: response.debugOtp || "",
      });
      setMessage(
        response.emailSent
          ? `We sent a one-time code to ${response.email}.`
          : "Email delivery is not configured in this environment. Use the local verification code shown below.",
      );
      setMode("otp");
    } catch (err) {
      setError(err.message || "Login failed.");
    }
  }

  async function handleVerifyOtp(event) {
    event.preventDefault();
    setError("");
    try {
      await verifyLoginOtp(otpForm.email, otpForm.otp);
      navigate("/");
    } catch (err) {
      setError(err.message || "Invalid or expired OTP.");
    }
  }

  async function handleSignup(event) {
    event.preventDefault();
    setError("");
    setMessage("");
    try {
      await signup(signupForm);
      setMessage("Signup successful. You can now log in.");
      setMode("login");
      setLoginForm({email: signupForm.email, password: signupForm.password});
    } catch (err) {
      setError(err.message || "Signup failed.");
    }
  }

  return (
    <main className="login-page">
      <section className="login-card wide-login-card">
        <p className="eyebrow">AI SQL Query Generator</p>
        <h1>{mode === "login" ? "Sign in to your SQL workspace" : "Create your SQL workspace"}</h1>
        <p className="muted">
          Generate, preview, and execute database queries from natural language.
          Sign-in is protected with a one-time email code, and every new account starts with standard user access.
        </p>

        <div className="tab-row">
          <button type="button" className={mode === "login" || mode === "otp" ? "" : "ghost-button"} onClick={() => setMode("login")}>Login</button>
          <button type="button" className={mode === "signup" ? "" : "ghost-button"} onClick={() => setMode("signup")}>Signup</button>
        </div>

        {mode === "login" && (
          <form onSubmit={handleLogin}>
            <label>
              Email
              <input
                type="email"
                autoComplete="email"
                value={loginForm.email}
                onChange={(event) => setLoginForm({...loginForm, email: event.target.value})}
              />
            </label>
            <label>
              Password
              <input
                type="password"
                autoComplete="current-password"
                value={loginForm.password}
                onChange={(event) => setLoginForm({...loginForm, password: event.target.value})}
              />
            </label>
            {error && <p className="error">{error}</p>}
            {message && <p className="notice">{message}</p>}
            <button type="submit" disabled={loading}>{loading ? "Signing in..." : "Login"}</button>
          </form>
        )}

        {mode === "otp" && (
          <form onSubmit={handleVerifyOtp}>
            <label>
              Email verification code
              <input
                inputMode="numeric"
                maxLength={6}
                value={otpForm.otp}
                onChange={(event) => setOtpForm({
                  ...otpForm,
                  otp: event.target.value.replace(/\D/g, "").slice(0, 6),
                })}
              />
            </label>
            {message && <p className="notice">{message}</p>}
            {otpForm.debugOtp && (
              <p className="notice">Local verification code: <strong>{otpForm.debugOtp}</strong></p>
            )}
            {error && <p className="error">{error}</p>}
            <div className="tab-row">
              <button type="submit" disabled={loading || otpForm.otp.length !== 6}>
                {loading ? "Verifying..." : "Verify and continue"}
              </button>
              <button
                type="button"
                className="ghost-button"
                onClick={() => {
                  setMode("login");
                  setOtpForm({email: "", otp: "", debugOtp: ""});
                  setMessage("");
                  setError("");
                }}
              >
                Use different account
              </button>
            </div>
          </form>
        )}

        {mode === "signup" && (
          <form onSubmit={handleSignup}>
            <div className="form-grid">
              <label>
                Username
                <input value={signupForm.username} onChange={(event) => setSignupForm({...signupForm, username: event.target.value})} />
              </label>
              <label>
                Email
                <input type="email" value={signupForm.email} onChange={(event) => setSignupForm({...signupForm, email: event.target.value})} />
              </label>
              <label>
                Password
                <input type="password" value={signupForm.password} onChange={(event) => setSignupForm({...signupForm, password: event.target.value})} />
              </label>
              <label>
                Confirm password
                <input type="password" value={signupForm.confirmPassword} onChange={(event) => setSignupForm({...signupForm, confirmPassword: event.target.value})} />
              </label>
            </div>
            <p className="muted">New accounts receive standard user access. Administrative privileges are managed separately.</p>
            {error && <p className="error">{error}</p>}
            <button type="submit" disabled={loading}>{loading ? "Creating..." : "Create Account"}</button>
          </form>
        )}
      </section>
    </main>
  );
}
