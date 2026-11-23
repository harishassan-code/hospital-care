# User manual

How to use Hospital Care (CityCare), by role and by task. WBS 10.3.2 .2 ("Write the user manual").
For running the system see the [README](../../README.md); for a scripted walkthrough see the
[demo script](demo-script.md).

> Academic project. All data is synthetic and all clinical rules are simulated. Don't enter real patient data.

## The public site (no sign-in)

- **Home page** (`/`): what CityCare is, **the network right now** (how many emergency departments are accepting
  patients, the shortest wait and where, ambulances free, and beds and blood across the city as levels: Available,
  Limited or Full for beds; OK, Low or Critical for blood), and **the member hospitals**, shortest emergency wait first.
  **Use my location** sorts them nearest first; your location stays on your device and is never sent anywhere.
- **A hospital's page** (`/hospitals/<id>`): its emergency department (status, estimated wait, people waiting), who is
  on duty now by specialty, its beds as levels, and its services and departments. Doctors' names are shown only to
  signed-in hospital staff. Exact stock and anything about patients are never shown here.
- In an emergency, call **1122**; the number is on every public page.

## 1. Signing in

1. Open the site and choose **Log in**. On a local install that is `http://localhost:5173/login`.
2. Enter your email and password. Demo accounts all use the password `CityCare-demo-1`
   (`admin@`, `doctor@`, `nurse@`, `bloodbank@`, `pharmacist@`, `patient@` + `demo.citycare.pk`).
3. Staff land in the **staff workspace** (`/staff`). Patients land on the public home page.

After 5 wrong passwords in a row the account is locked for 15 minutes. A session ends after 30 minutes without
activity; sign in again to continue.

New patients can create their own account with **Create an account** (`/signup`). To add a staff member, they sign
up the same way, and an admin then gives them a role and the hospital they work at on **Users and roles** (see §8).

## 2. The staff workspace

- **Sidebar:** only the modules your role may use. Opening another module's address shows "no access"; the server
  refuses the request as well, so hiding is not the only protection.
- **Top bar:** the current page, your shift, and the **bell**. The bell counts your unread notifications plus items
  that need attention (low stock, units near expiry, beds slow to clean).
- **Critical alerts** appear as a banner at the top of every page until you acknowledge them.

### What each role can do

| Module | Admin | Doctor | Nurse | Blood bank | Pharmacist |
|---|---|---|---|---|---|
| Overview, Alerts | view | view | view | view | view |
| City command centre | view | – | – | – | – |
| Emergencies | edit | edit | edit | view | view |
| Transfers | edit | edit | edit | edit | – |
| Beds | edit | view | edit | – | – |
| Blood bank | edit | view | – | edit | – |
| Donors | edit | – | – | edit | – |
| Pharmacy | edit | view | view | – | edit |
| Equipment | edit | view | edit | – | – |
| Operating rooms | edit | view (books slots) | edit | – | – |
| Ambulances | edit | view | edit | – | – |
| Hospitals | edit | view | view | view | view |
| Specialists | edit | view | edit (own hospital) | view | view |
| Users and roles, Audit log, Reports | admin only | – | – | – | – |

Everyone except admins sees and changes only their own hospital's records. The table is kept in step with the
server's rules in [api-contracts.md](../architecture/api-contracts.md).

## 3. Overview (hospital dashboard)

Shows your hospital at a glance: bed occupancy, red-cell stock by blood group against its minimum, pharmacy stock,
open emergencies and pending transfers. It refreshes on its own; you don't need to reload.

## 4. Emergencies

### Our emergency department (admin, doctor, nurse)
The **Our emergency department** panel on **Emergencies** sets what the public sees for your hospital: the status
(accepting patients, very busy, not accepting ambulances), how many people are waiting and the estimated wait. Change
the figures and choose **Update status**; the public pages show it at once, and the change is recorded in the audit
log. Other roles see the panel without the form. The **Emergency** tile on the overview shows the same figures.

### Open a case (doctor, nurse, admin)
1. **Emergencies → New case.**
2. Choose a **severity** (critical, high, moderate, low) and an optional patient reference (a tag, never a name).
3. Add one or more **needs**: blood (group, component, units), a bed (type), equipment (type) or an operating room
   (capability), each with a quantity.
4. **Create.** The case opens with status **Open**. Critical cases always sort first.

### Cover the needs
- Each need shows **Available here** and **Short**. Stock already held for other cases is not counted.
- **Reserve here** holds local units for 30 minutes. Two people can't hold the same unit.
- **Sources in the network** ranks other hospitals that have what you're short of, with a score and the reason
  (distance and travel time, stock, expiry for blood).
- **Request transfer** from a ranked hospital (blood and equipment). See §5.
- **Allocate** a hold once the resource is in use. When every need is covered the case becomes **Fulfilled**.

### Case status
Use **Update status** to start matching, escalate, close (an outcome note is required) or cancel. A critical case
left in the same status too long is escalated automatically, and staff get a critical alert. Closing or cancelling a
case cancels its open transfers and releases their holds. The **Status history** lists every step with who and when.

### Patient transfer
When your hospital can't cover a critical case, the case page lets you move the **patient** instead: choose a
destination hospital that has what the case needs, and follow the transfer until arrival.

## 5. Transfers

**Incoming** lists requests other hospitals sent you; **Outgoing** lists the requests you sent.

| Step | Who | What happens |
|---|---|---|
| Request | the case's hospital | Nothing is reserved at the supplier yet |
| **Approve** / **Reject** | the supplier (blood bank for blood, nurse for equipment, or admin) | Approval holds the units at the supplier; rejection needs a reason |
| **Dispatch**, **Start transit** | the supplier | Optionally with an ambulance (§7) |
| **Confirm receipt** | the receiving hospital | The units move to the receiver and are allocated to the case |
| **Cancel** | the requester, before receipt | Any holds are released |

Every step is recorded in the transfer's history and the audit log, and the other side gets a notification.

## 6. Resources

- **Beds:** the bed board by ward. Change a bed's status (free, occupied, reserved, cleaning, out of service).
- **Blood bank:** register a unit (donation number, group, component; expiry defaults from the component's shelf
  life), record screening results, release, issue or discard (with a reason). The stock grid shows each group against
  its minimum; near-expiry units are flagged.
- **Donors:** register donors, record a screening (eligible, or deferred until a date), and book or cancel
  donation appointments on free slots.
- **Pharmacy:** medicine stock and batches.
- **Equipment:** register equipment (asset tag, type, location) and change its status (in use, maintenance, out of
  service).
- **Operating rooms:** register rooms and their capabilities; book and cancel slots on the day schedule. Clashing
  bookings are refused.
- **Specialists:** the staff directory with on-call windows; **Available now** filters to who is on call.

## 7. Ambulances

The fleet with each vehicle's type and status. Nurses and admins register vehicles and take them in and out of
service. A supplying hospital can dispatch an available ambulance with an approved transfer; the transfer shows the
trip, the ambulance and the estimated arrival time.

## 8. Administration (admin)

- **Hospitals:** register hospitals (address, location, capabilities) and their departments, wards and storage
  locations.
- **Users and roles:** change a person's role and the hospital they work at; deactivated accounts are marked.
  Doctors, nurses, blood bank and pharmacists need a hospital (admins may have none, and then see every hospital).
  A new staff member signs up first, then gets their role and hospital here. Accounts are deactivated in Django
  admin (`/admin/`, which is switched off on staging).
- **City command centre:** every hospital in one table: free beds and ICU, blood by group, near-expiry units,
  equipment, active emergencies, with shortages highlighted.
- **Audit log:** search every recorded action by person, action, entity and date, and export the result as CSV.
  The log can't be edited or deleted.
- **Reports:** requests, fulfilment time and blood wastage over a date range, for one hospital or all; export as
  CSV or PDF.

## 9. Alerts

**Alerts** lists your notifications, newest first, with a read/unread filter. Opening one marks it read. Critical
ones (a new critical case, an escalation, a transfer request to your hospital) stay as a banner until you choose
**Acknowledge**.

## 10. If something goes wrong

| What you see | What to do |
|---|---|
| "The hospital's system didn't respond" | The API is unreachable or asleep (staging sleeps after 15 minutes). Wait a moment and try again |
| "No access" on a page | Your role can't use that module; ask an admin if you need it |
| "Someone else changed this first" | Another user moved the same record. The page shows the latest state; try again |
| Locked out after wrong passwords | Wait 15 minutes, then sign in again |
