console.log("Perfume recommender UI loaded.");
// ensure notice & left badge start hidden
document.getElementById("aiNotice")?.classList.add("hidden");
document.getElementById("llmLeft")?.style && (document.getElementById("llmLeft").style.display = "none");
const state = { use_cases: ["office", "summer"] };

function setAiBadges({ show, left, limited, used }) {
  const aiNotice = document.getElementById("aiNotice");
  const llmLeftBadge = document.getElementById("llmLeft");
  const llmBadge = document.getElementById("llmBadge");

  // --- handle hiding when explain unchecked ---
  if (!show) {
    if (llmLeftBadge) llmLeftBadge.style.display = "none";
    if (llmBadge) {
      llmBadge.textContent = "AI reasoning: ready";
      llmBadge.classList.remove("danger");
    }
    if (aiNotice) aiNotice.classList.add("hidden");
    return;
  }

  // --- determine visual states ---
  const danger = typeof left === "number" && left <= 5;
  const capped = limited || (typeof left === "number" && left <= 0);

  // --- update AI reasoning badge ---
  if (llmBadge) {
    if (capped) {
      llmBadge.textContent = "AI reasoning: capped";
      llmBadge.classList.add("danger");
    } else if (danger) {
      llmBadge.textContent = "AI reasoning: capped";
      llmBadge.classList.add("danger");
    } else if (used) {
      llmBadge.textContent = "AI reasoning: used";
      llmBadge.classList.remove("danger");
    } else {
      llmBadge.textContent = "AI reasoning: ready";
      llmBadge.classList.remove("danger");
    }
  }

  // --- update 'AI left' badge ---
  if (typeof left === "number" && llmLeftBadge) {
    llmLeftBadge.style.display = "inline-block";
    llmLeftBadge.textContent = `AI left: ${left}`;
    if (danger) llmLeftBadge.classList.add("danger");
    else llmLeftBadge.classList.remove("danger");
  }

  // --- update AI notice ---
  if (aiNotice) {
    if (capped) {
      aiNotice.classList.remove("hidden");
      aiNotice.innerHTML = `<strong>No more AI explanations today.</strong> Recommendations still work; AI insights will resume after the daily reset.`;
    } else if (danger) {
      aiNotice.classList.remove("hidden");
      aiNotice.innerHTML = `<strong>Heads up:</strong> Only ${left} AI explanations left today.`;
    } else {
      aiNotice.classList.add("hidden");
    }
  }
}

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

  // before you start the try block
  const errorDiv = document.getElementById("error");
  const resultsDiv = document.getElementById("results");
  const cardsDiv = document.getElementById("cards") || resultsDiv;

  errorDiv.textContent = "";
  cardsDiv.innerHTML = "";  // ✅ clear old cards only

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
    // === AI daily limit UI ===
    const aiNotice = document.getElementById("aiNotice");
    const llmLeftBadge = document.getElementById("llmLeft");
    const llmBadge = document.getElementById("llmBadge");
    const explainChecked = document.getElementById("explain").checked;

    setAiBadges({
      show: explainChecked,
      left: data.llm_remaining,
      limited: data.llm_limited === true,
      used: data.llm_used === true
    });

    // update remaining counter
    if (typeof data.llm_remaining === "number" && llmLeftBadge) {
      llmLeftBadge.style.display = "inline-block";
      llmLeftBadge.textContent = `AI left: ${data.llm_remaining}`;

      // style tweaks when low / zero
      if (data.llm_remaining <= 0) {
        llmLeftBadge.classList.add("danger");
      } else {
        llmLeftBadge.classList.remove("danger");
      }
    }

    // show/hide limit notice
    const limited = data.llm_limited === true;
    if (aiNotice) {
      if (limited) {
        aiNotice.classList.remove("hidden");
        // Optional: sharpen text when hard limited
        aiNotice.innerHTML = `<strong>No more AI explanations today.</strong> Recommendations still work; try AI insights again after the daily reset.`;
      } else {
        // show a gentle heads-up if very low (<= 5 left)
        if (typeof data.llm_remaining === "number" && data.llm_remaining <= 5 && data.llm_remaining > 0) {
          aiNotice.classList.remove("hidden");
          aiNotice.innerHTML = `<strong>Heads up:</strong> Only ${data.llm_remaining} AI explanations left today.`;
        } else {
          aiNotice.classList.add("hidden");
        }
      }
    }

    // optional: reflect if AI was used this call
    if (llmBadge) {
      if (limited) {
        llmBadge.textContent = "AI reasoning: capped";
      } else if (data.llm_used) {
        llmBadge.textContent = "AI reasoning: used";
      } else {
        llmBadge.textContent = "AI reasoning: ready";
      }
    }

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
      cardsDiv.appendChild(card);
    });

  } catch (err) {
    console.error(err);
    errorDiv.textContent = err.message || "Request failed";
  }
});