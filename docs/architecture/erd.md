# Entity-relationship diagram

The database as built at the end of Sprint 2, drawn from the Django models in `backend/apps/*/models.py`.
The source is the Mermaid block below; GitHub renders it as a diagram. Update it in the same pull request as any
model change.

Tables that later sprints add (Donor, EmergencyCase, Reservation, TransferRequest, Notification, Equipment,
OperatingRoom, Ambulance) are listed under the diagram with the sprint that adds them.

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

## Planned tables

| Table | App | Sprint | Issue |
|---|---|---|---|
| Donor, Donation, TestResult | blood | 3 | #17–#21 |
| Equipment, OperatingRoom, OperatingRoomBooking (inherit Resource) | resources | 4 | #26–#29 |
| EmergencyCase, RequirementItem | emergencies | 5 | #30–#36 |
| Reservation, Allocation | matching | 6–7 | #38–#45 |
| TransferRequest, Ambulance, Trip | transfers | 7–8 | #47–#51 |
| Notification | notifications | 8 | #52–#53 |
