import{createRequire}from'module';const require=createRequire(import.meta.url);

// node_modules/@netlify/blobs/dist/chunk-XR3MUBBK.js
var NF_ERROR = "x-nf-error";
var NF_REQUEST_ID = "x-nf-request-id";
var BlobsInternalError = class extends Error {
  constructor(res) {
    let details = res.headers.get(NF_ERROR) || `${res.status} status code`;
    if (res.headers.has(NF_REQUEST_ID)) {
      details += `, ID: ${res.headers.get(NF_REQUEST_ID)}`;
    }
    super(`Netlify Blobs has generated an internal error (${details})`);
    this.name = "BlobsInternalError";
  }
};
var collectIterator = async (iterator) => {
  const result = [];
  for await (const item of iterator) {
    result.push(item);
  }
  return result;
};
var base64Decode = (input) => {
  const { Buffer: Buffer2 } = globalThis;
  if (Buffer2) {
    return Buffer2.from(input, "base64").toString();
  }
  return atob(input);
};
var base64Encode = (input) => {
  const { Buffer: Buffer2 } = globalThis;
  if (Buffer2) {
    return Buffer2.from(input).toString("base64");
  }
  return btoa(input);
};
var getEnvironment = () => {
  const { Deno, Netlify, process: process2 } = globalThis;
  return Netlify?.env ?? Deno?.env ?? {
    delete: (key) => delete process2?.env[key],
    get: (key) => process2?.env[key],
    has: (key) => Boolean(process2?.env[key]),
    set: (key, value) => {
      if (process2?.env) {
        process2.env[key] = value;
      }
    },
    toObject: () => process2?.env ?? {}
  };
};
var getEnvironmentContext = () => {
  const context = globalThis.netlifyBlobsContext || getEnvironment().get("NETLIFY_BLOBS_CONTEXT");
  if (typeof context !== "string" || !context) {
    return {};
  }
  const data = base64Decode(context);
  try {
    return JSON.parse(data);
  } catch {
  }
  return {};
};
var MissingBlobsEnvironmentError = class extends Error {
  constructor(requiredProperties) {
    super(
      `The environment has not been configured to use Netlify Blobs. To use it manually, supply the following properties when creating a store: ${requiredProperties.join(
        ", "
      )}`
    );
    this.name = "MissingBlobsEnvironmentError";
  }
};
var BASE64_PREFIX = "b64;";
var METADATA_HEADER_INTERNAL = "x-amz-meta-user";
var METADATA_HEADER_EXTERNAL = "netlify-blobs-metadata";
var METADATA_MAX_SIZE = 2 * 1024;
var encodeMetadata = (metadata) => {
  if (!metadata) {
    return null;
  }
  const encodedObject = base64Encode(JSON.stringify(metadata));
  const payload = `b64;${encodedObject}`;
  if (METADATA_HEADER_EXTERNAL.length + payload.length > METADATA_MAX_SIZE) {
    throw new Error("Metadata object exceeds the maximum size");
  }
  return payload;
};
var decodeMetadata = (header) => {
  if (!header || !header.startsWith(BASE64_PREFIX)) {
    return {};
  }
  const encodedData = header.slice(BASE64_PREFIX.length);
  const decodedData = base64Decode(encodedData);
  const metadata = JSON.parse(decodedData);
  return metadata;
};
var getMetadataFromResponse = (response) => {
  if (!response.headers) {
    return {};
  }
  const value = response.headers.get(METADATA_HEADER_EXTERNAL) || response.headers.get(METADATA_HEADER_INTERNAL);
  try {
    return decodeMetadata(value);
  } catch {
    throw new Error(
      "An internal error occurred while trying to retrieve the metadata for an entry. Please try updating to the latest version of the Netlify Blobs client."
    );
  }
};
var BlobsConsistencyError = class extends Error {
  constructor() {
    super(
      `Netlify Blobs has failed to perform a read using strong consistency because the environment has not been configured with a 'uncachedEdgeURL' property`
    );
    this.name = "BlobsConsistencyError";
  }
};
var regions = {
  "us-east-1": true,
  "us-east-2": true,
  "eu-central-1": true,
  "ap-southeast-1": true,
  "ap-southeast-2": true
};
var isValidRegion = (input) => Object.keys(regions).includes(input);
var InvalidBlobsRegionError = class extends Error {
  constructor(region) {
    super(
      `${region} is not a supported Netlify Blobs region. Supported values are: ${Object.keys(regions).join(", ")}.`
    );
    this.name = "InvalidBlobsRegionError";
  }
};
var DEFAULT_RETRY_DELAY = getEnvironment().get("NODE_ENV") === "test" ? 1 : 5e3;
var MIN_RETRY_DELAY = 1e3;
var MAX_RETRY = 5;
var RATE_LIMIT_HEADER = "X-RateLimit-Reset";
var fetchAndRetry = async (fetch2, url, options, attemptsLeft = MAX_RETRY) => {
  try {
    const res = await fetch2(url, options);
    if (attemptsLeft > 0 && (res.status === 429 || res.status >= 500)) {
      const delay = getDelay(res.headers.get(RATE_LIMIT_HEADER));
      await sleep(delay);
      return fetchAndRetry(fetch2, url, options, attemptsLeft - 1);
    }
    return res;
  } catch (error) {
    if (attemptsLeft === 0) {
      throw error;
    }
    const delay = getDelay();
    await sleep(delay);
    return fetchAndRetry(fetch2, url, options, attemptsLeft - 1);
  }
};
var getDelay = (rateLimitReset) => {
  if (!rateLimitReset) {
    return DEFAULT_RETRY_DELAY;
  }
  return Math.max(Number(rateLimitReset) * 1e3 - Date.now(), MIN_RETRY_DELAY);
};
var sleep = (ms) => new Promise((resolve) => {
  setTimeout(resolve, ms);
});
var SIGNED_URL_ACCEPT_HEADER = "application/json;type=signed-url";
var Client = class {
  constructor({ apiURL, consistency, edgeURL, fetch: fetch2, region, siteID, token, uncachedEdgeURL }) {
    this.apiURL = apiURL;
    this.consistency = consistency ?? "eventual";
    this.edgeURL = edgeURL;
    this.fetch = fetch2 ?? globalThis.fetch;
    this.region = region;
    this.siteID = siteID;
    this.token = token;
    this.uncachedEdgeURL = uncachedEdgeURL;
    if (!this.fetch) {
      throw new Error(
        "Netlify Blobs could not find a `fetch` client in the global scope. You can either update your runtime to a version that includes `fetch` (like Node.js 18.0.0 or above), or you can supply your own implementation using the `fetch` property."
      );
    }
  }
  async getFinalRequest({
    consistency: opConsistency,
    key,
    metadata,
    method,
    parameters = {},
    storeName
  }) {
    const encodedMetadata = encodeMetadata(metadata);
    const consistency = opConsistency ?? this.consistency;
    let urlPath = `/${this.siteID}`;
    if (storeName) {
      urlPath += `/${storeName}`;
    }
    if (key) {
      urlPath += `/${key}`;
    }
    if (this.edgeURL) {
      if (consistency === "strong" && !this.uncachedEdgeURL) {
        throw new BlobsConsistencyError();
      }
      const headers = {
        authorization: `Bearer ${this.token}`
      };
      if (encodedMetadata) {
        headers[METADATA_HEADER_INTERNAL] = encodedMetadata;
      }
      if (this.region) {
        urlPath = `/region:${this.region}${urlPath}`;
      }
      const url2 = new URL(urlPath, consistency === "strong" ? this.uncachedEdgeURL : this.edgeURL);
      for (const key2 in parameters) {
        url2.searchParams.set(key2, parameters[key2]);
      }
      return {
        headers,
        url: url2.toString()
      };
    }
    const apiHeaders = { authorization: `Bearer ${this.token}` };
    const url = new URL(`/api/v1/blobs${urlPath}`, this.apiURL ?? "https://api.netlify.com");
    for (const key2 in parameters) {
      url.searchParams.set(key2, parameters[key2]);
    }
    if (this.region) {
      url.searchParams.set("region", this.region);
    }
    if (storeName === void 0 || key === void 0) {
      return {
        headers: apiHeaders,
        url: url.toString()
      };
    }
    if (encodedMetadata) {
      apiHeaders[METADATA_HEADER_EXTERNAL] = encodedMetadata;
    }
    if (method === "head" || method === "delete") {
      return {
        headers: apiHeaders,
        url: url.toString()
      };
    }
    const res = await this.fetch(url.toString(), {
      headers: { ...apiHeaders, accept: SIGNED_URL_ACCEPT_HEADER },
      method
    });
    if (res.status !== 200) {
      throw new BlobsInternalError(res);
    }
    const { url: signedURL } = await res.json();
    const userHeaders = encodedMetadata ? { [METADATA_HEADER_INTERNAL]: encodedMetadata } : void 0;
    return {
      headers: userHeaders,
      url: signedURL
    };
  }
  async makeRequest({
    body,
    consistency,
    headers: extraHeaders,
    key,
    metadata,
    method,
    parameters,
    storeName
  }) {
    const { headers: baseHeaders = {}, url } = await this.getFinalRequest({
      consistency,
      key,
      metadata,
      method,
      parameters,
      storeName
    });
    const headers = {
      ...baseHeaders,
      ...extraHeaders
    };
    if (method === "put") {
      headers["cache-control"] = "max-age=0, stale-while-revalidate=60";
    }
    const options = {
      body,
      headers,
      method
    };
    if (body instanceof ReadableStream) {
      options.duplex = "half";
    }
    return fetchAndRetry(this.fetch, url, options);
  }
};
var getClientOptions = (options, contextOverride) => {
  const context = contextOverride ?? getEnvironmentContext();
  const siteID = context.siteID ?? options.siteID;
  const token = context.token ?? options.token;
  if (!siteID || !token) {
    throw new MissingBlobsEnvironmentError(["siteID", "token"]);
  }
  if (options.region !== void 0 && !isValidRegion(options.region)) {
    throw new InvalidBlobsRegionError(options.region);
  }
  const clientOptions = {
    apiURL: context.apiURL ?? options.apiURL,
    consistency: options.consistency,
    edgeURL: context.edgeURL ?? options.edgeURL,
    fetch: options.fetch,
    region: options.region,
    siteID,
    token,
    uncachedEdgeURL: context.uncachedEdgeURL ?? options.uncachedEdgeURL
  };
  return clientOptions;
};

// node_modules/@netlify/blobs/dist/main.js
var DEPLOY_STORE_PREFIX = "deploy:";
var LEGACY_STORE_INTERNAL_PREFIX = "netlify-internal/legacy-namespace/";
var SITE_STORE_PREFIX = "site:";
var Store = class _Store {
  constructor(options) {
    this.client = options.client;
    if ("deployID" in options) {
      _Store.validateDeployID(options.deployID);
      let name = DEPLOY_STORE_PREFIX + options.deployID;
      if (options.name) {
        name += `:${options.name}`;
      }
      this.name = name;
    } else if (options.name.startsWith(LEGACY_STORE_INTERNAL_PREFIX)) {
      const storeName = options.name.slice(LEGACY_STORE_INTERNAL_PREFIX.length);
      _Store.validateStoreName(storeName);
      this.name = storeName;
    } else {
      _Store.validateStoreName(options.name);
      this.name = SITE_STORE_PREFIX + options.name;
    }
  }
  async delete(key) {
    const res = await this.client.makeRequest({ key, method: "delete", storeName: this.name });
    if (![200, 204, 404].includes(res.status)) {
      throw new BlobsInternalError(res);
    }
  }
  async get(key, options) {
    const { consistency, type } = options ?? {};
    const res = await this.client.makeRequest({ consistency, key, method: "get", storeName: this.name });
    if (res.status === 404) {
      return null;
    }
    if (res.status !== 200) {
      throw new BlobsInternalError(res);
    }
    if (type === void 0 || type === "text") {
      return res.text();
    }
    if (type === "arrayBuffer") {
      return res.arrayBuffer();
    }
    if (type === "blob") {
      return res.blob();
    }
    if (type === "json") {
      return res.json();
    }
    if (type === "stream") {
      return res.body;
    }
    throw new BlobsInternalError(res);
  }
  async getMetadata(key, { consistency } = {}) {
    const res = await this.client.makeRequest({ consistency, key, method: "head", storeName: this.name });
    if (res.status === 404) {
      return null;
    }
    if (res.status !== 200 && res.status !== 304) {
      throw new BlobsInternalError(res);
    }
    const etag = res?.headers.get("etag") ?? void 0;
    const metadata = getMetadataFromResponse(res);
    const result = {
      etag,
      metadata
    };
    return result;
  }
  async getWithMetadata(key, options) {
    const { consistency, etag: requestETag, type } = options ?? {};
    const headers = requestETag ? { "if-none-match": requestETag } : void 0;
    const res = await this.client.makeRequest({
      consistency,
      headers,
      key,
      method: "get",
      storeName: this.name
    });
    if (res.status === 404) {
      return null;
    }
    if (res.status !== 200 && res.status !== 304) {
      throw new BlobsInternalError(res);
    }
    const responseETag = res?.headers.get("etag") ?? void 0;
    const metadata = getMetadataFromResponse(res);
    const result = {
      etag: responseETag,
      metadata
    };
    if (res.status === 304 && requestETag) {
      return { data: null, ...result };
    }
    if (type === void 0 || type === "text") {
      return { data: await res.text(), ...result };
    }
    if (type === "arrayBuffer") {
      return { data: await res.arrayBuffer(), ...result };
    }
    if (type === "blob") {
      return { data: await res.blob(), ...result };
    }
    if (type === "json") {
      return { data: await res.json(), ...result };
    }
    if (type === "stream") {
      return { data: res.body, ...result };
    }
    throw new Error(`Invalid 'type' property: ${type}. Expected: arrayBuffer, blob, json, stream, or text.`);
  }
  list(options = {}) {
    const iterator = this.getListIterator(options);
    if (options.paginate) {
      return iterator;
    }
    return collectIterator(iterator).then(
      (items) => items.reduce(
        (acc, item) => ({
          blobs: [...acc.blobs, ...item.blobs],
          directories: [...acc.directories, ...item.directories]
        }),
        { blobs: [], directories: [] }
      )
    );
  }
  async set(key, data, { metadata } = {}) {
    _Store.validateKey(key);
    const res = await this.client.makeRequest({
      body: data,
      key,
      metadata,
      method: "put",
      storeName: this.name
    });
    if (res.status !== 200) {
      throw new BlobsInternalError(res);
    }
  }
  async setJSON(key, data, { metadata } = {}) {
    _Store.validateKey(key);
    const payload = JSON.stringify(data);
    const headers = {
      "content-type": "application/json"
    };
    const res = await this.client.makeRequest({
      body: payload,
      headers,
      key,
      metadata,
      method: "put",
      storeName: this.name
    });
    if (res.status !== 200) {
      throw new BlobsInternalError(res);
    }
  }
  static formatListResultBlob(result) {
    if (!result.key) {
      return null;
    }
    return {
      etag: result.etag,
      key: result.key
    };
  }
  static validateKey(key) {
    if (key === "") {
      throw new Error("Blob key must not be empty.");
    }
    if (key.startsWith("/") || key.startsWith("%2F")) {
      throw new Error("Blob key must not start with forward slash (/).");
    }
    if (new TextEncoder().encode(key).length > 600) {
      throw new Error(
        "Blob key must be a sequence of Unicode characters whose UTF-8 encoding is at most 600 bytes long."
      );
    }
  }
  static validateDeployID(deployID) {
    if (!/^\w{1,24}$/.test(deployID)) {
      throw new Error(`'${deployID}' is not a valid Netlify deploy ID.`);
    }
  }
  static validateStoreName(name) {
    if (name.includes("/") || name.includes("%2F")) {
      throw new Error("Store name must not contain forward slashes (/).");
    }
    if (new TextEncoder().encode(name).length > 64) {
      throw new Error(
        "Store name must be a sequence of Unicode characters whose UTF-8 encoding is at most 64 bytes long."
      );
    }
  }
  getListIterator(options) {
    const { client, name: storeName } = this;
    const parameters = {};
    if (options?.prefix) {
      parameters.prefix = options.prefix;
    }
    if (options?.directories) {
      parameters.directories = "true";
    }
    return {
      [Symbol.asyncIterator]() {
        let currentCursor = null;
        let done = false;
        return {
          async next() {
            if (done) {
              return { done: true, value: void 0 };
            }
            const nextParameters = { ...parameters };
            if (currentCursor !== null) {
              nextParameters.cursor = currentCursor;
            }
            const res = await client.makeRequest({
              method: "get",
              parameters: nextParameters,
              storeName
            });
            let blobs = [];
            let directories = [];
            if (![200, 204, 404].includes(res.status)) {
              throw new BlobsInternalError(res);
            }
            if (res.status === 404) {
              done = true;
            } else {
              const page = await res.json();
              if (page.next_cursor) {
                currentCursor = page.next_cursor;
              } else {
                done = true;
              }
              blobs = (page.blobs ?? []).map(_Store.formatListResultBlob).filter(Boolean);
              directories = page.directories ?? [];
            }
            return {
              done: false,
              value: {
                blobs,
                directories
              }
            };
          }
        };
      }
    };
  }
};
var getStore = (input) => {
  if (typeof input === "string") {
    const clientOptions = getClientOptions({});
    const client = new Client(clientOptions);
    return new Store({ client, name: input });
  }
  if (typeof input?.name === "string" && typeof input?.siteID === "string" && typeof input?.token === "string") {
    const { name, siteID, token } = input;
    const clientOptions = getClientOptions(input, { siteID, token });
    if (!name || !siteID || !token) {
      throw new MissingBlobsEnvironmentError(["name", "siteID", "token"]);
    }
    const client = new Client(clientOptions);
    return new Store({ client, name });
  }
  if (typeof input?.name === "string") {
    const { name } = input;
    const clientOptions = getClientOptions(input);
    if (!name) {
      throw new MissingBlobsEnvironmentError(["name"]);
    }
    const client = new Client(clientOptions);
    return new Store({ client, name });
  }
  if (typeof input?.deployID === "string") {
    const clientOptions = getClientOptions(input);
    const { deployID } = input;
    if (!deployID) {
      throw new MissingBlobsEnvironmentError(["deployID"]);
    }
    const client = new Client(clientOptions);
    return new Store({ client, deployID });
  }
  throw new Error(
    "The `getStore` method requires the name of the store as a string or as the `name` property of an options object"
  );
};

// src/api.mjs
import crypto from "node:crypto";
var MAX_PROGRESS = 2e5;
var MAX_CALLS = 300;
var mem = /* @__PURE__ */ new Map();
function store() {
  if (process.env.SETU_MEMSTORE) {
    return {
      get: async (k, o) => {
        const v = mem.get(k);
        return v === void 0 ? null : o && o.type === "json" ? JSON.parse(v) : v;
      },
      setJSON: async (k, v) => {
        mem.set(k, JSON.stringify(v));
      },
      set: async (k, v) => {
        mem.set(k, String(v));
      }
    };
  }
  return getStore({ name: "setu", consistency: "strong" });
}
var json = (code, obj, extra) => new Response(JSON.stringify(obj), {
  status: code,
  headers: { "content-type": "application/json", "cache-control": "no-store", ...extra || {} }
});
var cap = (s, n) => String(s == null ? "" : s).slice(0, n);
var b64u = (buf) => Buffer.from(buf).toString("base64url");
async function secret(st) {
  if (process.env.SESSION_SECRET) return process.env.SESSION_SECRET;
  let s = await st.get("config/secret");
  if (!s) {
    s = crypto.randomBytes(32).toString("hex");
    await st.set("config/secret", s);
  }
  return s;
}
function sign(payload, key) {
  const body = b64u(JSON.stringify(payload));
  const mac = crypto.createHmac("sha256", key).update(body).digest("base64url");
  return body + "." + mac;
}
function verify(tok, key) {
  if (!tok || tok.indexOf(".") < 0) return null;
  const [body, mac] = tok.split(".");
  const want = crypto.createHmac("sha256", key).update(body).digest("base64url");
  if (mac.length !== want.length || !crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(want))) return null;
  try {
    const p = JSON.parse(Buffer.from(body, "base64url").toString());
    return p.exp > Date.now() ? p : null;
  } catch (e) {
    return null;
  }
}
var hashPin = (pin, salt) => crypto.scryptSync(pin, salt, 32).toString("hex");
var userKey = (u) => "users/" + u;
var normUser = (u) => cap(u, 40).trim().toLowerCase();
async function authed(req, st) {
  const h = req.headers.get("authorization") || "";
  const tok = h.startsWith("Bearer ") ? h.slice(7) : "";
  return verify(tok, await secret(st));
}
async function session(st, user) {
  const exp = Date.now() + 30 * 24 * 3600 * 1e3;
  return sign({ u: user.username, n: user.name, exp }, await secret(st));
}
var api_default = async (req) => {
  const url = new URL(req.url);
  const path = url.pathname.replace(/^\/api\/?/, "").replace(/\/$/, "");
  const st = store();
  try {
    if (path === "health") {
      return json(200, { ok: true, ai: !!process.env.LLM_API_KEY, model: process.env.LLM_MODEL || "llama-3.3-70b-versatile", time: (/* @__PURE__ */ new Date()).toISOString() });
    }
    if (path === "signup" && req.method === "POST") {
      const b = await req.json().catch(() => ({}));
      const username = normUser(b.username), name = cap(b.name, 60).trim(), pin = String(b.pin || "");
      if (!/^[a-z0-9_.-]{3,40}$/.test(username)) return json(400, { error: "Username: 3+ letters/numbers" });
      if (!/^\d{4,8}$/.test(pin)) return json(400, { error: "PIN must be 4-8 digits" });
      if (!name) return json(400, { error: "Name required" });
      if (await st.get(userKey(username))) return json(409, { error: "Username taken" });
      const salt = crypto.randomBytes(16).toString("hex");
      const user = { username, name, salt, pin: hashPin(pin, salt), created: (/* @__PURE__ */ new Date()).toISOString(), fails: 0 };
      await st.setJSON(userKey(username), user);
      return json(200, { token: await session(st, user), user: { username, name, created: user.created } });
    }
    if (path === "login" && req.method === "POST") {
      const b = await req.json().catch(() => ({}));
      const username = normUser(b.username), pin = String(b.pin || "");
      const user = await st.get(userKey(username), { type: "json" });
      if (!user) return json(401, { error: "Wrong username or PIN" });
      if (user.lockUntil && user.lockUntil > Date.now()) return json(429, { error: "Too many tries. Wait 5 minutes." });
      const ok = crypto.timingSafeEqual(Buffer.from(hashPin(pin, user.salt)), Buffer.from(user.pin));
      if (!ok) {
        user.fails = (user.fails || 0) + 1;
        if (user.fails >= 5) {
          user.lockUntil = Date.now() + 5 * 60 * 1e3;
          user.fails = 0;
        }
        await st.setJSON(userKey(username), user);
        return json(401, { error: "Wrong username or PIN" });
      }
      user.fails = 0;
      user.lockUntil = 0;
      user.lastLogin = (/* @__PURE__ */ new Date()).toISOString();
      await st.setJSON(userKey(username), user);
      return json(200, { token: await session(st, user), user: { username, name: user.name, created: user.created } });
    }
    const me = await authed(req, st);
    if (path === "me") {
      if (!me) return json(401, { error: "Not signed in" });
      const user = await st.get(userKey(me.u), { type: "json" });
      if (!user) return json(401, { error: "Account gone" });
      return json(200, { username: user.username, name: user.name, created: user.created, lastLogin: user.lastLogin || null });
    }
    if (path === "progress") {
      if (!me) return json(401, { error: "Not signed in" });
      if (req.method === "GET") return json(200, await st.get("progress/" + me.u, { type: "json" }) || { state: null, updated: null });
      if (req.method === "PUT") {
        const text = await req.text();
        if (text.length > MAX_PROGRESS) return json(413, { error: "Progress too large" });
        let b;
        try {
          b = JSON.parse(text);
        } catch (e) {
          return json(400, { error: "bad json" });
        }
        const rec = { state: b.state || {}, updated: (/* @__PURE__ */ new Date()).toISOString() };
        await st.setJSON("progress/" + me.u, rec);
        return json(200, { updated: rec.updated });
      }
    }
    if (path === "calls" && req.method === "GET") {
      if (!me) return json(401, { error: "Not signed in" });
      const calls = await st.get("calls/" + me.u, { type: "json" }) || [];
      return json(200, { calls: calls.slice(-50).reverse(), total: calls.length });
    }
    if (path === "raju" && req.method === "POST") return await raju(req, st, me);
    return json(404, { error: "no route " + path });
  } catch (e) {
    console.error(e);
    return json(500, { error: "server error" });
  }
};
async function raju(req, st, me) {
  const key = process.env.LLM_API_KEY;
  const b = await req.json().catch(() => ({}));
  const verdict = b.verdict === "correct" ? "correct" : "wrong";
  const base = (process.env.LLM_URL || "https://api.groq.com/openai/v1").replace(/\/$/, "");
  const model = process.env.LLM_MODEL || "llama-3.3-70b-versatile";
  const inp = {
    rule: cap(b.rule, 600),
    raju_said: cap(b.raju_said, 200),
    meant_en: cap(b.meant_en, 200),
    learner: cap(b.learner, 200),
    tries: Math.min(Number(b.tries) || 1, 9),
    correct_sentence: verdict === "correct" ? cap(b.correct_sentence, 200) : ""
  };
  const log = { at: (/* @__PURE__ */ new Date()).toISOString(), rule: cap(b.rule_id, 40), verdict, model, ms: 0, tokens: 0, ok: false, error: "" };
  const finish = async (code, body) => {
    if (me) {
      try {
        const k = "calls/" + me.u;
        const arr = await st.get(k, { type: "json" }) || [];
        arr.push(log);
        await st.setJSON(k, arr.slice(-MAX_CALLS));
      } catch (e) {
        console.error("log fail", e);
      }
    }
    return json(code, { ...body, call: log });
  };
  if (!key) {
    log.error = "no LLM_API_KEY on server";
    return finish(503, { error: log.error });
  }
  const system = 'You are Raju, a friendly classmate who is also learning Telugu. You are a Hindi speaker, so you make the mistakes Hindi speakers make. The learner just tried to correct your Telugu sentence. A rule-based checker (not you) has already decided the verdict; never contradict it. Write a SHORT reaction (1-2 sentences) in simple Hindi (Devanagari) and the same in simple English. Do NOT write any new Telugu yourself; you may quote the Telugu strings you were given, exactly. If the verdict is wrong: do not reveal or hint the full correct sentence; encourage and point back to the rule in plain words. If the verdict is correct: thank them and say in one line what you learned from the rule. Reply ONLY as JSON: {"hi":"...","en":"..."}';
  const ac = new AbortController();
  const timer = setTimeout(() => ac.abort(), 15e3);
  const t0 = Date.now();
  try {
    const r = await fetch(base + "/chat/completions", {
      method: "POST",
      signal: ac.signal,
      headers: { "content-type": "application/json", authorization: "Bearer " + key },
      body: JSON.stringify({
        model,
        temperature: 0.6,
        max_tokens: 220,
        response_format: { type: "json_object" },
        messages: [{ role: "system", content: system }, { role: "user", content: "Verdict (decided by the checker): " + verdict.toUpperCase() + "\n" + JSON.stringify(inp) }]
      })
    });
    log.ms = Date.now() - t0;
    if (!r.ok) {
      log.error = "model http " + r.status;
      return finish(502, { error: log.error });
    }
    const data = await r.json();
    log.tokens = data.usage && data.usage.total_tokens || 0;
    const text = (((data.choices || [])[0] || {}).message || {}).content || "";
    let o;
    try {
      o = JSON.parse(text);
    } catch (e) {
      const m = text.match(/\{[\s\S]*\}/);
      try {
        o = m ? JSON.parse(m[0]) : {};
      } catch (e2) {
        o = {};
      }
    }
    let hi = cap(o.hi, 300), en = cap(o.en, 300);
    if (verdict === "wrong" && b.never_say) {
      const bad = String(b.never_say).split("|").filter(Boolean);
      if (bad.some((s) => (hi + " " + en).includes(s))) {
        hi = "\u0905\u092D\u0940 \u0928\u0939\u0940\u0902 \u0939\u0941\u0906, \u0928\u093F\u092F\u092E \u092B\u093F\u0930 \u092A\u0922\u093C\u0924\u0947 \u0939\u0948\u0902\u0964";
        en = "Not quite yet. Let's read the rule again.";
        log.error = "leak blocked";
      }
    }
    if (!hi && !en) {
      log.error = "empty model reply";
      return finish(502, { error: log.error });
    }
    log.ok = true;
    return finish(200, { hi, en, model, ms: log.ms, tokens: log.tokens });
  } catch (e) {
    log.ms = Date.now() - t0;
    log.error = e.name === "AbortError" ? "model timeout" : "model call failed";
    return finish(502, { error: log.error });
  } finally {
    clearTimeout(timer);
  }
}
var config = { path: "/api/*" };
export {
  config,
  api_default as default
};
