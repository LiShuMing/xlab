#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import subprocess
import re
from datetime import datetime, timedelta
import dashscope
from dashscope import Generation
import configparser


class GitCommitAnalyzer:
    def __init__(self, repo_path, api_key=None):
        self.repo_path = repo_path
        self.api_key = api_key
        if api_key:
            dashscope.api_key = api_key

    def get_git_commits(self, since_days=7):
        """获取指定天数内的git提交记录"""
        os.chdir(self.repo_path)
        
        # 获取一周内的提交记录
        cmd = [
            'git', '--no-pager', 'log',
            f'--since="{since_days} days ago"',
            '--pretty=format:COMMIT: %H%nAuthor: %an <%ae>%nDate: %ad%nSubject: %s%nBody: %b%n---END---'
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            commits_data = result.stdout.strip()
            return commits_data
        except subprocess.CalledProcessError as e:
            print(f"Error executing git command: {e}")
            return ""

    def parse_commits(self, commits_data):
        """解析提交记录"""
        if not commits_data:
            return []
            
        commits = commits_data.split('---END---')
        parsed_commits = []
        
        for commit in commits:
            if commit.strip():
                commit_info = {}
                lines = commit.strip().split('\n')
                
                for line in lines:
                    if line.startswith('COMMIT: '):
                        commit_info['hash'] = line[8:].strip()
                    elif line.startswith('Author: '):
                        commit_info['author'] = line[8:].strip()
                    elif line.startswith('Date: '):
                        commit_info['date'] = line[6:].strip()
                    elif line.startswith('Subject: '):
                        commit_info['subject'] = line[9:].strip()
                    elif line.startswith('Body: '):
                        commit_info['body'] = line[6:].strip()
                        
                if commit_info:
                    parsed_commits.append(commit_info)
                    
        return parsed_commits

    def generate_report_with_qwen(self, commits_data, max_chars=200):
        """使用Qwen API生成中文周报"""
        if not self.api_key:
            return "API密钥未设置，无法生成报告"
            
        # 构建提示词
        prompt = f"""
你是一名技术文档工程师，需要根据提供的git提交历史生成一份中文周报。

任务：分析提供的过去一周的git提交记录，生成一份不超过{max_chars}个字符的综合性周报。

输入的Git提交信息包括：
- 提交哈希、作者、日期
- 提交消息（主题和正文）
- 详细的提交描述

报告要求：
1. 结构清晰（主要成果、Bug修复、技术指标等）
2. 重点关注架构变更、性能改进和重要重构
3. 覆盖最有影响力的提交，而不是每个小变更
4. 将相关提交归类到连贯的功能/改进主题中
5. 强调战略重要性和未来影响

分析指南：
- 同时阅读提交标题和正文以获取完整上下文
- 识别多个提交中的模式和主题
- 区分主要功能、重构、bug修复和优化
- 注意向后兼容性考虑和版本影响
- 识别架构决策及其影响

输出格式：适合工程团队的专业技术报告，重点突出重要功能和系统改进，而不是日常维护任务。

Git提交记录：
{commits_data}

请生成一份简洁但全面的中文技术周报：
"""
        
        try:
            response = Generation.call(
                model='qwen-plus',
                prompt=prompt,
                max_tokens=500,
                temperature=0.7
            )
            
            if response.status_code == 200:
                return response.output.text.strip()
            else:
                return f"API调用失败: {response}"
        except Exception as e:
            return f"生成报告时出错: {str(e)}"

    def run_analysis(self, since_days=7, max_chars=200):
        """运行完整的分析流程"""
        print("正在收集git提交记录...")
        commits_data = self.get_git_commits(since_days)
        
        if not commits_data:
            return "未找到提交记录"
            
        print("正在解析提交记录...")
        parsed_commits = self.parse_commits(commits_data)
        print(f"共找到 {len(parsed_commits)} 条提交记录")
        
        print("正在生成周报...")
        report = self.generate_report_with_qwen(commits_data, max_chars)
        
        return report


def main():
    # 从环境变量或配置文件获取API密钥
    api_key = os.environ.get('DASHSCOPE_API_KEY')
    
    # 如果没有设置环境变量，尝试从配置文件读取
    if not api_key:
        config = configparser.ConfigParser()
        config_file = os.path.join(os.path.dirname(__file__), 'config.ini')
        if os.path.exists(config_file):
            config.read(config_file)
            api_key = config.get('qwen', 'api_key', fallback=None)
    
    # 初始化分析器
    repo_path = "/Users/lishuming/work/starrocks"  # 默认仓库路径
    analyzer = GitCommitAnalyzer(repo_path, api_key)
    
    # 生成周报
    report = analyzer.run_analysis(since_days=7, max_chars=200)
    print("\n=== 周报生成结果 ===")
    print(report)


if __name__ == "__main__":
    main()