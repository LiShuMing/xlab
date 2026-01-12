#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import unittest
import os
from git_report_generator import GitCommitAnalyzer


class TestGitCommitAnalyzer(unittest.TestCase):
    def setUp(self):
        """Set up test fixtures"""
        self.repo_path = "/Users/lishuming/work/starrocks"
        self.analyzer = GitCommitAnalyzer(self.repo_path)

    def test_parse_commits(self):
        """Test commit parsing functionality"""
        # Sample commit data for testing
        sample_data = """COMMIT: abc123def456
Author: John Doe <john@example.com>
Date: Mon Aug 5 10:30:00 2025
Subject: feat: add new feature
Body: This commit adds a new feature to the system

---END---
COMMIT: def456ghi789
Author: Jane Smith <jane@example.com>
Date: Tue Aug 6 14:45:00 2025
Subject: fix: resolve memory leak issue
Body: Fixed memory leak in data processing module

---END---"""
        
        parsed = self.analyzer.parse_commits(sample_data)
        self.assertEqual(len(parsed), 2)
        self.assertEqual(parsed[0]['hash'], 'abc123def456')
        self.assertEqual(parsed[1]['subject'], 'fix: resolve memory leak issue')

    def test_empty_commits(self):
        """Test parsing empty commit data"""
        parsed = self.analyzer.parse_commits("")
        self.assertEqual(len(parsed), 0)


if __name__ == '__main__':
    unittest.main()