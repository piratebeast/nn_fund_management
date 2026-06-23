# TECHNICAL SUBMISSION PACKAGE
**Position:** Trainee Software Developer Assessment  
**Company:** NN Services & Engineering Ltd.  
**Module Name:** nn_fund_management  
**Target Odoo Version:** 19.0 Community Edition  
**Submission Date:** June 23, 2026  

---

## SECTION 1: README & ENVIRONMENT ORCHESTRATION

### 📌 Deliverable Overview
This repository contains the complete, installable Odoo custom module `nn_fund_management` designed to handle incoming corporate funds, structural project allocations, strict workflow approvals, and a continuous immutable sub-ledger system that completely eliminates double-spending risks.

### 🛠️ Required Dependencies
The module builds upon and extends the native Odoo core ecosystem. The required dependencies specified in the manifest are:
* `base` (Core Odoo Kernel)
* `project` (Project Management — for project-based fund allocation and requisition targets)
* `mail` (Chatter Network — for approval histories, logging, and audit tracking)

---

### 🚀 Dockerized Installation & Configuration

This project is fully dockerized to ensure absolute portability across multiple host systems. Follow these steps to build, configure, and initialize the system environment.

#### 1. Build and Launch the Containers
Navigate to your root orchestration directory containing the `docker-compose.yml` file in your terminal and spin up your background services:
```bash
docker compose up -d --build
```

#### 2. Compile and Initialize the Custom Module
Force the Odoo registry to pull, validate, and load the custom sub-ledger module tables, sequences, access rights, and access control matrices:
```bash
docker compose exec web odoo -d nn_fund_dev --db_host=db --db_user=odoo --db_password=odoo_db_pass -u nn_fund_management --stop-after-init
```
#### 3. Cycle Backend Worker Processes
Once the compilation pass ends safely with a clean log shutdown signature, restart the container workers to refresh active cache profiles:
```bash
docker compose restart web
```
#### 4. Accessing the Application Workspace
Open your web browser and target the live client workspace at:

URL: http://localhost:8069

Default Database Instance: nn_fund_dev

### ⚙️ Configuration Steps
To verify functional behavior across distinct organizational access tiers, establish the following security groups under Settings -> Users & Companies -> Groups:
- **Fund User:** Standard operational level. Allows creation and submission of allocation requests, fund requisitions, and internal transfers.
- **Finance User:** Authorized level to process and confirm incoming capital fund deposits.
- **GM Approver:** First tier of workflow clearance. Evaluates submitted documents and advance states to Managing Director review.
- **MD Approver:** Ultimate operational clearance tier. Confirming records releases holds and posts active sub-ledger rows.
- **Fund Administrator:** Administrative role. Holds explicit super-user authority to cancel or reverse finalized financial transactions.

### 📌 Technical Assumptions
**Exclusivity Logic:** To maintain clean financial reporting lanes, allocation requests, fund requisitions, and balance transfers must strictly adhere to an exclusive choice. Transactions must target a Project OR an Expense Head, but never both simultaneously.

**Non-Negative Inputs:** All monetary values (Transaction Amount, Requested Amount, Bill Amount) must be strictly greater than zero. Negative entries are blocked on the server side.

**Single Source of Truth Calculations:** To protect data integrity, calculated balances are never updated via direct manual edits. Values are computed in real time by summing double-entry lines in the central ledger history database table.

### ⚠️ Known Limitations
**Single Currency Context:** The module computes balances by processing numerical sums of ledger floats without managing real-time multi-currency exchange rate adjustments.

**Full Reversal on Cancellation:** Reversing a posted or approved transaction applies a complete mathematical negation row to the ledger rather than enabling selective line editing.

### ✍️ AI Tools Usage and Transparency Disclosure
Per section guidelines, below is the required transparency log documenting design collaboration with AI:

**AI Tools Used:** Claude / Google Gemini.

**Parts Developed with AI Assistance:** - Structural layout configuration of the abstract approval workflow class mixin (approval_mixin.py).

- Baseline boilerplate scaffolding templates for the XML form, list, and statusbar view files.

**Errors Found in AI-Generated Code & Corrected:**

- AI initially outputted a flat, static numerical float column for tracking account and project balances, which posed desynchronization risks. This was completely rewritten into real-time dynamic compute methods referencing ledger logs.

- AI generated an invalid non-existent Odoo model category descriptor configuration tag (res.groups.privilege), which instantly crashed database module initialization. This was stripped and corrected to standard Odoo security groups.

- 
## ✍️ Authors

- [@shishir](https://github.com/piratebeast)
