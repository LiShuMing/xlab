import unittest
import os
import sys

# Add the project root to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


class TestAILabPlatform(unittest.TestCase):
    """Test suite for AI Lab Platform modules."""
    
    def test_all_modules_import(self):
        """Test that all new modules can be imported without errors"""
        try:
            # Core modules
            from modules.sandbox import SandboxModule
            from modules.stock_analyzer import StockAnalyzerModule
            from modules.blog_analyzer import BlogAnalyzerModule
            from modules.starrocks_sql import StarRocksSQLModule
            from modules.etf_analyzer import ETFAnalyzerModule
            
            # Core infrastructure
            from core.llm_factory import get_llm, get_available_providers
            from core.memory_manager import SessionMemoryManager
            from config.settings import settings
            
        except ImportError as e:
            self.fail(f"Import error: {e}")
    
    def test_module_registration(self):
        """Test that all modules are properly registered"""
        from modules.base_module import ModuleRegistry
        from modules.sandbox import SandboxModule
        from modules.stock_analyzer import StockAnalyzerModule
        from modules.blog_analyzer import BlogAnalyzerModule
        from modules.starrocks_sql import StarRocksSQLModule
        from modules.etf_analyzer import ETFAnalyzerModule
        
        modules = ModuleRegistry.get_modules()
        
        # Check that all expected modules are registered
        expected_modules = [
            "Sandbox",
            "Stock Analyzer",
            "Blog Analyzer",
            "StarRocks SQL",
            "ETF Momentum"
        ]
        
        for module_name in expected_modules:
            self.assertIn(module_name, modules, f"Module '{module_name}' should be registered")
    
    def test_requirements_file_exists(self):
        """Test that requirements.txt exists"""
        self.assertTrue(os.path.exists("requirements.txt"), "requirements.txt file should exist")
    
    def test_main_app_exists(self):
        """Test that main app file exists"""
        self.assertTrue(os.path.exists("app.py"), "app.py file should exist")
    
    def test_config_files_exist(self):
        """Test that configuration files exist"""
        self.assertTrue(os.path.exists("config/settings.py"), "config/settings.py should exist")
        self.assertTrue(os.path.exists("core/llm_factory.py"), "core/llm_factory.py should exist")


if __name__ == '__main__':
    unittest.main()
