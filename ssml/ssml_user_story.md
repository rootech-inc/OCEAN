# SSML Operations Portal User Story

## Title
SSML Operations Portal for Inventory, Contractors, and Billing

## As a
SSML operations manager

## I want
A centralized SSML app that lets me manage contractors, track inventory and work orders, and generate invoices and compliance records.

## So that
I can run field operations efficiently, maintain stock accuracy, and ensure contractor billing and compliance are handled correctly.

---

## Description
The SSML portal should provide a dashboard for material stock, contractor performance, service orders, and financial status. It should enable creation and editing of contractors, issue and receive inventory, track service orders, generate contractor invoices, and manage FOC compliance and document uploads.

---

## Acceptance Criteria

### Dashboard
- Displays total installations, today’s installs, reorder alerts, average installs per day/month, best contractor, and billable stock estimate.
- Shows locations and current material reorder recommendations.

### Contractor Management
- User can add new contractors with company, owner, contact, address, bank, and compliance fields.
- User can view contractor details, jobs, material balances, returns, and ledger summary.
- User can edit contractor profile and update contractor status.

### Inventory Management
- User can record GRN receipts and create issue records.
- User can view material stock by location, cardex history, and low-stock alerts.
- User can transfer inventory between locations and track stock movements.

### Work Order Tracking
- User can create new service orders and upload service order data.
- User can filter service orders by contractor, status, and location.
- User can close pending jobs and update service order status.

### Billing and Compliance
- User can generate contractor invoices and ECG invoices.
- User can manage petty cash, expense requests, and upload financial evidence.
- User can create and validate FOC compliance records and contractor documents.

### Reports and Exports
- User can export contractor data, materials reports, returns reports, and job summaries to Excel/PDF.
- User can download contractor material balances and returns statements.

---

## Example User Story Card

**Title:** Contractor and Inventory Operations in SSML

**As a** SSML operations manager  
**I want** to manage contractors, inventory, and service orders in one place  
**So that** I can track stock, support field teams, and issue invoices accurately

**Acceptance Criteria**
- Dashboard shows installations, materials, and reorder alerts
- Contractor profile page shows ledger summary, jobs, and balances
- Inventory module supports GRN, issue, transfer, and cardex history
- Billing module supports invoice creation, FOC validation, and expense requests
- Export data to Excel/PDF for reporting
