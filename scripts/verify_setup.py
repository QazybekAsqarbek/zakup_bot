#!/usr/bin/env python
"""
Verification script to check if all components are properly set up.
Run this before starting the bot to catch configuration issues early.
"""

import sys
import os

def check_python_version():
    """Check if Python version is 3.10+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Python version {version.major}.{version.minor} is too old. Need 3.10+")
        return False
    print(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
    return True

def check_env_file():
    """Check if .env file exists"""
    if not os.path.exists('.env'):
        print("❌ .env file not found!")
        print("   Create .env file with:")
        print("   TELEGRAM_TOKEN=your_token")
        print("   ANTHROPIC_API_KEY=your_key")
        print("   DEEPSEEK_API_KEY=your_key")
        return False
    print("✅ .env file exists")
    return True

def check_imports():
    """Check if all required modules can be imported"""
    try:
        from dotenv import load_dotenv
        print("✅ python-dotenv")
    except ImportError:
        print("❌ python-dotenv not installed")
        return False
    
    try:
        from telegram import Update
        print("✅ python-telegram-bot")
    except ImportError:
        print("❌ python-telegram-bot not installed")
        return False
    
    try:
        import anthropic
        print("✅ anthropic")
    except ImportError:
        print("❌ anthropic not installed")
        return False
    
    try:
        from openai import OpenAI
        print("✅ openai")
    except ImportError:
        print("❌ openai not installed")
        return False
    
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        print("✅ motor (MongoDB)")
    except ImportError:
        print("❌ motor not installed")
        return False
    
    try:
        import pandas
        print("✅ pandas")
    except ImportError:
        print("❌ pandas not installed")
        return False
    
    return True

def check_config():
    """Check if configuration is valid"""
    try:
        from src.config import (
            TELEGRAM_TOKEN,
            ANTHROPIC_API_KEY,
            DEEPSEEK_API_KEY,
            MONGO_URL
        )
        
        if not TELEGRAM_TOKEN:
            print("❌ TELEGRAM_TOKEN not set in .env")
            return False
        print(f"✅ TELEGRAM_TOKEN: {TELEGRAM_TOKEN[:10]}...")
        
        if not ANTHROPIC_API_KEY:
            print("⚠️  ANTHROPIC_API_KEY not set (needed for PDF/images)")
        else:
            print(f"✅ ANTHROPIC_API_KEY: {ANTHROPIC_API_KEY[:10]}...")
        
        if not DEEPSEEK_API_KEY:
            print("❌ DEEPSEEK_API_KEY not set")
            return False
        print(f"✅ DEEPSEEK_API_KEY: {DEEPSEEK_API_KEY[:10]}...")
        
        print(f"✅ MONGO_URL: {MONGO_URL}")
        
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def check_modules():
    """Check if custom modules can be imported"""
    try:
        from src.database import db
        print("✅ src.database")
    except Exception as e:
        print(f"❌ src.database: {e}")
        return False
    
    try:
        from src.category_intelligence import category_intelligence
        print("✅ src.category_intelligence")
    except Exception as e:
        print(f"❌ src.category_intelligence: {e}")
        return False
    
    try:
        from src.unit_normalizer import unit_normalizer
        print("✅ src.unit_normalizer")
    except Exception as e:
        print(f"❌ src.unit_normalizer: {e}")
        return False
    
    try:
        from src.clarifier import auto_clarifier
        print("✅ src.clarifier")
    except Exception as e:
        print(f"❌ src.clarifier: {e}")
        return False
    
    try:
        from src.comparator import quote_comparator
        print("✅ src.comparator")
    except Exception as e:
        print(f"❌ src.comparator: {e}")
        return False
    
    return True

def check_mongodb():
    """Check if MongoDB is accessible"""
    try:
        from motor.motor_asyncio import AsyncIOMotorClient
        from src.config import MONGO_URL
        import asyncio
        
        async def test_connection():
            client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
            try:
                await client.admin.command('ping')
                return True
            except Exception as e:
                print(f"❌ MongoDB not accessible: {e}")
                return False
            finally:
                client.close()
        
        result = asyncio.run(test_connection())
        if result:
            print("✅ MongoDB connection successful")
        return result
    except Exception as e:
        print(f"❌ MongoDB check failed: {e}")
        return False

def main():
    """Run all checks"""
    print("="*60)
    print("🔍 ZAKUP BOT - SETUP VERIFICATION")
    print("="*60)
    print()
    
    all_passed = True
    
    print("📋 Checking Python version...")
    if not check_python_version():
        all_passed = False
    print()
    
    print("📋 Checking .env file...")
    if not check_env_file():
        all_passed = False
    print()
    
    print("📋 Checking dependencies...")
    if not check_imports():
        all_passed = False
        print("\n💡 Install dependencies: pip install -r requirements.txt")
    print()
    
    print("📋 Checking configuration...")
    if not check_config():
        all_passed = False
    print()
    
    print("📋 Checking custom modules...")
    if not check_modules():
        all_passed = False
    print()
    
    print("📋 Checking MongoDB connection...")
    if not check_mongodb():
        all_passed = False
        print("\n💡 Start MongoDB: docker-compose up -d")
    print()
    
    print("="*60)
    if all_passed:
        print("🎉 ALL CHECKS PASSED!")
        print("✅ Your bot is ready to run: python src/main.py")
    else:
        print("❌ SOME CHECKS FAILED")
        print("⚠️  Fix the issues above before running the bot")
        sys.exit(1)
    print("="*60)

if __name__ == "__main__":
    main()
