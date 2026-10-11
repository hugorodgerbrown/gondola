/*
 * static/js/passkey.js — The browser half of passkeys.
 *
 * On the sign-in page ([data-passkey-sign-in]) it offers saved passkeys in
 * the email field's autofill, and the "Sign in with a passkey" button asks
 * for one outright. On the account page ([data-passkey-add]) the button
 * adds a passkey for this device.
 *
 * Browsers without the JSON helpers on PublicKeyCredential keep the
 * passkey controls hidden; the emailed link works everywhere.
 */
(function () {
  "use strict";

  const supported =
    window.PublicKeyCredential &&
    typeof PublicKeyCredential.parseRequestOptionsFromJSON === "function" &&
    typeof PublicKeyCredential.parseCreationOptionsFromJSON === "function";

  function csrfToken() {
    const input = document.querySelector("[name=csrfmiddlewaretoken]");
    return input ? input.value : "";
  }

  async function getJSON(url, signal) {
    const response = await fetch(url, { credentials: "same-origin", signal: signal });
    if (!response.ok) throw new Error("options " + response.status);
    return response.json();
  }

  async function postJSON(url, body) {
    const response = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(body),
    });
    const data = await response.json().catch(function () { return {}; });
    if (!response.ok) throw new Error(data.error || "Something went wrong. Try again.");
    return data;
  }

  function showError(box, message) {
    if (!box) return;
    box.textContent = message;
    box.hidden = false;
  }

  /* --- Signing in ---------------------------------------------------------- */

  function signIn(root) {
    const optionsUrl = root.dataset.optionsUrl;
    const verifyUrl = root.dataset.verifyUrl;
    const nextUrl = root.dataset.next;
    const button = root.querySelector("[data-passkey-button]");
    const errorBox = root.querySelector("[data-passkey-error]");
    const form = root.querySelector("form");
    // Only one ceremony may be open at a time: they share the session's challenge.
    let autofill = null;
    // Set once a passkey is picked and on its way to the server. Signing in
    // rotates the CSRF token, so a second sign-in from this page would fail.
    let signingIn = false;

    async function ceremony(mediation, signal) {
      const options = await getJSON(optionsUrl, signal);
      const request = { publicKey: PublicKeyCredential.parseRequestOptionsFromJSON(options) };
      if (mediation) request.mediation = mediation;
      if (signal) request.signal = signal;
      const credential = await navigator.credentials.get(request);
      if (!credential || signingIn) return;
      signingIn = true;
      try {
        const data = await postJSON(verifyUrl, { credential: credential.toJSON(), next: nextUrl });
        window.location.assign(data.next);
      } catch (error) {
        signingIn = false;
        throw error;
      }
    }

    async function startAutofill() {
      const available = await PublicKeyCredential.isConditionalMediationAvailable().catch(
        function () { return false; }
      );
      if (!available) return;
      autofill = new AbortController();
      try {
        await ceremony("conditional", autofill.signal);
      } catch (error) {
        if (error.name !== "AbortError" && error.name !== "NotAllowedError") {
          showError(errorBox, error.message);
        }
      }
    }

    function stopAutofill() {
      if (autofill) autofill.abort();
      autofill = null;
    }

    button.hidden = false;
    button.addEventListener("click", async function () {
      if (signingIn) return;
      stopAutofill();
      button.disabled = true;
      try {
        await ceremony(null, null);
      } catch (error) {
        if (error.name !== "NotAllowedError" && error.name !== "AbortError") {
          showError(errorBox, error.message);
        }
      } finally {
        button.disabled = false;
      }
    });
    // Sending a link instead ends any passkey prompt still open.
    form.addEventListener("submit", stopAutofill);
    startAutofill();
  }

  /* --- Adding a passkey ---------------------------------------------------- */

  function add(root) {
    const button = root.querySelector("[data-passkey-button]");
    const errorBox = root.querySelector("[data-passkey-error]");
    root.hidden = false;
    button.addEventListener("click", async function () {
      button.disabled = true;
      try {
        const options = await getJSON(root.dataset.optionsUrl);
        const credential = await navigator.credentials.create({
          publicKey: PublicKeyCredential.parseCreationOptionsFromJSON(options),
        });
        await postJSON(root.dataset.verifyUrl, { credential: credential.toJSON() });
        window.location.reload();
      } catch (error) {
        if (error.name === "InvalidStateError") {
          showError(errorBox, "This device already has a passkey for your account.");
        } else if (error.name !== "NotAllowedError" && error.name !== "AbortError") {
          showError(errorBox, error.message);
        }
        button.disabled = false;
      }
    });
  }

  if (!supported) return;
  document.querySelectorAll("[data-passkey-sign-in]").forEach(signIn);
  document.querySelectorAll("[data-passkey-add]").forEach(add);
})();
