import unittest
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestFinanceToolkit(unittest.TestCase):
    
    def test_imports(self):
        """Test that all modules can be imported without errors"""
        try:
            from apps.stock_analyzer import stock_analyzer_app
            from apps.blog_analyzer import blog_analyzer_app
            from apps.starrocks_sql_generator import starrocks_sql_generator_app
            from apps.etf_analyzer import etf_analyzer_app
        except ImportError as e:
            self.fail(f"Import error: {e}")
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists"""
        self.assertTrue(os.path.exists("requirements.txt"), "requirements.txt file should exist")
    
    def test_main_app_exists(self):
        """Test that main app file exists"""
        self.assertTrue(os.path.exists("app.py"), "app.py file should exist")

if __name__ == '__main__':
    unittest.main()