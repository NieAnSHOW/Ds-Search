# SearchBench live API implementation plan

**Goal:** Run real searches against five providers with one-run, memory-only keys, then review and compare real evidence.

**Architecture:** A Python standard-library server binds only to 127.0.0.1 and serves Benchmark.html plus fixed same-origin endpoints. The browser sends one provider key per search request; neither side persists keys, request bodies, or responses. Results and human annotations remain in page memory until explicitly exported without credentials.

## Constraints

- Preserve Temp.html-derived visual identity and unrelated working-tree changes.
- Never read existing credentials or write supplied keys to storage, logs, URLs, exports, or error text.
- Key inputs clear at run start; the run closure clears key references on finish/cancel/pagehide. Python request-local secrets release in finally. No promise of physical RAM zeroization.
- Fixed official HTTPS provider endpoints, no redirects/proxy-environment credential forwarding, bounded request/response sizes and timeouts.
- Same-origin JSON requests require runtime anti-CSRF token; static serving is allowlisted and responses use no-store.
- Missing/failed/empty results are distinct. Unreviewed quality metrics are null, never fabricated.

## Tasks

- [x] Backend: write failing tests for five provider contracts, malicious/secret-bearing responses, invalid requests and local HTTP boundaries; implement server and adapters; run tests.
- [x] Frontend: replace synthetic execution with one-run key inputs, question editor, progress/cancel, real results, result review, evidence coverage and manually judged relevance rate; exports exclude credentials. nDCG remains out of scope until a graded reference pool exists.
- [x] Integration: exercise full UI with synthetic test keys and mocked provider transport only; verify cleanup, annotation, cancellation, exports and mobile layout.
- [x] Independent code/security review; fix issues; run repository checks and document launch/use and live-test limitations.

## API contract

GET /api/health -> {ok:true, csrf_token:string, providers:[string,...]}.

POST /api/search, JSON + X-Benchmark-Token -> {provider, key, query, top_k, mode?}; one query and provider per request. Supported modes: provider default (fixed reproducible request parameters).

Success: {ok:true, provider, query, mode, elapsed_ms, http_status:200, results:[{rank,title,url,snippet,content,published_at,site_name}], usage:object, cost:null, raw:object}. Every returned string is scrubbed against the submitted key.

Failure: {ok:false, provider?, error:{code,message}, elapsed_ms?, http_status:number|null}; no upstream body/exception text. Validation uses 400; upstream auth/quota/network/schema failures return safe structured errors. The frontend records bridge HTTP status separately from provider HTTP status.

## Verification focus

- Cross-origin sites cannot make credentialed calls through the loopback service.
- Redirection, malformed JSON, business failures with HTTP 200, and unknown schemas fail visibly.
- Provider text is untrusted and rendered as text; result links accept HTTP(S) only.
- Partial and cancelled runs cannot count unattempted requests as successful or rejected content.
- Human annotations and coverage denominators remain explicit, with metrics pending until required judgments exist.

## Verification evidence

- Repository suite: 102 tests run, 100 passed and 2 optional skills-CLI integration tests skipped; 24 benchmark backend tests included.
- JavaScript syntax and repository metadata/reference validation passed.
- Browser checks used synthetic keys and a local mocked provider transport, with no external search calls: input clearing, cancellation, reload clearing, empty versus failed responses, literal rendering of hostile HTML, manual annotation aggregation, credential-free JSON export, upstream 401 preservation, and 390px layout.
- Five official request contracts were checked; Metaso response normalization follows the cited community adapter and awaits a first real-account response. No real credentials were read or used during verification.
