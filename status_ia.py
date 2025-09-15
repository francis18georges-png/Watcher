#!/usr/bin/env python3
"""
Status du projet IA Watcher - Quick diagnostic script
Usage: python status_ia.py
"""
import sys
from pathlib import Path
import traceback

def check_component(name: str, test_func):
    """Test a component and report status."""
    try:
        test_func()
        print(f"✅ {name}")
        return True
    except Exception as e:
        print(f"❌ {name}: {e}")
        return False

def test_imports():
    """Test core imports."""
    from app.core.engine import Engine
    from app.core.memory import Memory
    from app.llm.client import Client
    from app.tools.embeddings import embed_ollama

def test_config():
    """Test configuration loading."""
    from config import load_config
    cfg = load_config()
    assert "llm" in cfg
    assert "memory" in cfg

def test_engine():
    """Test engine initialization."""
    from app.core.engine import Engine
    e = Engine()
    assert e.start_msg is not None

def test_chat():
    """Test basic chat functionality."""
    from app.core.engine import Engine
    e = Engine()
    response = e.chat("Test")
    assert len(response) > 0

def main():
    print("🤖 Status du dossier IA Watcher")
    print("=" * 40)
    
    # Component tests
    components = [
        ("Imports du core système", test_imports),
        ("Configuration TOML", test_config),
        ("Initialisation Engine", test_engine),
        ("Fonctions de chat", test_chat),
    ]
    
    results = []
    for name, test_func in components:
        results.append(check_component(name, test_func))
    
    print("\n" + "=" * 40)
    success_rate = sum(results) / len(results) * 100
    print(f"📊 Taux de réussite: {success_rate:.1f}%")
    
    if success_rate >= 75:
        print("🎉 Le dossier IA est opérationnel!")
        print("🔧 Pour activer Ollama: docker run -d -p 11434:11434 ollama/ollama")
    else:
        print("⚠️  Des corrections sont nécessaires")
        
    print("\n📝 Notes:")
    print("- Les warnings Ollama sont normaux si le serveur n'est pas démarré")
    print("- Le système fonctionne en mode fallback sans Ollama")
    print("- Voir README.md pour les instructions complètes")

if __name__ == "__main__":
    main()