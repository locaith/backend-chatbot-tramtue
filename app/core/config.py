"""
Configuration management với Pydantic Settings
"""
import os
import json
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from pydantic import Field
from pydantic_settings import BaseSettings
import structlog

logger = structlog.get_logger()

class Settings(BaseSettings):
    """Main application settings"""
    
    # API Keys
    gemini_api_key: str = Field(..., env="GEMINI_API_KEY")
    serper_api_key: str = Field(..., env="SERPER_API_KEY")
    
    # Supabase
    supabase_url: str = Field(..., env="SUPABASE_URL")
    supabase_service_role_key: str = Field(..., env="SUPABASE_SERVICE_ROLE_KEY")
    
    # Models
    model_flash: str = Field("gemini-2.5-flash", env="MODEL_FLASH")
    model_pro: str = Field("gemini-2.5-pro", env="MODEL_PRO")
    
    # File paths
    policy_file: str = Field("config/policy.tramtue.yml", env="POLICY_FILE")
    system_prompt_file: str = Field("prompts/system_tramtue.txt", env="SYSTEM_PROMPT_FILE")
    discovery_prompt_file: str = Field("prompts/agents/discovery.txt", env="DISCOVERY_PROMPT_FILE")
    cskh_prompt_file: str = Field("prompts/agents/cskh.txt", env="CSKH_PROMPT_FILE")
    sales_prompt_file: str = Field("prompts/agents/sales.txt", env="SALES_PROMPT_FILE")
    handoff_prompt_file: str = Field("prompts/agents/handoff.txt", env="HANDOFF_PROMPT_FILE")
    followup_prompt_file: str = Field("prompts/agents/followup.txt", env="FOLLOWUP_PROMPT_FILE")
    rag_config_file: str = Field("config/rag.ingest.config.json", env="RAG_CONFIG_FILE")
    
    # CORS
    cors_allowed_origins: str = Field("*", env="CORS_ALLOWED_ORIGINS")
    
    # Rate limiting
    rate_limit_requests: int = Field(100, env="RATE_LIMIT_REQUESTS")
    rate_limit_window: int = Field(60, env="RATE_LIMIT_WINDOW")
    
    # Admin
    admin_token: str = Field("admin-secret-token", env="ADMIN_TOKEN")
    
    # Server
    host: str = Field("0.0.0.0", env="HOST")
    port: int = Field(8000, env="PORT")
    workers: int = Field(1, env="WORKERS")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
        protected_namespaces = ('settings_',)
        extra = "ignore"  # Ignore extra fields to avoid validation errors

class ConfigManager:
    """Quản lý cấu hình và hot-reload"""
    
    def __init__(self):
        self.settings = Settings()
        self._policy_cache: Optional[Dict[str, Any]] = None
        self._prompts_cache: Dict[str, str] = {}
        self._rag_config_cache: Optional[Dict[str, Any]] = None
        self._file_mtimes: Dict[str, float] = {}
        
    def get_settings(self) -> Settings:
        """Lấy settings hiện tại"""
        return self.settings
        
    def load_policy(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load policy từ YAML file với caching"""
        policy_path = Path(self.settings.policy_file)
        
        if not policy_path.exists():
            raise FileNotFoundError(f"Policy file not found: {policy_path}")
            
        current_mtime = policy_path.stat().st_mtime
        
        if (force_reload or 
            self._policy_cache is None or 
            self._file_mtimes.get("policy", 0) < current_mtime):
            
            try:
                with open(policy_path, 'r', encoding='utf-8') as f:
                    self._policy_cache = yaml.safe_load(f)
                self._file_mtimes["policy"] = current_mtime
                logger.info("Policy loaded successfully", file=str(policy_path))
            except Exception as e:
                logger.error("Failed to load policy", error=str(e), file=str(policy_path))
                raise
                
        return self._policy_cache
        
    def load_prompt(self, prompt_type: str, force_reload: bool = False) -> str:
        """Load prompt từ file với caching"""
        prompt_files = {
            "system": self.settings.system_prompt_file,
            "discovery": self.settings.discovery_prompt_file,
            "cskh": self.settings.cskh_prompt_file,
            "sales": self.settings.sales_prompt_file,
            "handoff": self.settings.handoff_prompt_file,
            "followup": self.settings.followup_prompt_file
        }
        
        if prompt_type not in prompt_files:
            raise ValueError(f"Unknown prompt type: {prompt_type}")
            
        prompt_path = Path(prompt_files[prompt_type])
        
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
            
        current_mtime = prompt_path.stat().st_mtime
        cache_key = f"prompt_{prompt_type}"
        
        if (force_reload or 
            cache_key not in self._prompts_cache or 
            self._file_mtimes.get(cache_key, 0) < current_mtime):
            
            try:
                with open(prompt_path, 'r', encoding='utf-8') as f:
                    self._prompts_cache[cache_key] = f.read()
                self._file_mtimes[cache_key] = current_mtime
                logger.info("Prompt loaded successfully", 
                           type=prompt_type, file=str(prompt_path))
            except Exception as e:
                logger.error("Failed to load prompt", 
                           error=str(e), type=prompt_type, file=str(prompt_path))
                raise
                
        return self._prompts_cache[cache_key]
        
    def load_rag_config(self, force_reload: bool = False) -> Dict[str, Any]:
        """Load RAG config từ JSON file với caching"""
        rag_path = Path(self.settings.rag_config_file)
        
        if not rag_path.exists():
            raise FileNotFoundError(f"RAG config file not found: {rag_path}")
            
        current_mtime = rag_path.stat().st_mtime
        
        if (force_reload or 
            self._rag_config_cache is None or 
            self._file_mtimes.get("rag_config", 0) < current_mtime):
            
            try:
                with open(rag_path, 'r', encoding='utf-8') as f:
                    self._rag_config_cache = json.load(f)
                self._file_mtimes["rag_config"] = current_mtime
                logger.info("RAG config loaded successfully", file=str(rag_path))
            except Exception as e:
                logger.error("Failed to load RAG config", 
                           error=str(e), file=str(rag_path))
                raise
                
        return self._rag_config_cache
        
    def reload_all(self) -> Dict[str, bool]:
        """Reload tất cả config và prompts"""
        results = {}
        
        try:
            self.load_policy(force_reload=True)
            results["policy"] = True
        except Exception as e:
            logger.error("Failed to reload policy", error=str(e))
            results["policy"] = False
            
        for prompt_type in ["system", "discovery", "cskh", "sales", "handoff", "followup"]:
            try:
                self.load_prompt(prompt_type, force_reload=True)
                results[f"prompt_{prompt_type}"] = True
            except Exception as e:
                logger.error("Failed to reload prompt", 
                           type=prompt_type, error=str(e))
                results[f"prompt_{prompt_type}"] = False
                
        try:
            self.load_rag_config(force_reload=True)
            results["rag_config"] = True
        except Exception as e:
            logger.error("Failed to reload RAG config", error=str(e))
            results["rag_config"] = False
            
        return results
        
    def validate_startup(self) -> bool:
        """Validate tất cả config files khi khởi động"""
        try:
            # Load và validate tất cả files
            self.load_policy()
            self.load_rag_config()
            
            for prompt_type in ["system", "discovery", "cskh", "sales", "handoff", "followup"]:
                self.load_prompt(prompt_type)
                
            logger.info("All configuration files validated successfully")
            return True
            
        except Exception as e:
            logger.error("Configuration validation failed", error=str(e))
            return False

# Global config manager instance
config_manager = ConfigManager()

def get_config() -> ConfigManager:
    """Get global config manager instance"""
    return config_manager

def get_settings() -> Settings:
    """Get application settings"""
    return config_manager.get_settings()