const express = require("express");
const fs = require("fs");
const http = require("http");

const app = express();
const PORT = process.env.PORT || 3001;

const DATA_DIR = process.env.DATA_DIR || "/data";
const TEMPLATE_PATH = `${DATA_DIR}/template.html`;
const CAMPAIGN_PATH = `${DATA_DIR}/campaign.json`;
const MONGODB_MCP_URL = process.env.MONGODB_MCP_URL || "http://mongodb-mcp:8082";
const HERO_IMAGE_URL = process.env.HERO_IMAGE_URL || "";

let heroImageBuffer = null;
let heroImageFetched = false;

let customerCache = {};
let cacheTime = 0;
const CACHE_TTL = 60000;

function loadFile(filePath) {
  try { return fs.readFileSync(filePath, "utf-8"); } catch { return null; }
}

function getCampaign() {
  const raw = loadFile(CAMPAIGN_PATH);
  try { return raw ? JSON.parse(raw) : {}; } catch { return {}; }
}

function parseSseJson(text) {
  for (const line of text.split("\n")) {
    if (line.startsWith("data: ")) {
      try { return JSON.parse(line.slice(6)); } catch {}
    }
  }
  return JSON.parse(text);
}

async function fetchCustomerFromMCP(customerId) {
  if (customerCache[customerId] && Date.now() - cacheTime < CACHE_TTL) {
    return customerCache[customerId];
  }

  const mcpHeaders = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
  };

  try {
    const resp = await fetch(`${MONGODB_MCP_URL}/mcp`, {
      method: "POST",
      headers: mcpHeaders,
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "initialize",
        params: {
          protocolVersion: "2024-11-05",
          capabilities: {},
          clientInfo: { name: "campaign-landing", version: "1.0.0" },
        },
        id: 1,
      }),
    });

    if (!resp.ok) throw new Error(`MCP init failed: ${resp.status}`);
    const sessionId = resp.headers.get("mcp-session-id") || "";

    const searchResp = await fetch(`${MONGODB_MCP_URL}/mcp`, {
      method: "POST",
      headers: { ...mcpHeaders, "mcp-session-id": sessionId },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
          name: "get_all_vip_customers",
          arguments: { limit: 100 },
        },
        id: 2,
      }),
    });

    if (searchResp.ok) {
      const raw = await searchResp.text();
      const data = parseSseJson(raw);
      if (data.result && data.result.content) {
        const customers = JSON.parse(data.result.content[0].text);
        customerCache = {};
        for (const c of customers) {
          customerCache[c.customer_id] = c;
        }
      }
    }

    // Also fetch prospects so PROSPECT-* IDs resolve
    const prospectResp = await fetch(`${MONGODB_MCP_URL}/mcp`, {
      method: "POST",
      headers: { ...mcpHeaders, "mcp-session-id": sessionId },
      body: JSON.stringify({
        jsonrpc: "2.0",
        method: "tools/call",
        params: {
          name: "get_prospects",
          arguments: { limit: 100 },
        },
        id: 3,
      }),
    });

    if (prospectResp.ok) {
      const raw = await prospectResp.text();
      const data = parseSseJson(raw);
      if (data.result && data.result.content) {
        const prospects = JSON.parse(data.result.content[0].text);
        for (const p of prospects) {
          customerCache[p.customer_id] = p;
        }
      }
    }

    cacheTime = Date.now();
    return customerCache[customerId] || null;
  } catch (e) {
    console.log(`[Campaign Landing] MCP fetch failed, trying ConfigMap fallback: ${e.message}`);
  }

  // Fallback to ConfigMap file if MCP fails
  try {
    const raw = loadFile(`${DATA_DIR}/customers.json`);
    if (raw) {
      const list = JSON.parse(raw);
      for (const c of list) {
        customerCache[c.customer_id] = c;
      }
      cacheTime = Date.now();
      return customerCache[customerId] || null;
    }
  } catch {}

  return null;
}

function personalize(html, customer, campaign) {
  const isProspect = customer.tier === "prospect";

  // Prospects get anonymous treatment — no names, just inviting language
  const name = isProspect ? "Distinguished Guest" : (customer.name_en || customer.name || "Valued Guest");
  const firstName = isProspect ? "Distinguished Guest" : (customer.name_en || customer.name || "Guest").split(" ")[0];
  const tier = (customer.tier || "VIP").charAt(0).toUpperCase() + (customer.tier || "vip").slice(1);
  const interests = (customer.interests || []).join(", ");

  const greeting = isProspect
    ? "An Exclusive Invitation Awaits You"
    : `Your Exclusive Experience Awaits, ${firstName}`;

  const tierEn = { diamond: "Diamond Elite", platinum: "Platinum VIP", gold: "Gold Member", prospect: "Exclusive Invitee" }[customer.tier] || "VIP Guest";

  const replacements = {
    "{{CUSTOMER_NAME}}": name,
    "{{CUSTOMER_FIRST_NAME}}": firstName,
    "{{CUSTOMER_TIER}}": tier,
    "{{CUSTOMER_TIER_BADGE}}": tierEn,
    "{{CUSTOMER_TIER_BADGE_ZH}}": tierEn,
    "{{GREETING}}": greeting,
    "{{CUSTOMER_INTERESTS}}": interests,
    "{{CUSTOMER_LANGUAGE}}": customer.preferred_language || "en",
    "{{CAMPAIGN_NAME}}": campaign.campaign_name || "",
    "{{HOTEL_NAME}}": campaign.hotel_name || "Simon Casino Resort",
  };

  let result = html;
  for (const [key, value] of Object.entries(replacements)) {
    result = result.split(key).join(value);
  }

  // Catch LLM-hardcoded generic text that should have been placeholders
  result = result
    .replace(/Honored Guest/g, tierEn)
    .replace(/Valued Guest/g, name)
    .replace(/>Guest</g, `>${firstName}<`)
    .replace(/Welcome,?\s*Guest/gi, `Welcome, ${firstName}`)
    .replace(/>VIP Guest</g, `>${tierEn}<`);

  return result;
}

function applyGenericDefaults(html, campaign) {
  return html
    .split("{{CUSTOMER_NAME}}").join("Valued Guest")
    .split("{{CUSTOMER_FIRST_NAME}}").join("Guest")
    .split("{{CUSTOMER_TIER}}").join("VIP")
    .split("{{CUSTOMER_TIER_BADGE}}").join("Honored Guest")
    .split("{{CUSTOMER_TIER_BADGE_ZH}}").join("Honored Guest")
    .split("{{GREETING}}").join("Your Exclusive Experience Awaits")
    .split("{{CUSTOMER_INTERESTS}}").join("")
    .split("{{CUSTOMER_LANGUAGE}}").join("en")
    .split("{{CAMPAIGN_NAME}}").join(campaign.campaign_name || "")
    .split("{{HOTEL_NAME}}").join(campaign.hotel_name || "Simon Casino Resort");
}

function fetchHeroImage() {
  if (!HERO_IMAGE_URL || heroImageFetched) return;
  heroImageFetched = true;
  http.get(HERO_IMAGE_URL, (res) => {
    if (res.statusCode !== 200) {
      console.log(`[Campaign Landing] Hero image fetch failed: ${res.statusCode}`);
      return;
    }
    const chunks = [];
    res.on("data", (chunk) => chunks.push(chunk));
    res.on("end", () => {
      heroImageBuffer = Buffer.concat(chunks);
      console.log(`[Campaign Landing] Hero image downloaded (${heroImageBuffer.length} bytes)`);
    });
  }).on("error", (e) => {
    console.log(`[Campaign Landing] Hero image fetch error: ${e.message}`);
  });
}

app.get("/hero-image.png", (req, res) => {
  if (!heroImageFetched) {
    fetchHeroImage();
  }
  if (heroImageBuffer) {
    res.setHeader("Content-Type", "image/png");
    res.setHeader("Cache-Control", "public, max-age=3600");
    return res.send(heroImageBuffer);
  }
  res.status(404).json({ error: "Hero image not available" });
});

app.get("/healthz", (req, res) => {
  res.json({ status: "healthy", service: "Campaign Landing" });
});

app.get("/readyz", (req, res) => {
  const template = loadFile(TEMPLATE_PATH);
  res.json({ status: template ? "ready" : "not ready" });
});

app.get("/", async (req, res) => {
  const template = loadFile(TEMPLATE_PATH);
  if (!template) {
    return res.status(503).send("Landing page not yet configured");
  }

  const campaign = getCampaign();
  const customerId = req.query.c;

  res.setHeader("Content-Type", "text/html");
  res.setHeader("X-Frame-Options", "");
  res.setHeader("Content-Security-Policy", "");

  if (!customerId) {
    return res.send(applyGenericDefaults(template, campaign));
  }

  const customer = await fetchCustomerFromMCP(customerId);

  if (!customer) {
    return res.send(applyGenericDefaults(template, campaign));
  }

  res.send(personalize(template, customer, campaign));
});

app.listen(PORT, "0.0.0.0", () => {
  console.log(`[Campaign Landing] Serving on 0.0.0.0:${PORT}`);
  console.log(`[Campaign Landing] Template: ${TEMPLATE_PATH}`);
  console.log(`[Campaign Landing] MongoDB MCP: ${MONGODB_MCP_URL}`);
  if (HERO_IMAGE_URL) {
    console.log(`[Campaign Landing] Hero image: ${HERO_IMAGE_URL}`);
    fetchHeroImage();
  }
});
