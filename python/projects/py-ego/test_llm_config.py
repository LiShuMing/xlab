#!/usr/bin/env python3
"""
测试 LLM 配置是否正确加载和工作
"""
import sys
from config import (
    LLM_BASE_URL, LLM_API_KEY, LLM_MODEL, LLM_TIMEOUT, 
    LOG_LEVEL, get_openai_client
)

def test_config():
    """测试配置加载"""
    print("=" * 50)
    print("📋 LLM 配置信息")
    print("=" * 50)
    print(f"Base URL: {LLM_BASE_URL}")
    print(f"Model: {LLM_MODEL}")
    print(f"Timeout: {LLM_TIMEOUT}s")
    print(f"Log Level: {LOG_LEVEL}")
    print(f"API Key: {'✅ 已设置' if LLM_API_KEY else '❌ 未设置'}")
    
    if not LLM_API_KEY:
        print("\n⚠️ 警告: API Key 未设置，请在 ~/.env 中配置 LLM_API_KEY")
        return False
    return True

def test_client():
    """测试 OpenAI 客户端初始化"""
    print("\n" + "=" * 50)
    print("🔧 测试 OpenAI 客户端")
    print("=" * 50)
    try:
        client = get_openai_client()
        print(f"✅ 客户端初始化成功")
        print(f"   Base URL: {client.base_url}")
        print(f"   Timeout: {client.timeout}")
        return True
    except Exception as e:
        print(f"❌ 客户端初始化失败: {e}")
        return False

def test_llm_api():
    """测试实际的 LLM API 调用"""
    print("\n" + "=" * 50)
    print("🤖 测试 LLM API 调用")
    print("=" * 50)
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个简洁的助手"},
                {"role": "user", "content": "你好，请回复'测试成功'"}
            ],
            max_tokens=50,
            temperature=0.7
        )
        reply = response.choices[0].message.content
        print(f"✅ API 调用成功")
        print(f"📝 回复: {reply}")
        return True
    except Exception as e:
        print(f"❌ API 调用失败: {e}")
        return False

def test_embedding():
    """测试 Embedding 功能"""
    print("\n" + "=" * 50)
    print("🔤 测试 Embedding 功能")
    print("=" * 50)
    try:
        from embeddings import get_embedding
        print("正在获取 embedding（首次加载模型可能需要一些时间）...")
        embedding = get_embedding("这是一个测试句子")
        if embedding is not None:
            print(f"✅ Embedding 获取成功")
            print(f"   维度: {len(embedding)}")
            print(f"   前5个值: {embedding[:5]}")
            return True
        else:
            print("❌ Embedding 返回 None")
            return False
    except Exception as e:
        print(f"❌ Embedding 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    print("\n" + "🚀 " * 25)
    print("\n   LLM 配置测试工具\n")
    print("🚀 " * 25 + "\n")
    
    all_passed = True
    
    # 测试配置
    if not test_config():
        all_passed = False
    
    # 测试客户端
    if not test_client():
        all_passed = False
    
    # 询问是否测试 API 调用
    print("\n" + "-" * 50)
    choice = input("是否测试实际的 LLM API 调用? (y/n): ").strip().lower()
    if choice == 'y':
        if not test_llm_api():
            all_passed = False
    
    # 询问是否测试 Embedding
    choice = input("是否测试 Embedding 功能? (y/n): ").strip().lower()
    if choice == 'y':
        if not test_embedding():
            all_passed = False
    
    print("\n" + "=" * 50)
    if all_passed:
        print("✅ 所有测试通过!")
    else:
        print("⚠️ 部分测试未通过，请检查配置")
    print("=" * 50)

if __name__ == "__main__":
    main()
