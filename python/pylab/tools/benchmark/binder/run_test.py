import os
import subprocess
import sys

# MySQL 连接信息
HOST="172.26.81.63"
PORT="9030"
USER="root"
SCHEMA="db2"

def run_command(command, cwd=None):
    """
    Helper function to run a shell command and return its output.
    """
    try:
        print("Running command:", " ".join(command))
        result = subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running command: {e.stderr.strip()}")
    

def run_mysqlslap(concurrency: int = 1, query: str = "select 1", iterations: int = 3, number_of_queries: int = 30):
    """
    Run mysqlslap with the given parameters.
    """
    command = [
        "mysqlslap",
        f"--host={HOST}",
        f"--port={PORT}",
        f"--user={USER}",
        f"--concurrency={concurrency}",
        f"--iterations={iterations}",
        f"--number-of-queries={number_of_queries}",
        f"--create-schema={SCHEMA}",
        f"--query={query}",
    ]
    return run_command(command)

def run_mysql(sql: str):
    """
    Run a SQL query on MySQL.
    """
    command = [
        "mysql",
        f"-h{HOST}",
        f"-P{PORT}",
        f"-u{USER}",
        SCHEMA,
        "-e",
        sql,
    ]
    return run_command(command)

if __name__ == "__main__":
    with open("ddl.sql") as f:
        sqls = f.readlines()
        arr = "\n".join(sqls).split(";")
        for sql in arr:
            run_mysql(sql)