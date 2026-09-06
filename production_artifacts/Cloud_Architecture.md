# Cloud Architecture: TrustFork on 100% Free Cloud (Render.com / Fly.io)

**Author:** Cloud Product Management (`@cloud_pm`)  
**Status:** PROPOSED (Pending Approval)  
**Target Cloud:** Render.com (Primary) / Fly.io (Alternative)  
**Hosting Model:** 100% Free-Tier Containerized Web Service  
**Financial Cost:** **$0.00 / Month (Completely Free Forever — No Credit Card Billing)**  

---

## 1. Executive Summary & Zero-Cost Mandate

The user has explicitly mandated a **100% Free Cloud Deployment** with **zero immediate or recurring costs**. 

To satisfy this constraint while preserving TrustFork's distributed systems showcase (FastAPI async engine, Web UI console, Merkle DAG, Ed25519 cryptography, and SQLite Saga store), the architecture targets **Render's Free Web Service Tier** (with automated GitHub continuous deployment and free SSL/TLS).

### Zero-Cost Workload Specifications
- **Hosting Tier:** Render Free Web Service (`free` instance type: 512 MB RAM, 0.1 CPU).
- **Monthly Cost:** **$0.00 / month (Free Forever)**.
- **TLS / HTTPS:** Automated Let's Encrypt SSL (`https://trustfork.onrender.com`) at **$0.00**.
- **Continuous Deployment:** Automatic build & redeploy on `git push origin main` via GitHub webhooks at **$0.00**.
- **Bandwidth:** 100 GB/month included free.

---

## 2. Target Free Cloud Architecture Topology

```
                                [ Evaluators / Browsers / Public Web ]
                                                  │
                                                  ▼
                         ┌─────────────────────────────────────────────────┐
                         │   Render Global Cloud Edge & Anycast CDN        │
                         │   - Automated Free Managed TLS (Let's Encrypt)  │
                         │   - Free Domain: `https://<app>.onrender.com`   │
                         │   - Built-in DDoS Shield & HTTP/2 Ingress       │
                         └────────────────────────┬────────────────────────┘
                                                  │ Port 443 -> $PORT
                                                  ▼
                         ┌─────────────────────────────────────────────────┐
                         │   Render Free Container Runner (512 MB RAM)     │
                         │   Service: `trustfork-web`                      │
                         │   - Python 3.12 / Multi-stage Docker Container  │
                         │   - Fast Uvicorn Server on 0.0.0.0:$PORT        │
                         │   - Serves High-Tech Web UI & REST API Endpoints│
                         └────────────────────────┬────────────────────────┘
                                                  │
                                                  ▼
                         ┌─────────────────────────────────────────────────┐
                         │   Local Application Data Store                  │
                         │   Path: `/app/data/saga.db`                     │
                         │   - SQLite WAL Mode (Zero-cost local storage)   │
                         │   - Auto-initialized Genesis Policy DAG         │
                         └─────────────────────────────────────────────────┘
```

---

## 3. Component Breakdown & Service Mapping

### 3.1. Compute: Render Free Web Service
- **Deployment Strategy:** `render.yaml` Blueprint or native Dockerfile build from GitHub.
- **Sleep / Wake Cycle:** Free tier spins down after 15 minutes of inactivity; spins up automatically upon incoming HTTP request within 20–30 seconds.
- **Health Checks:**
  - **Health Check Path:** `/api/state` (HTTP 200).
- **Port Binding:** Reads `$PORT` dynamically from Render's runtime environment (defaults to `8000` locally).

### 3.2. Data Persistence in Free Tier
- **Storage Strategy:** Container filesystem storage under `app_build/data/saga.db` or `/tmp/saga.db`.
- **Durability Behavior:** SQLite WAL mode ensures transactional durability across API requests and graceful restarts. (For zero-cost hosting, state resets on manual redeploy, which acts as a convenient clean-slate demo reset for evaluators).

### 3.3. Security & Cloud Best Practices
- **Non-Root Execution:** Multi-stage Docker build running under unprivileged `appuser`.
- **Zero Secrets in Code:** Environment variable injection via `render.yaml`.
- **HTTPS Enforcement:** Free automatic SSL certificate renewal.

---

## 4. Environment Variables Configuration

| Variable Name | Value | Purpose |
| :--- | :--- | :--- |
| `PORT` | `10000` (Assigned by Render) | Container HTTP listener port. |
| `HOST` | `0.0.0.0` | Bind host address. |
| `DATA_DIR` | `./data` | Application data folder. |
| `SAGA_DB_PATH` | `./data/saga.db` | SQLite database file location. |
| `ENVIRONMENT` | `production-free` | Runtime indicator. |

---

## 5. Sequential Execution Roadmap

- **Phase 2 (Cloud Engineer):** Verify environment-driven port and database configuration in `server.py` and `saga_store.py`.
- **Phase 3 (Security & QA):** Audit codebase for zero hardcoded secrets and cloud readiness.
- **Phase 4 (Cloud Architect):** Generate `render.yaml` (Render Infrastructure Blueprint), production `Dockerfile`, and local `docker-compose.yml`.
- **Phase 5 (DevOps Master):** Provide step-by-step 1-click deploy link or CLI deploy commands to launch the live free URL.

---

## 6. Socratic Hard Stop Approval

This architecture satisfies the user's requirement for a **100% Free Cloud Deployment ($0.00)** with zero credit card billing risk.
