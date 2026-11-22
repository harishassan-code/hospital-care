# Demo script

The final demo (and any sprint review) runs from **staging**, following these steps in order. It tells one story: a
critical patient at **CityCare General Hospital** needs three ventilators, the hospital has only two free, and the
network finds, moves and confirms the third. Bolt [B14](../aidlc/bolts/B14-staging-and-demo.md), issues #59 and #69.

**Time:** about 12 minutes for the core steps, plus up to 5 for the optional ones.
**Data:** all synthetic, from `seed_demo`. Never type real patient details, even as a joke.

## Before you start (10 minutes before)

| | |
|---|---|
| **Site** | the Vercel URL in the [README](../../README.md#staging) |
| **Wake the API** | `python3 scripts/smoke_staging.py <site>` must end with "Staging is up." (the free API sleeps after 15 min) |
| **Logins** | password for all: `CityCare-demo-1` · `doctor@`, `nurse@`, `admin@`, `bloodbank@`, `patient@` + `demo.citycare.pk` |
| **Browser** | one normal window and one private window, so two people can be signed in at once without signing out |
| **Check the data** | Equipment page (as `nurse@`): CityCare General shows **2 ventilators available** (VENT-003, VENT-005). If not, see *Reset* below |
| **Zoom** | browser zoom 125 %, so the back row can read it |

All demo staff work at CityCare General. The supplying hospital's side is shown with `admin@`, who can act for any
hospital.

## Core steps

| # | Who | Do | The audience sees | Say |
|---|---|---|---|---|
| 1 | *(anyone)* | Open the site, signed out | The public home page with **API status: up** and the emergency department status | "Anyone can see whether the ER is accepting patients, without an account." |
| 2 | `patient@` | Sign in, try `/staff` in the address bar | Sent back: patients never see the staff area | "Each role sees only its own modules; the server enforces it, not just the menu." |
| 3 | `doctor@` | Sign out, sign in as the doctor. Open **Overview** | The staff workspace with the doctor's modules only | Point out what a doctor doesn't get: Users and roles, and edit rights on the blood bank. |
| 4 | `doctor@` | **Emergencies → New case**: severity **Critical**, any patient reference (e.g. `DEMO-001`), one need: **Equipment · Ventilator · 3**. Create | The case page opens: status **Open**, critical at the top of the list | "Critical cases always sort first, and escalate on their own if nobody fulfils them in 30 minutes." |
| 5 | `doctor@` | Look at the need | **Available here: 2 · Short: 1** | "It checks our own stock first, counting what's already held for other cases." |
| 6 | `doctor@` | **Reserve 2 here** | Two holds in the Reservations panel (VENT-003, VENT-005), held for 30 minutes | "Reserving is atomic: two doctors clicking at once can't get the same ventilator." |
| 7 | `doctor@` | Scroll to **Sources in the network** | Seaview Hospital and Northside Children's Hospital, ranked, each with a score and the reason (distance, stock) | "The ranking is configurable per resource type: nearest for equipment, earliest expiry for blood." |
| 8 | `doctor@` | On the top hospital: quantity **1**, **Request transfer** | A transfer in the case's Transfers panel, status **Requested**. Nothing is reserved at the supplier yet | "The supplier stays in control of its stock until it says yes." |
| 9 | `admin@` *(private window)* | **Transfers** → the incoming request → **Approve** | Status **Approved**; the supplier's ventilator is now held for the case | "Approval reserves the unit at the supplier, in one transaction." |
| 10 | `admin@` | **Dispatch**, then **Start transit** | Status **Dispatched → In transit**, each step in the transfer's history with who and when | |
| 11 | `nurse@` *(normal window, sign out the doctor)* | **Transfers** → the outgoing transfer → confirm receipt | Status **Delivered**; the ventilator is allocated to the case | "Only the receiving hospital can confirm it arrived." |
| 12 | `nurse@` | Open the case. **Allocate** the two local holds | The need is covered: 3 of 3. Case status **Fulfilled**. The timeline shows every step | "From 'we're short' to 'covered' without a phone call, and every step is recorded." |

## Optional steps (include once merged into `main`)

Check the PR is merged and staging has redeployed before rehearsing these. Add each as a numbered step after 12.

| PR | Feature | Step |
|---|---|---|
| #104 | In-app alerts (B06, B07) | After step 8, `admin@` sees an unread alert for the new transfer request. |
| #104 | Hospital dashboard (B08) | `nurse@` opens the dashboard: open requests and transfers, refreshing on their own. |
| #104 | City command centre (B09) | `admin@` opens the command centre: stock and open cases across all hospitals. |
| #104 | Ambulances (B04, B05) | Dispatch an ambulance for the transfer in step 10 and follow the trip. |
| #104 | Audit search and export (B10) | `admin@` filters the audit log by today's date and exports the CSV: every step above is in it. |
| #104 | Donors page (B11) | `bloodbank@` opens Donors (doctors can't: it's personal data). |
| #106 | Patient transfer (B17) | Flag a critical case the hospital can't cover and move the patient. |
| #109 | Specialists (B16) | The **Available now** filter on the specialist directory. |
| B18 | Operational reports | `admin@` opens Reports for the last 30 days and exports the PDF. |

## If something goes wrong

| Problem | Fallback |
|---|---|
| The site loads but says **API status: down**, or sign-in spins | The API is waking up. Wait 30–60 s and reload. Talk through step 1 meanwhile. |
| Step 5 shows fewer than 2 available | Earlier rehearsals used them. Ask for 1 more than **Available here** in step 4, so there is still exactly one short. |
| Step 7 shows no sources | The partner hospitals' ventilators were used up by a rehearsal. Reset (below), or show the ranking on a blood need instead (e.g. 10 units of O−). |
| A hold disappeared | Holds expire after 30 minutes. Reserve again; holds that belong to an approved transfer never expire. |
| **403** on a change | The CSRF origin on Render doesn't match the site URL. Fix `CSRF_TRUSTED_ORIGINS` (deployment guide) after the demo, and show the rest read-only. |
| Staging is down completely | Run it locally (`docker compose up --build`, then `seed_demo`) and present from `localhost`. |

## Reset after a rehearsal

From the Render dashboard, open the API service's **Shell** and run:

```bash
python manage.py seed_demo --reset
```

This clears and re-creates hospitals, stock and equipment. Emergency cases and transfers from rehearsals stay in the
list; that's fine, and new ones sort by severity and age.

## Rehearsals

| Date | Who | Result | Fixes |
|---|---|---|---|
| | | | |
