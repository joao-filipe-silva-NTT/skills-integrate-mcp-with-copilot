document.addEventListener("DOMContentLoaded", () => {
  const activitiesList = document.getElementById("activities-list");
  const activitySelect = document.getElementById("activity");
  const signupForm = document.getElementById("signup-form");
  const loginForm = document.getElementById("login-form");
  const registerForm = document.getElementById("register-form");
  const signupContainer = document.getElementById("signup-container");
  const sessionBanner = document.getElementById("session-banner");
  const sessionText = document.getElementById("session-text");
  const logoutBtn = document.getElementById("logout-btn");
  const authContainer = document.getElementById("auth-container");
  const messageDiv = document.getElementById("message");

  let authToken = localStorage.getItem("authToken") || "";
  let currentUser = JSON.parse(localStorage.getItem("currentUser") || "null");

  function showMessage(text, type = "info") {
    messageDiv.textContent = text;
    messageDiv.className = type;
    messageDiv.classList.remove("hidden");

    setTimeout(() => {
      messageDiv.classList.add("hidden");
    }, 5000);
  }

  async function apiFetch(url, options = {}) {
    const headers = {
      ...(options.headers || {}),
    };

    if (authToken) {
      headers.Authorization = `Bearer ${authToken}`;
    }

    return fetch(url, {
      ...options,
      headers,
    });
  }

  function updateSessionUI() {
    const authenticated = Boolean(authToken && currentUser);

    signupContainer.classList.toggle("disabled", !authenticated);

    if (authenticated) {
      sessionText.textContent = `Logged in as ${currentUser.email} (${currentUser.role})`;
      sessionBanner.classList.remove("hidden");
      authContainer.classList.add("collapsed");
    } else {
      sessionBanner.classList.add("hidden");
      authContainer.classList.remove("collapsed");
    }
  }

  function clearSession() {
    authToken = "";
    currentUser = null;
    localStorage.removeItem("authToken");
    localStorage.removeItem("currentUser");
    updateSessionUI();
  }

  function saveSession(token, user) {
    authToken = token;
    currentUser = user;
    localStorage.setItem("authToken", token);
    localStorage.setItem("currentUser", JSON.stringify(user));
    updateSessionUI();
  }

  // Function to fetch activities from API
  async function fetchActivities() {
    try {
      const response = await fetch("/activities");
      const activities = await response.json();

      // Clear loading message
      activitiesList.innerHTML = "";

      // Populate activities list
      Object.entries(activities).forEach(([name, details]) => {
        const activityCard = document.createElement("div");
        activityCard.className = "activity-card";

        const spotsLeft =
          details.max_participants - details.participants.length;

        // Show unregister only when authenticated, and students can only remove themselves.
        const participantsHTML =
          details.participants.length > 0
            ? `<div class="participants-section">
              <h5>Participants:</h5>
              <ul class="participants-list">
                ${details.participants
                  .map((email) => {
                    const canUnregister =
                      currentUser &&
                      (currentUser.role !== "student" || currentUser.email === email);

                    const actionButton = canUnregister
                      ? `<button class="delete-btn" data-activity="${name}" data-email="${email}">Unregister</button>`
                      : "";

                    return `<li><span class="participant-email">${email}</span>${actionButton}</li>`;
                  })
                  .join("")}
              </ul>
            </div>`
            : `<p><em>No participants yet</em></p>`;

        activityCard.innerHTML = `
          <h4>${name}</h4>
          <p>${details.description}</p>
          <p><strong>Schedule:</strong> ${details.schedule}</p>
          <p><strong>Availability:</strong> ${spotsLeft} spots left</p>
          <div class="participants-container">
            ${participantsHTML}
          </div>
        `;

        activitiesList.appendChild(activityCard);

        // Add option to select dropdown
        const option = document.createElement("option");
        option.value = name;
        option.textContent = name;
        activitySelect.appendChild(option);
      });

      // Add event listeners to delete buttons
      document.querySelectorAll(".delete-btn").forEach((button) => {
        button.addEventListener("click", handleUnregister);
      });
    } catch (error) {
      activitiesList.innerHTML =
        "<p>Failed to load activities. Please try again later.</p>";
      console.error("Error fetching activities:", error);
    }
  }

  // Handle unregister functionality
  async function handleUnregister(event) {
    if (!authToken) {
      showMessage("Please log in to unregister participants.", "error");
      return;
    }

    const button = event.target;
    const activity = button.getAttribute("data-activity");
    const email = button.getAttribute("data-email");

    try {
      const response = await apiFetch(
        `/activities/${encodeURIComponent(
          activity
        )}/unregister?email=${encodeURIComponent(email)}`,
        {
          method: "DELETE",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");

        // Refresh activities list to show updated participants
        fetchActivities();
      } else if (response.status === 401) {
        clearSession();
        showMessage("Session expired. Please log in again.", "error");
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to unregister. Please try again.", "error");
      console.error("Error unregistering:", error);
    }
  }

  // Handle form submission
  signupForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    if (!authToken) {
      showMessage("Please log in before signing up.", "error");
      return;
    }

    const activity = document.getElementById("activity").value;

    try {
      const response = await apiFetch(
        `/activities/${encodeURIComponent(activity)}/signup`,
        {
          method: "POST",
        }
      );

      const result = await response.json();

      if (response.ok) {
        showMessage(result.message, "success");
        signupForm.reset();

        // Refresh activities list to show updated participants
        fetchActivities();
      } else if (response.status === 401) {
        clearSession();
        showMessage("Session expired. Please log in again.", "error");
      } else {
        showMessage(result.detail || "An error occurred", "error");
      }
    } catch (error) {
      showMessage("Failed to sign up. Please try again.", "error");
      console.error("Error signing up:", error);
    }
  });

  loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      email: document.getElementById("login-email").value,
      password: document.getElementById("login-password").value,
      role: document.getElementById("login-role").value,
    };

    try {
      const response = await fetch("/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Login failed", "error");
        return;
      }

      saveSession(result.access_token, result.user);
      showMessage("Login successful.", "success");
      loginForm.reset();
      fetchActivities();
    } catch (error) {
      showMessage("Unable to log in right now.", "error");
      console.error("Login error:", error);
    }
  });

  registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();

    const payload = {
      email: document.getElementById("register-email").value,
      password: document.getElementById("register-password").value,
      role: document.getElementById("register-role").value,
    };

    try {
      const response = await fetch("/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      const result = await response.json();
      if (!response.ok) {
        showMessage(result.detail || "Registration failed", "error");
        return;
      }

      showMessage("Registration successful. You can now log in.", "success");
      registerForm.reset();
    } catch (error) {
      showMessage("Unable to register right now.", "error");
      console.error("Registration error:", error);
    }
  });

  logoutBtn.addEventListener("click", async () => {
    try {
      if (authToken) {
        await apiFetch("/logout", { method: "POST" });
      }
    } finally {
      clearSession();
      showMessage("Logged out.", "success");
      fetchActivities();
    }
  });

  // Initialize app
  updateSessionUI();
  fetchActivities();
});
