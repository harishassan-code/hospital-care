# Entity-relationship diagram

The database as built at the end of Sprint 2, drawn from the Django models in `backend/apps/*/models.py`.
The source is the Mermaid block below; GitHub renders it as a diagram. Update it in the same pull request as any
model change.

The second diagram, [Planned MVP schema](#planned-mvp-schema-proposed), proposes the tables later sprints add.
Together they cover the entities in the proposal's database design (§11): users, hospitals, resources, blood,
requests, reservations, transfers, notifications and audit.

```mermaid
erDiagram
    User }o--o| Hospital : "works at"
    Hospital }o--o{ Capability : has
    Hospital ||--o{ Department : has
    Hospital ||--o{ Ward : has
    Hospital ||--o{ StorageLocation : has
    Department |o--o{ Ward : groups
    Ward ||--o{ Bed : contains
    Hospital ||--o{ Bed : owns
    Hospital ||--o{ BloodUnit : owns
    StorageLocation |o--o{ Bed : "stored at"
    StorageLocation |o--o{ BloodUnit : "stored at"
    Medicine ||--o{ Batch : "stocked as"
    User |o--o{ AuditLog : "acted in"

    User {
        bigint id PK
        string email UK "case-insensitive"
        string role "admin|doctor|nurse|bloodBank|pharmacist|patient"
        string phone
        bigint hospital_id FK "null for patients and network admins"
        bool is_active
        bool is_superuser "always acts as admin"
    }
    Hospital {
        bigint id PK
        string name UK "case-insensitive"
        string type "hospital|bloodBank"
        string address
        decimal latitude "-90..90"
        decimal longitude "-180..180"
        string phone
        bool is_active "deactivated = left out of matching"
    }
    Capability {
        bigint id PK
        string code UK
        string name
    }
    Department {
        bigint id PK
        bigint hospital_id FK
        string name "unique per hospital"
    }
    Ward {
        bigint id PK
        string code UK "bed board id"
        bigint hospital_id FK
        bigint department_id FK "optional"
        string name "unique per hospital"
        string kind
        int sort_order
    }
    StorageLocation {
        bigint id PK
        bigint hospital_id FK
        string name "unique per hospital"
    }
    Bed {
        bigint id PK
        string label UK "API id"
        bigint ward_id FK
        string bed_type "icu|emergency|general|isolation|nicu"
        bigint hospital_id FK "Resource: = ward's hospital"
        bigint storage_location_id FK "Resource"
        string status "occupied|reserved|cleaning|free|outOfService"
        datetime status_since "Resource"
        string patient_initials
        int patient_age
        string patient_sex
        datetime admitted_at
        date expected_discharge
        string isolation
    }
    BloodUnit {
        bigint id PK
        string donation_number UK "ISBT 128"
        string group "O-..AB+"
        string component "redCells|plasma|platelets|cryo"
        datetime collected_at
        datetime expires_at "after collected_at"
        string status "quarantined|available|reserved|issued|expired"
        string location "label, kept until Sprint 3"
        bigint hospital_id FK "Resource"
        bigint storage_location_id FK "Resource"
        datetime status_since "Resource"
    }
    Medicine {
        bigint id PK
        string code UK
        string name
        string strength
        int reorder_level
        decimal daily_use
        bool high_alert
        bool controlled
    }
    Batch {
        bigint id PK
        bigint medicine_id FK
        string number "unique per medicine"
        date expires_on
        int quantity
    }
    DoctorShift {
        bigint id PK
        string name
        string department
        time start
        time end
    }
    EmergencyStatus {
        bigint id PK "always 1"
        string status
        int wait_minutes
        int waiting_count
    }
    AuditLog {
        bigint id PK
        datetime at
        bigint actor_id FK "null if account deleted"
        string actor_email
        string action
        string target_type
        string target_id
        json before
        json after
        string reason
    }
```

`Bed` and `BloodUnit` share the abstract `Resource` columns (`hospital`, `storage_location`, `status_since`).
See [resources.md](resources.md) for the status lifecycles and the audit log. `Medicine`, `DoctorShift` and
`EmergencyStatus` still belong to the single demo hospital. Tying them to `Hospital` is part of their next stories.

## Planned MVP schema (proposed)

A proposal for the team to review at each story's refinement, not built yet. Names and states come from the
proposal (§11) and the backlog's acceptance criteria. Existing tables appear only by name. Every lifecycle uses
the shared `StateMachine`, and every status change is audit-logged ([resources.md](resources.md)).

```mermaid
erDiagram
    Donor ||--o{ Donation : gives
    Donation ||--o{ BloodUnit : "split into"
    BloodUnit ||--o{ TestResult : "screened by"
    Hospital ||--o{ EmergencyRequest : raises
    User ||--o{ EmergencyRequest : "created by"
    EmergencyRequest ||--|{ RequestItem : needs
    RequestItem ||--o{ Reservation : "held by"
    Reservation }o--|| BloodUnit : "holds (or another Resource)"
    Reservation ||--o| Allocation : "confirmed as"
    EmergencyRequest ||--o{ TransferRequest : "may need"
    TransferRequest }o--|| Hospital : "supplied by"
    TransferRequest ||--|{ TransferItem : moves
    TransferItem }o--|| BloodUnit : unit
    TransferRequest |o--o| Trip : "carried by"
    Ambulance ||--o{ Trip : drives
    Hospital ||--o{ Ambulance : "based at"
    Hospital ||--o{ Equipment : owns
    Hospital ||--o{ OperatingRoom : owns
    OperatingRoom ||--o{ RoomBooking : "booked as"
    User ||--o{ Notification : receives

    Donor {
        bigint id PK
        string code UK "synthetic identity only"
        string blood_group
        date last_donation "minimum interval enforced"
    }
    TestResult {
        bigint id PK
        bigint blood_unit_id FK
        string test "HIV, HBV, HCV, syphilis, malaria..."
        bool passed
        string reason "required when failed"
    }
    EmergencyRequest {
        bigint id PK
        bigint hospital_id FK
        bigint created_by_id FK
        string severity "critical|urgent|routine"
        string status "open|matching|partiallyFulfilled|fulfilled|escalated|closed|cancelled"
        string outcome_note "required to close"
        datetime escalate_after
    }
    RequestItem {
        bigint id PK
        bigint request_id FK
        string resource_type "blood|bed|equipment|operatingRoom"
        string blood_group "blood only"
        string component "blood only"
        int quantity "> 0"
        int fulfilled "never above quantity"
    }
    Reservation {
        bigint id PK
        bigint request_item_id FK
        string resource "content type + id"
        string status "held|allocated|released|expired"
        datetime expires_at "configurable hold time"
    }
    Allocation {
        bigint id PK
        bigint reservation_id FK
        bigint allocated_by_id FK
        datetime at
    }
    TransferRequest {
        bigint id PK
        bigint request_id FK
        bigint from_hospital_id FK
        bigint to_hospital_id FK
        string status "requested|approved|dispatched|inTransit|delivered|rejected|cancelled"
        string reason "required to reject"
    }
    Ambulance {
        bigint id PK
        string code UK
        string type
        bigint base_hospital_id FK
        string status "Resource"
    }
    Trip {
        bigint id PK
        bigint ambulance_id FK
        string status "dispatched|enRoute|arrived|completed"
    }
    Equipment {
        bigint id PK
        string code UK
        string type
        string status "available|inUse|maintenance|outOfService"
    }
    OperatingRoom {
        bigint id PK
        string name
        string capabilities "e.g. cardiac, trauma"
    }
    RoomBooking {
        bigint id PK
        bigint room_id FK
        datetime start
        datetime end "no overlap per room: DB exclusion constraint"
    }
    Notification {
        bigint id PK
        bigint user_id FK
        string event
        bool read
    }
```

Two differences from the proposal's entity list to settle in refinement:

- The proposal lists **Role** as an entity. Roles are a fixed list in code today (`accounts.Role`, see #9).
- The proposal lists **TransferStatusHistory** and **CompatibilityRule**. Status history currently comes from the
  audit log (ADR-7). Compatibility rules are documented in `docs/domain/blood-compatibility.md`, and #37 decides
  whether they become a table.

| Table | App | Sprint | Issues |
|---|---|---|---|
| Donor, Donation, TestResult | blood | 3 | #17–#21 |
| Equipment, OperatingRoom, RoomBooking (Equipment inherits Resource) | resources | 4 | #26–#29 |
| EmergencyRequest, RequestItem | emergencies | 5 | #30–#36 |
| Reservation, Allocation | matching | 6–7 | #38–#45 |
| TransferRequest, TransferItem, Ambulance, Trip | transfers | 7–8 | #47–#51 |
| Notification | notifications | 8 | #52–#53 |
