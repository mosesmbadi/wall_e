# somastories Database — Schema Annotation

This file teaches the SQL generator the business relationships, value enumerations,
and naming conventions specific to this database.

---

## Overview

`somastories` is a storytelling platform. Authors publish **stories** (standalone)
and **chapter_series** (multi-chapter works). Readers use a **token economy** to
unlock premium content. The platform also supports **podcasts**, **bookmarks**,
**comments**, and **author payouts** via M-Pesa.

---

## Key Relationships (Foreign Keys)

| Child table            | FK column                | Parent table           | Notes                       |
| ---------------------- | ------------------------ | ---------------------- | --------------------------- |
| `stories`              | `author_id`              | `users`                | Author of the story         |
| `chapters`             | `chapter_series_id`      | `chapter_series`       | Chapters belong to a series |
| `chapter_series`       | `author_id`              | `users`                | Author of the series        |
| `bookmarks`            | `user_id`                | `users`                |                             |
| `bookmarks`            | `story_id`               | `stories`              |                             |
| `bookmarks`            | `category_id`            | `bookmark_categories`  |                             |
| `bookmarks`            | `bookmark_collection_id` | `bookmark_collections` |                             |
| `bookmark_categories`  | `user_id`                | `users`                |                             |
| `bookmark_collections` | `user_id`                | `users`                |                             |
| `comments`             | `author_id`              | `users`                | Comment author              |
| `comments`             | `story_id`               | `stories`              |                             |
| `comments`             | `parent_id`              | `comments`             | For threaded replies        |
| `follows`              | `follower`               | `users`                | User who follows            |
| `follows`              | `following`              | `users`                | User being followed         |
| `user_profiles`        | `user_id`                | `users`                | Extended profile info       |
| `user_interactions`    | `user_id`                | `users`                |                             |
| `user_interactions`    | `story_id`               | `stories`              |                             |
| `transactions`         | `user_id`                | `users`                | Token credit/debit ledger   |
| `payment_requests`     | `user_id`                | `users`                | M-Pesa STK push requests    |
| `payment_requests`     | `offer_id`               | `offers`               | Token bundle purchased      |
| `payment_methods`      | `user_id`                | `users`                |                             |
| `purchases`            | `user_id`                | `users`                |                             |
| `purchases`            | `transaction_id`         | `transactions`         |                             |
| `unlocked_stories`     | `user_id`                | `users`                |                             |
| `unlocked_stories`     | `story_id`               | `stories`              |                             |
| `unlocked_stories`     | `author_payout_id`       | `author_payouts`       |                             |
| `unlocked_chapters`    | `user_id`                | `users`                |                             |
| `unlocked_chapters`    | `chapter_id`             | `chapters`             |                             |
| `unlocked_chapters`    | `transaction_id`         | `transactions`         |                             |
| `author_payouts`       | `author_id`              | `users`                |                             |
| `author_payouts`       | `withdrawal_request_id`  | `withdrawal_requests`  |                             |
| `withdrawal_requests`  | `user_id`                | `users`                |                             |
| `withdrawal_requests`  | `initiated_by_id`        | `users`                | Admin who initiated         |
| `payout_runs`          | `initiated_by_id`        | `users`                |                             |
| `story_tags`           | `story_id`               | `stories`              |                             |
| `story_tags`           | `tag_id`                 | `api_tags`             |                             |
| `podcast_tags`         | `podcast_id`             | `podcasts`             |                             |
| `podcast_tags`         | `tag_id`                 | `api_tags`             |                             |
| `podcasts`             | `owner_user_id`          | `users`                |                             |
| `episodes`             | `podcast_id`             | `podcasts`             |                             |
| `moderator_comments`   | `story_id`               | `stories`              |                             |
| `moderator_comments`   | `moderator_id`           | `users`                |                             |
| `writer_requests`      | `user_id`                | `users`                |                             |
| `notifications`        | `recipient`              | `users`                |                             |
| `notifications`        | `sender`                 | `users`                |                             |

---

## Value Enumerations

### `stories.status`

- `published` — visible to readers
- `draft` — not yet published

### `chapters.status`

- `published` — visible to readers
- `draft` — not yet published

### `users.role`

- `reader` — standard reader account
- `writer` — approved author/writer
- `admin` — platform administrator
- `god` — super-admin with full access

### `writer_requests.status`

- `pending` — awaiting review
- `confirmed` — approved, user promoted to writer
- `rejected` — request denied

### `transactions.type`

- `earned_story_unlock` — tokens earned when someone reads your story
- `deduct_story_unlock` — tokens spent to unlock a story
- `role_promotion_bonus` — bonus tokens on becoming a writer

### `transactions.status`

- `completed` — transaction finalised

### `payment_requests.status`

- `pending` — STK push sent, awaiting callback
- `failed` — payment failed
- `completed` — payment successful (set after M-Pesa callback)

### `comments.status`

- `visible` — comment is active and visible

---

## Human-Readable Name Columns

| Table            | Name column        | Notes                                 |
| ---------------- | ------------------ | ------------------------------------- |
| `users`          | `name`, `username` | Full name or username; prefer `name`  |
| `stories`        | `title`            | Story title                           |
| `chapter_series` | `title`            | Series title                          |
| `chapters`       | `title`            | Chapter title                         |
| `podcasts`       | `title`            | Podcast title                         |
| `episodes`       | `title`            | Episode title                         |
| `api_tags`       | `name`             | Tag name (e.g. "romance", "thriller") |
| `offers`         | `name`             | Token bundle name                     |

---

## Common Query Patterns

### Count published stories

```sql
SELECT COUNT(*) FROM stories WHERE status = 'published';
```

### Stories by a specific author (user may be known by name or username)

```sql
SELECT s.title, s.reads, s.upvotes
FROM stories s
JOIN users u ON u.id = s.author_id
WHERE u.name ILIKE '%john%'
  AND s.status = 'published'
ORDER BY s.reads DESC;
```

### Top stories by reads

```sql
SELECT title, reads, upvotes
FROM stories
WHERE status = 'published'
ORDER BY reads DESC
LIMIT 10;
```

### Revenue from token purchases in a period

```sql
SELECT SUM(amount) AS total_revenue, COUNT(*) AS total_payments
FROM payment_requests
WHERE status = 'completed'
  AND created_at >= '2025-01-01'
  AND created_at < '2026-01-01';
```

### Stories unlocked by a user

```sql
SELECT s.title, us.unlocked_at
FROM unlocked_stories us
JOIN stories s ON s.id = us.story_id
JOIN users u ON u.id = us.user_id
WHERE u.username = 'some_username';
```

### Tags on a story (JOIN through story_tags)

```sql
SELECT t.name
FROM story_tags st
JOIN api_tags t ON t.id = st.tag_id
JOIN stories s ON s.id = st.story_id
WHERE s.title ILIKE '%dragon%';
```

### Writer request pipeline

```sql
SELECT u.name, u.email, wr.status, wr.requested_at, wr.reviewed_at
FROM writer_requests wr
JOIN users u ON u.id = wr.user_id
WHERE wr.status = 'pending'
ORDER BY wr.requested_at;
```

### Author payout summary

```sql
SELECT u.name, ap.amount, ap.pay_period_start, ap.pay_period_end, ap.status
FROM author_payouts ap
JOIN users u ON u.id = ap.author_id
ORDER BY ap.created_at DESC
LIMIT 20;
```

### Monthly new user signups

```sql
SELECT DATE_TRUNC('month', created_at) AS month, COUNT(*) AS new_users
FROM users
GROUP BY month
ORDER BY month;
```
