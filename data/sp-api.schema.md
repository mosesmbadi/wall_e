# sp-api Database — Schema Annotation

This file teaches the SQL generator the business relationships, value enumerations,
and naming conventions specific to this database. Add to it whenever new tables or
conventions are discovered.

---

## Key Relationships (Foreign Keys)

| Child table                    | FK column               | Parent table                   | Parent PK | Notes                                                      |
| ------------------------------ | ----------------------- | ------------------------------ | --------- | ---------------------------------------------------------- |
| `facilities_facilityequipment` | `facility_id`           | `facilities_facility`          | `id`      | Bridge table — one facility has many equipment             |
| `facilities_facilityequipment` | `equipment_id`          | `catalog_equipment`            | `id`      | Equipment catalogue entry                                  |
| `facilities_facilityuser`      | `facility_id`           | `facilities_facility`          | `id`      | Users assigned to a facility                               |
| `facilities_facilityuser`      | `user_id`               | `accounts_customuser`          | `id`      |                                                            |
| `facilities_facility`          | `region_id`             | `facilities_region`            | `id`      | Geographic region                                          |
| `jobs_job`                     | `facility_equipment_id` | `facilities_facilityequipment` | `id`      | Job is performed on a specific facility-equipment instance |
| `jobs_job`                     | `contract_id`           | `jobs_contract`                | `id`      | Optional contract covering the job                         |
| `jobs_job`                     | `assigned_to_id`        | `accounts_customuser`          | `id`      | Engineer assigned                                          |
| `jobs_job`                     | `assigned_by_id`        | `accounts_customuser`          | `id`      | Manager who assigned                                       |
| `jobs_job`                     | `closed_by_id`          | `accounts_customuser`          | `id`      |                                                            |
| `jobs_job`                     | `requested_by_id`       | `accounts_customuser`          | `id`      |                                                            |
| `jobs_ticket`                  | `job_id`                | `jobs_job`                     | `id`      |                                                            |
| `jobs_equipmentcontract`       | `equipment_id`          | `catalog_equipment`            | `id`      |                                                            |
| `jobs_contract`                | `facility_id`           | `facilities_facility`          | `id`      |                                                            |
| `attendance_attendance`        | `user_id`               | `accounts_customuser`          | `id`      |                                                            |
| `staff_mileage`                | `user_id`               | `accounts_customuser`          | `id`      |                                                            |
| `stock_take_stocktakeitem`     | `facility_id`           | `facilities_facility`          | `id`      |                                                            |

---

## Value Enumerations

### `jobs_job.status`

- `DONE` — job is completed
- `Pending` — job is pending / not yet started
- `OPEN` — job is in progress / open

### `jobs_job.title` (job type)

- `PPM` — Planned Preventive Maintenance
- `REPAIR` — Reactive repair job
- `APPLICATION` — Application/installation job

---

## Human-Readable Name Columns

| Table                 | Name column               | Notes                                                                                                                                                                   |
| --------------------- | ------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `facilities_facility` | `name`                    | Names often contain apostrophes and dashes, e.g. "Nairobi Women's - Adams", "Aga Khan Nairobi" — always use ILIKE with individual keyword tokens, never the full phrase |
| `facilities_region`   | `name`                    | e.g. "Nairobi", "Coast"                                                                                                                                                 |
| `catalog_equipment`   | `name`                    | e.g. "Hematology Analyzer", "Coagulation Analyzer"                                                                                                                      |
| `accounts_customuser` | `first_name`, `last_name` | Use CONCAT for full name                                                                                                                                                |

---

## Common Query Patterns

### Equipment at a facility

Facility names in this database contain apostrophes and hyphens (e.g. "Nairobi Women's - Adams").
When filtering by facility name from user input, **split the user's keywords and match each separately**, or use the most unique keyword with ILIKE.

Example — user asks for "equipment at Nairobi Womens Adams":

```sql
SELECT ce.name AS equipment_name, COUNT(*) AS total
FROM facilities_facilityequipment fe
JOIN facilities_facility ff ON ff.id = fe.facility_id
JOIN catalog_equipment ce ON ce.id = fe.equipment_id
WHERE ff.name ILIKE '%adams%'
GROUP BY ce.name
ORDER BY ce.name;
```

Note: `'%adams%'` is the most specific unique token here. Do NOT use `'%Nairobi Womens Adams%'` as it will not match.

### Jobs completed in a year

```sql
SELECT COUNT(*) FROM jobs_job
WHERE status = 'DONE'
AND EXTRACT(YEAR FROM date_completed) = 2025;
```

### Jobs at a specific facility

```sql
SELECT j.*
FROM jobs_job j
JOIN facilities_facilityequipment fe ON fe.id = j.facility_equipment_id
JOIN facilities_facility ff ON ff.id = fe.facility_id
WHERE ff.name ILIKE '%Nairobi Womens%';
```

### Staff attendance for a user

```sql
SELECT * FROM attendance_attendance
WHERE user_id = (
  SELECT id FROM accounts_customuser
  WHERE first_name ILIKE '%John%' AND last_name ILIKE '%Doe%'
);
```
