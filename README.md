# Kim Quraish Beauty Studio – Booking & Payments

A Flask + SQLite full-stack app for salon booking, deposits, gift cards, and client CRM with Stripe, Resend, and EZTexting integration placeholders.

## Quickstart
1. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
2. **Run the server**
   ```bash
   flask --app app run --debug
   ```
3. The database initializes on first start with demo data.

## Default Accounts
- Admin: `kim@studio.com` / `adminpass`
- Employees: `lena@studio.com` / `employeepass`, `maya@studio.com` / `employeepass`
- Clients sign up via **/signup**.

## Environment Variables
- `FLASK_SECRET` – session secret.
- `STRIPE_SECRET_KEY` – live PaymentIntents.
- `STRIPE_TEST_KEY` – Stripe sandbox key for test-mode deposit captures.
- `RESEND_API_KEY` – enable email sends.
- `EZTEXTING_API_KEY` – enable SMS sends.

## Features
- Service listing with per-service deposits.
- Booking flow with live availability by artist, deposit capture, and confirmations by email/SMS.
- Gift card purchases with unique codes and balance tracking.
- Admin panel for services, employees, availability, time-off, and recent bookings.
- Employee dashboard for upcoming schedule and client CRM (notes, history).
- Contact form and luxury-themed marketing pages using provided brand fonts/colors.

## Deployment Notes
- SQLite database stored at `kimq.db` alongside the app file.
- When deploying on PythonAnywhere, point the WSGI entry to `app.app` and ensure env vars are set in the console.
- Replace `static/logo.jpg` with your studio logo file for the homepage hero.
