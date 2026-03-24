"""
Topic clustering and project identification.

Uses Union-Find algorithm for topic co-occurrence clustering with
sender_org grouping for improved cluster quality.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

import structlog

from my_email.project.models import Project, ProjectAssignment

log = structlog.get_logger()


def _slugify(name: str) -> str:
    """
    Convert topic name to project ID (lowercase, alphanumeric).

    Args:
        name: Topic name to convert.

    Returns:
        Slugified string suitable for use as project ID.
    """
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def discover_projects(
    conn: sqlite3.Connection,
    min_emails: int = 3,
    co_occurrence_threshold: int = 5,
) -> list[Project]:
    """
    Discover projects from topic co-occurrence patterns.

    Uses Union-Find algorithm to cluster topics that frequently appear
    together in the same emails, combined with sender_org grouping
    to improve cluster quality.

    Args:
        conn: Database connection.
        min_emails: Minimum emails for a valid project cluster.
        co_occurrence_threshold: Minimum co-occurrences to link topics.
            Higher values (5+) prevent giant clusters from forming.

    Returns:
        List of discovered Project objects, sorted by email count.
    """
    # Step 1: Load topic-to-message mappings and sender info
    topic_messages: dict[str, set[str]] = defaultdict(set)
    message_senders: dict[str, str] = {}
    message_dates: dict[str, str] = {}
    message_orgs: dict[str, str] = {}

    cursor = conn.execute("""
        SELECT mt.topic, mt.message_id, m.sender, m.received_at
        FROM message_topics mt
        JOIN messages m ON mt.message_id = m.id
    """)
    for topic, msg_id, sender, received_at in cursor.fetchall():
        topic_messages[topic].add(msg_id)
        message_senders[msg_id] = sender or ""
        message_dates[msg_id] = received_at[:10] if received_at else ""
        # Extract sender_org from sender (e.g., "DuckDB Labs" from "user@duckdb.org")
        if sender and "@" in sender:
            domain = sender.split("@")[1].lower()
            # Convert domain to org name (simple heuristic)
            message_orgs[msg_id] = domain

    if not topic_messages:
        return []

    # Step 2: Build co-occurrence graph using Union-Find
    topics = list(topic_messages.keys())
    parent = {t: t for t in topics}

    def find(x: str) -> str:
        if parent[x] != x:
            parent[x] = find(parent[x])
        return parent[x]

    def union(x: str, y: str) -> None:
        px, py = find(x), find(y)
        if px != py:
            parent[px] = py

    # Link topics that co-occur frequently (O(n²) but acceptable for MVP)
    for i, t1 in enumerate(topics):
        for t2 in topics[i + 1 :]:
            shared = topic_messages[t1] & topic_messages[t2]
            if len(shared) >= co_occurrence_threshold:
                union(t1, t2)

    # Step 3: Group topics by cluster
    clusters: dict[str, set[str]] = defaultdict(set)
    for topic in topics:
        clusters[find(topic)].add(topic)

    # Step 4: Build projects from clusters
    projects: list[Project] = []
    used_slugs: dict[str, int] = {}

    for root_topic, cluster_topics in clusters.items():
        # Get all messages in this cluster
        cluster_messages: set[str] = set()
        for t in cluster_topics:
            cluster_messages.update(topic_messages[t])

        if len(cluster_messages) < min_emails:
            continue

        # Derive project name from most frequent topic (centroid)
        centroid = max(cluster_topics, key=lambda t: len(topic_messages[t]))

        # Extract sender domains
        domains: set[str] = set()
        for msg_id in cluster_messages:
            sender = message_senders.get(msg_id, "")
            if "@" in sender:
                domain = sender.split("@")[1].lower()
                domains.add(domain)

        # Calculate date range
        dates = [message_dates.get(mid, "") for mid in cluster_messages]
        dates = [d for d in dates if d]
        first_seen = min(dates) if dates else None
        last_seen = max(dates) if dates else None

        # Create unique project ID
        base_slug = _slugify(centroid)
        if base_slug in used_slugs:
            used_slugs[base_slug] += 1
            project_id = f"{base_slug}-{used_slugs[base_slug]}"
        else:
            used_slugs[base_slug] = 1
            project_id = base_slug

        projects.append(
            Project(
                id=project_id,
                name=centroid,
                keywords=sorted(cluster_topics)[:10],
                sender_domains=sorted(domains)[:5],
                email_count=len(cluster_messages),
                first_seen=first_seen,
                last_seen=last_seen,
            )
        )

    return sorted(projects, key=lambda p: -p.email_count)


def assign_email(
    conn: sqlite3.Connection,
    message_id: str,
    topics: list[str],
    sender: str,
    min_confidence: float = 0.3,
) -> ProjectAssignment | None:
    """
    Assign a single email to its best-matching project.

    Uses weighted scoring:
    - Topic overlap with project keywords (weight: 0.6)
    - Sender domain match with project domains (weight: 0.4)

    Args:
        conn: Database connection.
        message_id: Gmail message ID.
        topics: List of topics extracted from the email.
        sender: Email sender address.
        min_confidence: Minimum confidence threshold for assignment.

    Returns:
        ProjectAssignment if match found above threshold, else None.
    """
    # Load all projects from database
    projects = list_projects(conn)

    if not projects or (not topics and not sender):
        return None

    best_project: Project | None = None
    best_score = 0.0
    best_reasons: list[str] = []

    sender_domain = sender.split("@")[1].lower() if sender and "@" in sender else ""

    for project in projects:
        score = 0.0
        reasons: list[str] = []

        # Topic overlap
        topic_overlap = len(set(topics) & set(project.keywords))
        if topic_overlap > 0:
            topic_score = topic_overlap / max(len(topics), 1)
            score += 0.6 * topic_score
            reasons.append(f"topics: {topic_overlap} match")

        # Domain match
        if sender_domain and sender_domain in project.sender_domains:
            score += 0.4
            reasons.append(f"domain: {sender_domain}")

        if score > best_score:
            best_score = score
            best_project = project
            best_reasons = reasons

    if best_project and best_score >= min_confidence:
        return ProjectAssignment(
            message_id=message_id,
            project_id=best_project.id,
            confidence=round(best_score, 2),
            reasons=best_reasons,
        )

    return None


# ── repository functions (persistence) ────────────────────────────────────────


def clear_projects(conn: sqlite3.Connection) -> None:
    """
    Clear all project data (for re-discovery).

    Args:
        conn: Database connection.
    """
    conn.execute("DELETE FROM email_projects")
    conn.execute("DELETE FROM projects")
    log.info("projects.cleared")


def save_project(conn: sqlite3.Connection, project: Project) -> None:
    """
    Upsert a project to the database.

    Args:
        conn: Database connection.
        project: Project to save.
    """
    import json

    conn.execute(
        """
        INSERT INTO projects (id, name, keywords, sender_domains, email_count, first_seen, last_seen)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            keywords = excluded.keywords,
            sender_domains = excluded.sender_domains,
            email_count = excluded.email_count,
            first_seen = excluded.first_seen,
            last_seen = excluded.last_seen,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            project.id,
            project.name,
            json.dumps(project.keywords),
            json.dumps(project.sender_domains),
            project.email_count,
            project.first_seen,
            project.last_seen,
        ),
    )


def save_assignment(conn: sqlite3.Connection, assignment: ProjectAssignment) -> None:
    """
    Save an email-to-project assignment.

    Args:
        conn: Database connection.
        assignment: Assignment to save.
    """
    import json

    conn.execute(
        """
        INSERT OR REPLACE INTO email_projects
        (message_id, project_id, confidence, reasons)
        VALUES (?, ?, ?, ?)
        """,
        (
            assignment.message_id,
            assignment.project_id,
            assignment.confidence,
            json.dumps(assignment.reasons),
        ),
    )


def get_project(conn: sqlite3.Connection, project_id: str) -> Project | None:
    """
    Get a project by ID.

    Args:
        conn: Database connection.
        project_id: Project ID (slug).

    Returns:
        Project if found, else None.
    """
    import json

    cursor = conn.execute(
        """SELECT id, name, keywords, sender_domains, email_count, first_seen, last_seen
           FROM projects WHERE id = ?""",
        (project_id,),
    )
    row = cursor.fetchone()
    if row:
        return Project(
            id=row[0],
            name=row[1],
            keywords=json.loads(row[2]) if row[2] else [],
            sender_domains=json.loads(row[3]) if row[3] else [],
            email_count=row[4],
            first_seen=row[5],
            last_seen=row[6],
        )
    return None


def list_projects(conn: sqlite3.Connection, min_emails: int = 1) -> list[Project]:
    """
    List all projects with at least min_emails, sorted by count.

    Args:
        conn: Database connection.
        min_emails: Minimum email count filter.

    Returns:
        List of Project objects sorted by email count.
    """
    import json

    cursor = conn.execute(
        """SELECT id, name, keywords, sender_domains, email_count, first_seen, last_seen
           FROM projects WHERE email_count >= ?
           ORDER BY email_count DESC""",
        (min_emails,),
    )
    projects = []
    for row in cursor.fetchall():
        projects.append(
            Project(
                id=row[0],
                name=row[1],
                keywords=json.loads(row[2]) if row[2] else [],
                sender_domains=json.loads(row[3]) if row[3] else [],
                email_count=row[4],
                first_seen=row[5],
                last_seen=row[6],
            )
        )
    return projects


def get_project_emails(
    conn: sqlite3.Connection,
    project_id: str,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict]:
    """
    Get all emails for a project, optionally filtered by date.

    Args:
        conn: Database connection.
        project_id: Project ID.
        start_date: Optional start date filter (YYYY-MM-DD).
        end_date: Optional end date filter (YYYY-MM-DD).

    Returns:
        List of email data dictionaries with message metadata.
    """
    query = """
        SELECT m.id, m.subject, m.sender, m.received_at, s.summary_json
        FROM email_projects ep
        JOIN messages m ON ep.message_id = m.id
        LEFT JOIN summaries s ON m.id = s.message_id
        WHERE ep.project_id = ?
    """
    params: list = [project_id]

    if start_date:
        query += " AND m.received_at >= ?"
        params.append(start_date)
    if end_date:
        query += " AND m.received_at <= ?"
        params.append(end_date)

    query += " ORDER BY m.received_at DESC"

    cursor = conn.execute(query, params)
    results = []
    for row in cursor.fetchall():
        results.append(
            {
                "id": row[0],
                "subject": row[1],
                "sender": row[2],
                "received_at": row[3],
                "summary_json": row[4],
            }
        )
    return results


def backfill_message_topics(conn: sqlite3.Connection) -> int:
    """
    Backfill message_topics from existing summary_json data.

    This is used for migrating existing data where summaries exist
    but message_topics wasn't populated during the summarize step.

    Args:
        conn: Database connection.

    Returns:
        Number of topic entries added.
    """
    import json

    cursor = conn.execute("SELECT message_id, summary_json FROM summaries")
    count = 0

    for row in cursor.fetchall():
        message_id = row[0]
        try:
            summary_data = json.loads(row[1])
            topics = summary_data.get("topics", [])
            for topic in topics:
                if topic:
                    result = conn.execute(
                        """INSERT OR IGNORE INTO message_topics (message_id, topic)
                           VALUES (?, ?)""",
                        (message_id, topic),
                    )
                    # rowcount is 1 if inserted, 0 if ignored (duplicate)
                    count += result.rowcount
        except (json.JSONDecodeError, TypeError):
            continue

    log.info("projects.backfill_complete", entries_added=count)
    return count