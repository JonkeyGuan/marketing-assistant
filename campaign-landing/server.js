const express = require("express");
const http = require("http");

const app = express();
const PORT = process.env.PORT || 3001;

const CAMPAIGN_API_URL = process.env.CAMPAIGN_API_URL || "http://campaign-api:8089";
const CAMPAIGN_ID = process.env.CAMPAIGN_ID || "";

let cachedTemplate = null;
let cachedCampaign = {};
let cachedCustomers = {};
let heroImageBuffer = null;
let dataLoaded = false;

async function loadDataFromApi() {
  if (!CAMPAIGN_ID) {
    console.log("[Campaign Landing] No CAMPAIGN_ID set, skipping data load");
    return;
  }
  const base = `${CAMPAIGN_API_URL}/api/campaigns/${CAMPAIGN_ID}/assets`;

  try {
    const templateResp = await fetch(`${base}/template.html`);
    if (templateResp.ok) {
      cachedTemplate = await templateResp.text();
      console.log(`[Campaign Landing] Template loaded (${cachedTemplate.length} chars)`);
    }
  } catch (e) {
    console.log(`[Campaign Landing] Template fetch failed: ${e.message}`);
  }

  try {
    const campaignResp = await fetch(`${base}/campaign.json`);
    if (campaignResp.ok) cachedCampaign = await campaignResp.json();
  } catch (e) {
    console.log(`[Campaign Landing] Campaign fetch failed: ${e.message}`);
  }

  try {
    const customersResp = await fetch(`${base}/customers.json`);
    if (customersResp.ok) {
      const list = await customersResp.json();
      for (const c of list) {
        cachedCustomers[c.customer_id] = c;
      }
      console.log(`[Campaign Landing] Loaded ${list.length} customers`);
    }
  } catch (e) {
    console.log(`[Campaign Landing] Customers fetch failed: ${e.message}`);
  }

  try {
    const heroResp = await fetch(`${base}/hero.png`);
    if (heroResp.ok) {
      heroImageBuffer = Buffer.from(await heroResp.arrayBuffer());
      console.log(`[Campaign Landing] Hero image downloaded (${heroImageBuffer.length} bytes)`);
    }
  } catch (e) {
    console.log(`[Campaign Landing] Hero image fetch failed: ${e.message}`);
  }

  dataLoaded = true;
}

function personalize(html, customer, campaign) {
  const isProspect = customer.tier === "prospect";

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

app.get("/hero-image.png", (req, res) => {
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
  res.json({ status: dataLoaded && cachedTemplate ? "ready" : "not ready" });
});

app.get("/", async (req, res) => {
  if (!cachedTemplate) {
    return res.status(503).send("Landing page not yet configured");
  }

  const customerId = req.query.c;

  res.setHeader("Content-Type", "text/html");
  res.setHeader("X-Frame-Options", "");
  res.setHeader("Content-Security-Policy", "");

  if (!customerId) {
    return res.send(applyGenericDefaults(cachedTemplate, cachedCampaign));
  }

  const customer = cachedCustomers[customerId] || null;

  if (!customer) {
    return res.send(applyGenericDefaults(cachedTemplate, cachedCampaign));
  }

  res.send(personalize(cachedTemplate, customer, cachedCampaign));
});

app.listen(PORT, "0.0.0.0", async () => {
  console.log(`[Campaign Landing] Serving on 0.0.0.0:${PORT}`);
  console.log(`[Campaign Landing] Campaign API: ${CAMPAIGN_API_URL}`);
  console.log(`[Campaign Landing] Campaign ID: ${CAMPAIGN_ID}`);
  await loadDataFromApi();
});
