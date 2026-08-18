# Digital POS and Business Management System (v6.0)

**Author:** Harrison Alfred Ombwayo  
**Document & Software Version:** 6.0  
**Dual-Runtime Architecture:** Cloud Web Application + Packaged Offline Desktop with Bi-Directional Write-Ahead Queue Synchronization.

---

## 1. Architectural Blueprint

```
+-------------------------------------------------------+
| React Frontend (SPA / PWA)                            |
| Redux Toolkit + RTK Query / Axios + Dexie.js (IndexedDB)|
+---------------------------+---------------------------+
                            |
                    REST / WebSockets
                            |
+---------------------------v---------------------------+
| Flask Backend (REST API)                              |
| Flask-SQLAlchemy, Marshmallow, JWT, Cryptography      |
+---------------------------+---------------------------+
                            |
                      SQLAlchemy ORM
                            |
+---------------------------v---------------------------+
| PostgreSQL / SQLite Database Engine                   |
| Relational Schema + JSONB Columns                     |
+-------------------------------------------------------+
```

---

## 2. 6-Phase Pipeline Conformance

```
Phase 1: Foundation & Security ➔ Phase 2: Core Business & Inventory ➔ Phase 3: Sales Engine & Checkout
      │
      ▼
Phase 6: Desktop & Offline Sync ◄─ Phase 5: Hardware & Peripheral Integrations ◄─ Phase 4: Frontend POS Shell
```

1. **Phase 1: Foundation & Security**
   - Multi-tenant data model (`stores`, `users` with strict RBAC hierarchy: `SUPER_ADMIN`, `STORE_ADMIN`, `STORE_MANAGER`, `CASHIER`, `STAFF`).
   - Cryptographic offline licensing using asymmetric **Ed25519** digital signatures bound to host machine hardware fingerprints (`CPU/MAC/GUID` hash).
   - JWT authentication & refresh tokens with tenant isolation guards.

2. **Phase 2: Core Business & Inventory**
   - Catalog management supporting `PHYSICAL`, `SERVICE`, and `COMPOSITE_RECIPE` items.
   - Composite Recipe Engine: automatic stock deductions of raw ingredients upon sale (e.g. burgers deducting buns, patties, and cheese).
   - Low-stock threshold alerts and audit trails (`stock_adjustment_logs`).
   - Inter-Store Stock Transfers (IST): `REQUESTED` ➔ `IN_TRANSIT` ➔ `RECEIVED`.
   - Procurement module: Suppliers, Purchase Orders (PO), and Goods Received Notes (GRN).

3. **Phase 3: Sales Engine & Checkout**
   - Atomic order processing, multi-tier tax computation, line-item and order-level discounts.
   - Split Payments across multiple channels (`CASH`, `CARD`, `MOBILE_MONEY` / M-Pesa).
   - Shift management with drawer float tracking, mid-shift safe drops/payouts, and physical cash reconciliation (X-Report and Z-Report).
   - Commercial document generation: Pro-forma, formal price quotes, tax invoices, and Goods Issued Notes (GIN) with vehicle registration.

4. **Phase 4: Frontend POS Shell**
   - High-performance React SPA with Tailwind CSS, Redux Toolkit, and keyboard shortcuts (`F1`-`F4`).
   - Fast barcode scanner listener with autofocus.
   - Touch-optimized cashier register, SKU variant picker, and modifier selector.
   - Held / parked carts manager (`parkCurrentCart`, `retrieveParkedCart`).
   - F&B Table Map visual floor plan (`AVAILABLE`, `OCCUPIED`, `BILLED`).

5. **Phase 5: Hardware & Peripheral Integrations**
   - Direct raw **ESC/POS** thermal receipt command generator (80mm / 58mm receipts, cash drawer kick pulse `ESC p`, and paper cut `GS V`).
   - Dual-screen **Customer-Facing Display (CFD)** synchronized in real-time via `BroadcastChannel`.
   - Interactive **Kitchen Display System (KDS)** bump station (`PENDING` ➔ `PREPARING` ➔ `READY` ➔ `SERVED`).
   - Fiscal device compliance adapter (eTIMS / ESD signatures).

6. **Phase 6: Desktop & Offline Sync**
   - **Dexie.js (IndexedDB)** client caching for zero-latency local operations.
   - Offline Write-Ahead Logging (`offline_sync_queue`) with automatic background sync upon network reconnection.
   - Electron wrapper packaging configuration.

---

## 3. Seeded Demo Accounts & Credentials

| Tenant Store | Code | Role | Email | Password | PIN Code |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Platform Super Admin** | `SUPER-TENANT` | `SUPER_ADMIN` | `superadmin@pos.local` | `Admin@12345` | `9999` |
| **Apex Retail Mart** | `APEX-01` | `STORE_ADMIN` | `admin@apex.local` | `Apex@12345` | `1111` |
| **Apex Retail Mart** | `APEX-01` | `STORE_MANAGER` | `manager@apex.local` | `Apex@12345` | `2222` |
| **Apex Retail Mart** | `APEX-01` | `CASHIER` | `cashier@apex.local` | `Apex@12345` | `1234` |
| **Bistro Deluxe Cafe** | `BISTRO-01` | `STORE_ADMIN` | `admin@bistro.local` | `Bistro@12345` | `3333` |
| **Bistro Deluxe Cafe** | `BISTRO-01` | `CASHIER` | `waiter@bistro.local` | `Bistro@12345` | `5678` |

---

## 4. Quick Start Guide

### 4.1 Backend Setup & Database Seeding
```bash
cd backend
python -m pip install -r requirements.txt
python seeds/seed_data.py
python run.py
```
*The backend REST API will start on `http://127.0.0.1:5000`.*

### 4.2 Running Backend Automated Tests
```bash
cd backend
python -m pytest tests/
```

### 4.3 Frontend Setup & Development Server
```bash
cd frontend
npm install
npm run dev
```
*The POS frontend application will open on `http://localhost:3000`.*

### 4.4 Launch Customer Facing Display (Secondary Monitor)
Navigate to `http://localhost:3000/#cfd` or click the **CFD Screen** button in the POS header.
