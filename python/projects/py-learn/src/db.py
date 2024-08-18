"""
数据库模块 - SQLite 封装

提供每日精进 Agent 所需的数据持久化功能。
遵循强类型设计原则。
"""

import sqlite3
import json
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from contextlib import contextmanager


@dataclass
class Domain:
    """领域定义"""
    id: str
    label: str
    rotation_day: int


@dataclass
class Topic:
    """主题定义"""
    id: str
    domain_id: str
    name: str
    level_default: int
    tags: List[str]
    subtopics: List[str]
    key_points: List[str]
    references: List[str]


@dataclass
class Question:
    """题目记录"""
    id: int
    date: str
    topic_id: str
    level: int
    qtype: str
    question_json: Dict[str, Any]
    status: str


@dataclass
class Answer:
    """作答记录"""
    id: int
    question_id: int
    answer_text: str
    concept_score: float
    depth_score: float
    boundary_score: float
    total_score: float
    gaps_json: List[str]
    summary: str
    created_at: str


@dataclass
class TopicStats:
    """主题统计"""
    topic_id: str
    attempt_count: int
    avg_score: float
    last_attempt: Optional[str]
    current_level: int
    is_weak: bool
    last_score: float


class Database:
    """
    SQLite 数据库封装类

    提供每日精进 Agent 的所有数据操作接口。
    使用强类型设计，所有方法都有明确的输入输出类型。
    """

    def __init__(self, db_path: str) -> None:
        """
        初始化数据库连接

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    @contextmanager
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接的上下文管理器"""
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _init_db(self) -> None:
        """初始化数据库表结构"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 领域表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS domains (
                    id TEXT PRIMARY KEY,
                    label TEXT NOT NULL,
                    rotation_day INTEGER NOT NULL
                )
            """)

            # 主题表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topics (
                    id TEXT PRIMARY KEY,
                    domain_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    level_default INTEGER DEFAULT 3,
                    tags TEXT,  -- JSON array
                    subtopics TEXT,  -- JSON array
                    key_points TEXT,  -- JSON array
                    "references" TEXT,  -- JSON array
                    FOREIGN KEY (domain_id) REFERENCES domains(id)
                )
            """)

            # 题目表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS questions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    topic_id TEXT NOT NULL,
                    level INTEGER NOT NULL,
                    qtype TEXT NOT NULL,
                    question_json TEXT NOT NULL,  -- JSON
                    status TEXT DEFAULT 'pending',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                )
            """)

            # 答案表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question_id INTEGER NOT NULL,
                    answer_text TEXT,
                    concept_score REAL DEFAULT 0,
                    depth_score REAL DEFAULT 0,
                    boundary_score REAL DEFAULT 0,
                    total_score REAL DEFAULT 0,
                    gaps_json TEXT,  -- JSON array
                    summary TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (question_id) REFERENCES questions(id)
                )
            """)

            # 主题统计表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS topic_stats (
                    topic_id TEXT PRIMARY KEY,
                    attempt_count INTEGER DEFAULT 0,
                    avg_score REAL DEFAULT 0,
                    last_attempt TEXT,
                    current_level INTEGER DEFAULT 3,
                    is_weak INTEGER DEFAULT 0,  -- bool
                    last_score REAL DEFAULT 0,
                    FOREIGN KEY (topic_id) REFERENCES topics(id)
                )
            """)

            # 热点表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS hot_topics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    domain_id TEXT,
                    title TEXT NOT NULL,
                    summary TEXT,
                    source_url TEXT,
                    fetched_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    used INTEGER DEFAULT 0
                )
            """)

            # 创建索引
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_date ON questions(date)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_questions_topic ON questions(topic_id)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_answers_question ON answers(question_id)
            """)

    # ==================== Domain 操作 ====================

    def init_domains(self, domains: List[Domain]) -> None:
        """
        批量初始化领域数据

        Args:
            domains: 领域列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for domain in domains:
                cursor.execute(
                    "INSERT OR REPLACE INTO domains (id, label, rotation_day) VALUES (?, ?, ?)",
                    (domain.id, domain.label, domain.rotation_day)
                )

    def get_all_domains(self) -> List[Domain]:
        """获取所有领域"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM domains ORDER BY rotation_day")
            rows = cursor.fetchall()
            return [Domain(
                id=row['id'],
                label=row['label'],
                rotation_day=row['rotation_day']
            ) for row in rows]

    def get_domain_by_day(self, day: int) -> Optional[Domain]:
        """
        根据星期几获取领域

        Args:
            day: 0=周日, 1=周一, ..., 6=周六
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM domains WHERE rotation_day = ?",
                (day,)
            )
            row = cursor.fetchone()
            if row:
                return Domain(
                    id=row['id'],
                    label=row['label'],
                    rotation_day=row['rotation_day']
                )
            return None

    # ==================== Topic 操作 ====================

    def init_topics(self, topics: List[Topic]) -> None:
        """
        批量初始化主题数据

        Args:
            topics: 主题列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            for topic in topics:
                cursor.execute(
                    """INSERT OR REPLACE INTO topics
                       (id, domain_id, name, level_default, tags, subtopics, key_points, "references")
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        topic.id,
                        topic.domain_id,
                        topic.name,
                        topic.level_default,
                        json.dumps(topic.tags),
                        json.dumps(topic.subtopics),
                        json.dumps(topic.key_points),
                        json.dumps(topic.references)
                    )
                )
                # 同时初始化 topic_stats
                cursor.execute(
                    """INSERT OR IGNORE INTO topic_stats
                       (topic_id, current_level) VALUES (?, ?)""",
                    (topic.id, topic.level_default)
                )

    def get_all_topics(self) -> List[Topic]:
        """获取所有主题"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM topics")
            rows = cursor.fetchall()
            return [self._row_to_topic(row) for row in rows]

    def get_topics_by_domain(self, domain_id: str) -> List[Topic]:
        """根据领域获取主题"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM topics WHERE domain_id = ?",
                (domain_id,)
            )
            rows = cursor.fetchall()
            return [self._row_to_topic(row) for row in rows]

    def get_topic_by_id(self, topic_id: str) -> Optional[Topic]:
        """根据 ID 获取主题"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM topics WHERE id = ?",
                (topic_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_topic(row)
            return None

    def _row_to_topic(self, row: sqlite3.Row) -> Topic:
        """将数据库行转换为 Topic 对象"""
        return Topic(
            id=row['id'],
            domain_id=row['domain_id'],
            name=row['name'],
            level_default=row['level_default'],
            tags=json.loads(row['tags']) if row['tags'] else [],
            subtopics=json.loads(row['subtopics']) if row['subtopics'] else [],
            key_points=json.loads(row['key_points']) if row['key_points'] else [],
            references=json.loads(row[7]) if row[7] else []
        )

    # ==================== Question 操作 ====================

    def create_question(self, topic_id: str, level: int, qtype: str,
                        question_data: Dict[str, Any]) -> int:
        """
        创建新题目

        Args:
            topic_id: 主题 ID
            level: 难度等级
            qtype: 题型
            question_data: 题目内容（字典）

        Returns:
            新创建题目的 ID
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO questions
                   (date, topic_id, level, qtype, question_json, status)
                   VALUES (?, ?, ?, ?, ?, 'pending')""",
                (date_str, topic_id, level, qtype, json.dumps(question_data))
            )
            return cursor.lastrowid

    def get_question_by_id(self, question_id: int) -> Optional[Question]:
        """根据 ID 获取题目"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM questions WHERE id = ?",
                (question_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_question(row)
            return None

    def get_today_question(self) -> Optional[Question]:
        """获取今日题目"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM questions WHERE date = ? ORDER BY id DESC LIMIT 1",
                (date_str,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_question(row)
            return None

    def update_question_status(self, question_id: int, status: str) -> None:
        """更新题目状态"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE questions SET status = ? WHERE id = ?",
                (status, question_id)
            )

    def get_recent_questions(self, limit: int = 10) -> List[Question]:
        """获取最近题目"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM questions ORDER BY date DESC, id DESC LIMIT ?",
                (limit,)
            )
            rows = cursor.fetchall()
            return [self._row_to_question(row) for row in rows]

    def _row_to_question(self, row: sqlite3.Row) -> Question:
        """将数据库行转换为 Question 对象"""
        return Question(
            id=row['id'],
            date=row['date'],
            topic_id=row['topic_id'],
            level=row['level'],
            qtype=row['qtype'],
            question_json=json.loads(row['question_json']),
            status=row['status']
        )

    # ==================== Answer 操作 ====================

    def save_answer(self, question_id: int, answer_text: str,
                    scores: Dict[str, float], gaps: List[str],
                    summary: str) -> int:
        """
        保存作答和评分

        Args:
            question_id: 题目 ID
            answer_text: 答案文本
            scores: 包含 concept_score, depth_score, boundary_score, total_score
            gaps: 遗漏的关键点列表
            summary: 标准答案摘要

        Returns:
            新创建答案的 ID
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """INSERT INTO answers
                   (question_id, answer_text, concept_score, depth_score,
                    boundary_score, total_score, gaps_json, summary)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    question_id,
                    answer_text,
                    scores.get('concept_score', 0),
                    scores.get('depth_score', 0),
                    scores.get('boundary_score', 0),
                    scores.get('total_score', 0),
                    json.dumps(gaps),
                    summary
                )
            )
            return cursor.lastrowid

    def get_answer_by_question(self, question_id: int) -> Optional[Answer]:
        """根据题目获取答案"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM answers WHERE question_id = ?",
                (question_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_answer(row)
            return None

    def _row_to_answer(self, row: sqlite3.Row) -> Answer:
        """将数据库行转换为 Answer 对象"""
        return Answer(
            id=row['id'],
            question_id=row['question_id'],
            answer_text=row['answer_text'],
            concept_score=row['concept_score'],
            depth_score=row['depth_score'],
            boundary_score=row['boundary_score'],
            total_score=row['total_score'],
            gaps_json=json.loads(row['gaps_json']) if row['gaps_json'] else [],
            summary=row['summary'] if row['summary'] else "",
            created_at=row['created_at']
        )

    # ==================== TopicStats 操作 ====================

    def get_topic_stats(self, topic_id: str) -> Optional[TopicStats]:
        """获取主题统计"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM topic_stats WHERE topic_id = ?",
                (topic_id,)
            )
            row = cursor.fetchone()
            if row:
                return self._row_to_topic_stats(row)
            return None

    def update_topic_stats(self, topic_id: str, new_score: float,
                           new_level: Optional[int] = None,
                           is_weak: Optional[bool] = None) -> None:
        """
        更新主题统计

        Args:
            topic_id: 主题 ID
            new_score: 新得分
            new_level: 新等级（可选）
            is_weak: 是否薄弱（可选）
        """
        date_str = datetime.now().strftime("%Y-%m-%d")
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 获取当前统计
            stats = self.get_topic_stats(topic_id)
            if not stats:
                # 创建新记录
                cursor.execute(
                    """INSERT INTO topic_stats
                       (topic_id, attempt_count, avg_score, last_attempt,
                        current_level, is_weak, last_score)
                       VALUES (?, 1, ?, ?, 3, 0, ?)""",
                    (topic_id, new_score, date_str, new_score)
                )
                return

            # 计算新平均值
            new_count = stats.attempt_count + 1
            new_avg = (stats.avg_score * stats.attempt_count + new_score) / new_count

            # 构建更新语句
            updates = [
                "attempt_count = ?",
                "avg_score = ?",
                "last_attempt = ?",
                "last_score = ?"
            ]
            params = [new_count, new_avg, date_str, new_score]

            if new_level is not None:
                updates.append("current_level = ?")
                params.append(new_level)
            if is_weak is not None:
                updates.append("is_weak = ?")
                params.append(1 if is_weak else 0)

            params.append(topic_id)

            cursor.execute(
                f"UPDATE topic_stats SET {', '.join(updates)} WHERE topic_id = ?",
                params
            )

    def get_weak_topics(self) -> List[Tuple[str, TopicStats]]:
        """获取所有薄弱主题"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT t.*, ts.* FROM topics t
                JOIN topic_stats ts ON t.id = ts.topic_id
                WHERE ts.is_weak = 1
            """)
            results = []
            for row in cursor.fetchall():
                topic = self._row_to_topic(row)
                stats = self._row_to_topic_stats(row)
                results.append((topic.id, stats))
            return results

    def _row_to_topic_stats(self, row: sqlite3.Row) -> TopicStats:
        """将数据库行转换为 TopicStats 对象"""
        return TopicStats(
            topic_id=row['topic_id'],
            attempt_count=row['attempt_count'],
            avg_score=row['avg_score'],
            last_attempt=row['last_attempt'],
            current_level=row['current_level'],
            is_weak=bool(row['is_weak']),
            last_score=row['last_score']
        )

    # ==================== 综合查询 ====================

    def get_weekly_summary(self) -> Dict[str, Any]:
        """获取本周学习摘要"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 本周题目数
            cursor.execute("""
                SELECT COUNT(*) FROM questions
                WHERE date >= date('now', 'weekday 0', '-7 days')
            """)
            total_questions = cursor.fetchone()[0]

            # 已完成数
            cursor.execute("""
                SELECT COUNT(*) FROM questions
                WHERE date >= date('now', 'weekday 0', '-7 days')
                AND status = 'answered'
            """)
            answered = cursor.fetchone()[0]

            # 平均分
            cursor.execute("""
                SELECT AVG(total_score) FROM answers a
                JOIN questions q ON a.question_id = q.id
                WHERE q.date >= date('now', 'weekday 0', '-7 days')
            """)
            avg_score = cursor.fetchone()[0] or 0

            return {
                'total_questions': total_questions,
                'answered': answered,
                'completion_rate': answered / total_questions if total_questions > 0 else 0,
                'avg_score': round(avg_score, 2)
            }
