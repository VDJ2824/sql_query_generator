const BREVO_API_URL = "https://api.brevo.com/v3/smtp/email";

function parseSender(sender) {
  const value = (sender || "").trim();
  const match = value.match(/^(.*?)\s*<([^>]+)>$/);
  if (match) {
    return {name: match[1].trim(), email: match[2].trim()};
  }
  return value ? {email: value} : null;
}

function isEmailConfigured() {
  return Boolean((process.env.BREVO_API_KEY || "").trim() && (process.env.BREVO_FROM || "").trim());
}

async function sendBrevoEmail({to, subject, text, html}) {
  const apiKey = (process.env.BREVO_API_KEY || "").trim();
  const sender = parseSender(process.env.BREVO_FROM);

  if (!apiKey || !sender) {
    console.warn("Brevo email service is not configured.");
    return false;
  }

  const timeoutMs = Number.parseInt(process.env.EMAIL_SEND_TIMEOUT_MS || "10000", 10);
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), Number.isFinite(timeoutMs) ? timeoutMs : 10000);

  try {
    const response = await fetch(BREVO_API_URL, {
      method: "POST",
      signal: controller.signal,
      headers: {
        accept: "application/json",
        "api-key": apiKey,
        "content-type": "application/json",
      },
      body: JSON.stringify({
        sender,
        to: [{email: to}],
        subject,
        textContent: text,
        htmlContent: html || `<p>${text}</p>`,
      }),
    });

    if (!response.ok) {
      console.warn(`Brevo email delivery failed with status ${response.status}.`);
      return false;
    }
    return true;
  } catch (error) {
    console.warn(`Brevo email delivery error: ${error.name || "RequestError"}.`);
    return false;
  } finally {
    clearTimeout(timer);
  }
}

async function sendLoginOtp({username, email, otp, expiresInMinutes}) {
  const subject = "Your Secure SQL Assistant login code";
  const text = [
    `Hello ${username},`,
    "",
    `Your Secure SQL Assistant login code is ${otp}.`,
    `It expires in ${expiresInMinutes} minutes.`,
    "",
    "If you did not request this, you can ignore this email.",
  ].join("\n");
  const html = [
    `<p>Hello ${username},</p>`,
    `<p>Your Secure SQL Assistant login code is <strong>${otp}</strong>.</p>`,
    `<p>It expires in ${expiresInMinutes} minutes.</p>`,
    "<p>If you did not request this, you can ignore this email.</p>",
  ].join("");

  return sendBrevoEmail({to: email, subject, text, html});
}

module.exports = {
  isEmailConfigured,
  sendLoginOtp,
};
