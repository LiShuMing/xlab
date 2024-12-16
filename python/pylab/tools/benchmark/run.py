import logging as log
import random
import time
from typing import List, Dict

import pymysql
from locust import User, task

import yaml


class StarRocksUser(User):
    abstract = True
    config = Dict

    def __init__(self, environment):
        super().__init__(environment)
        self.client: StarRocksClient = StarRocksClient(environment=environment, conn_infos=self.config['conn_infos'])

    def on_start(self):
        self.client.start()

    def on_stop(self):
        self.client.close()


class StarRocksClient:
    def __init__(self, *, environment, conn_infos):
        self.environment = environment

        info_index = random.randint(0, len(conn_infos) - 1)
        info = conn_infos[info_index]
        self.conn = pymysql.connect(host=info['host'], port=info['port'],
                                    user=info['user'], password=info['pwd'],
                                    db=info['db'])
        self.cur = None
        self.conn_id = 0

    def start(self):
        self.cur = self.conn.cursor()
        self.conn_id = self.conn.thread_id()

    def query(self, sql):
        start_time = time.time()
        try:
            self.cur.execute(sql)
            data = self.cur.fetchall()
            self.environment.events.request.fire(
                request_type="succeed",
                name="q",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=None,
                context={}
            )
            # log.info("conn[{}] query res [{}] cost {}".format(self.conn_id, data, time.time() - start_time))
            return data
        except Exception as e:
            self.environment.events.request.fire(
                request_type="failed",
                name="q",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e,
                context={}
            )
            # log.warning("query failed. sql : {}, err : {}".format(sql, e))
            raise e

    def close(self):
        if self.cur is not None:
            self.cur.close()


class TestStarRocksUser(StarRocksUser):
    def __init__(self, environment):
        with open('config/config.yaml', 'r', encoding='utf-8') as fin:
            self.config = yaml.safe_load(fin)

        super().__init__(environment)

        self.query_generator = self._get_query_generator(self.config['query_mode'])

    @staticmethod
    def _get_query_generator(query_mode):
        if query_mode == 'point':
            return TestStarRocksUser._gen_query_point
        elif query_mode == 'select_1':
            return TestStarRocksUser._gen_query_select_1
        else:
            return lambda: query_mode

    @staticmethod
    def _gen_query_point():
        pre = ['00006688', '000054521', '00002836', '00003751', '000048721']
        tail = ['fd366a', 'b98ae9', '6daf18', '9efe88', 'f23f8f']
        t = [1698329758631, 1697921330731, 1698476014618, 1698624916097, 1698782836759]
        tr = random.randint(0, 60000)
        pos = random.randint(0, 4)
        return "select * from ss_gather_plus where rowkey='{}_ss_prod_gather_{}_{}'".format(pre[pos], t[pos] + tr,
                                                                                            tail[pos])

    @staticmethod
    def _gen_query_select_1():
        return "select 1"

    @task
    def test_query(self):
        query = self.query_generator()
        self.client.query(query)