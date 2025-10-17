console.log("Perfume recommender UI loaded.");

const state = { use_cases: ["office", "summer"] };

// --- Toggle chips for use cases ---
document.querySelectorAll(".chip").forEach(btn => {
  btn.addEventListener("click", () => {
    const tag = btn.dataset.tag;
    const idx = state.use_cases.indexOf(tag);
    if (idx >= 0) {
      state.use_cases.splice(idx, 1);
      btn.classList.remove("active");
    } else {
      state.use_cases.push(tag);
      btn.classList.add("active");
    }
  });
});

// --- Helper to render stars ---
function renderStars(value, max = 5) {
  const full = Math.round(value);
  let html = "";
  for (let i = 1; i <= max; i++) {
    html += `<span class="star">${i <= full ? "★" : "☆"}</span>`;
  }
  return html;
}

// --- Handle request ---
document.getElementById("go").addEventListener("click", async () => {
  const liked = document.getElementById("liked").value
    .split(",").map(s => s.trim()).filter(Boolean);
  const notes = document.getElementById("notes").value
    .split(",").map(s => s.trim()).filter(Boolean);

  const body = {
    liked,
    preferred_notes: notes,
    use_cases: state.use_cases,
    price_min: parseFloat(document.getElementById("priceMin").value) || null,
    price_max: parseFloat(document.getElementById("priceMax").value) || null,
    rating_min: parseFloat(document.getElementById("ratingMin").value) || 0,
    rating_count_min: parseInt(document.getElementById("ratingCountMin").value) || 0,
    longevity_min: parseInt(document.getElementById("longevityMin").value) || 0,
    sillage_min: parseInt(document.getElementById("sillageMin").value) || 0,
    gender: document.getElementById("gender").value || "",
    k: parseInt(document.getElementById("k").value) || 8,
    explain: document.getElementById("explain").checked
  };

  const errorDiv = document.getElementById("error");
  const resultsDiv = document.getElementById("results");
  errorDiv.textContent = "";
  resultsDiv.innerHTML = "";

  try {
    console.log("Request:", body);
    const res = await fetch("/api/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body)
    });
    console.log("HTTP status:", res.status);

    if (!res.ok) {
      errorDiv.textContent = `Server error: ${res.status}`;
      return;
    }

    const data = await res.json();
    console.log("Response:", data);

    if (!data.results || !data.results.length) {
      resultsDiv.innerHTML = `<div class="muted">No results — try relaxing your filters.</div>`;
      return;
    }

    data.results.forEach(item => {
      const card = document.createElement("div");
      card.className = "card";

      const genderEmoji =
        item.gender?.toLowerCase() === "male" ? "♂️" :
        item.gender?.toLowerCase() === "female" ? "♀️" :
        "⚧️";

      card.innerHTML = `
        <div class="title">${item.brand} — ${item.name}</div>
        <div class="gender">${genderEmoji} ${item.gender || "Unisex"}</div>

        <div class="price">💰 ${item.price_range?.[0]}–${item.price_range?.[1]} PLN</div>

        <div class="kv">
          <span>${item.accords?.slice(0,3).join(", ")}</span>
        </div>

        <div class="stars">Rating: ${renderStars(item.rating_value)} 
          <span class="muted">(${item.rating_value?.toFixed(1)} / 5, ${item.rating_count} reviews)</span>
        </div>

        <div class="stars">Longevity: ${renderStars(item.longevity)}</div>
        <div class="stars">Sillage: ${renderStars(item.sillage)}</div>

        <div class="divider"></div>
        <div class="muted">${item.description || ""}</div>

        <div class="divider"></div>
        <div><a class="link" href="${item.url}" target="_blank">🔗 View on Fragrantica</a></div>

        ${item.ai_why ? `<div class="ai-why">💡 AI says:<br>${item.ai_why.replaceAll("\n", "<br>")}</div>` : ""}
      `;

      resultsDiv.appendChild(card);
    });

  } catch (err) {
    console.error(err);
    errorDiv.textContent = err.message || "Request failed";
  }
});