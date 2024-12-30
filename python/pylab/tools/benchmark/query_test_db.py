import pymysql
from locust import User, task, between

class QueryDatabaseUser(User):
    wait_time = between(1, 2)  # 等待时间
    
    def on_start(self):
        self.conn = pymysql.connect(
            host="172.26.92.227",
            port=9131,
            user="root",
            password="",
            database="test",
            cursorclass=pymysql.cursors.DictCursor
        )
        self.cursor = self.conn.cursor()
    
    @task
    def query_task(self):
        # query = "SELECT 1"
        query = "SELECT * FROM mv_iceberg_56df583fbae748a991253d5d4b93828d.sql_test_db.lineitem_days;"
        self.cursor.execute(query)
        result = self.cursor.fetchall()
        print(f"Retrieved {len(result)} rows")

    def on_stop(self):
        self.cursor.close()
        self.conn.close()