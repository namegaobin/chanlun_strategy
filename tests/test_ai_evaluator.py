"""
AI 评估模块测试
测试 LLM 调用、Prompt 构建、信号评估
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
import json


class TestAIEvaluator:
    """AI 评估器测试类"""

    # ==================== P0: 核心功能 ====================

    def test_llm_client_initialization(self):
        """
        TC051 - P0: LLM 客户端初始化
        Given: API配置
        When: 初始化客户端
        Then: 成功创建客户端实例
        """
        # Given
        from src.ai_evaluator import LLMConfig, LLMClient
        
        config = LLMConfig(
            model="deepseek-chat",
            base_url="https://api.deepseek.com/v1",
            api_key="test_key"
        )
        
        # When
        client = LLMClient(config)
        
        # Then
        assert client.config.model == "deepseek-chat"
        assert client.endpoint.endswith("/chat/completions")

    @patch('src.ai_evaluator.requests.post')
    def test_llm_generate_success(self, mock_post):
        """
        TC052 - P0: LLM 生成成功
        Given: 有效 prompt 和 mock 响应
        When: 调用 generate
        Then: 返回 AI 回复
        """
        # Given
        from src.ai_evaluator import LLMClient, LLMConfig
        
        config = LLMConfig(
            model="test-model",
            base_url="https://api.test.com/v1",
            api_key="test_key"
        )
        client = LLMClient(config)
        
        # Mock 响应
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{
                "message": {"content": "AI 回复内容"}
            }]
        }
        mock_post.return_value = mock_response
        
        # When
        result = client.generate("测试 prompt")
        
        # Then
        assert result == "AI 回复内容"

    def test_build_evaluation_prompt(self):
        """
        TC053 - P0: Prompt 构建
        Given: 股票代码、价格、结构数据
        When: 构建 Prompt
        Then: 包含所有必需信息
        """
        from src.ai_evaluator import build_evaluation_prompt
        
        # Given
        structure_data = {
            'zhongshu': {'zg': 11.0, 'zd': 10.0, 'middle': 10.5},
            'bi_direction': 'up',
            'bi_done': True,
            'bi_strength': 'strong'
        }
        
        signal_data = {
            'signal_type': 'third_buy',
            'strength': 'strong',
            'trigger_condition': '涨停后回抽不破ZG'
        }
        
        # When
        prompt = build_evaluation_prompt(
            stock_code='sh.600000',
            price=10.8,
            structure_data=structure_data,
            signal_data=signal_data,
            market_status='bull'
        )
        
        # Then
        assert 'sh.600000' in prompt
        assert '10.8' in prompt
        assert '11.0' in prompt  # ZG
        assert '10.0' in prompt  # ZD
        assert 'third_buy' in prompt

    # ==================== P1: 异常处理 ====================

    def test_llm_invalid_prompt(self):
        """
        TC054 - P1: 无效 Prompt 处理
        Given: 空 prompt
        When: 调用 generate
        Then: 抛出 ValueError
        """
        from src.ai_evaluator import LLMClient, LLMConfig
        
        config = LLMConfig(
            model="test",
            base_url="https://test.com/v1",
            api_key="test"
        )
        client = LLMClient(config)
        
        # When & Then
        with pytest.raises(ValueError):
            client.generate("")

    @patch('src.ai_evaluator.requests.post')
    def test_llm_api_failure(self, mock_post):
        """
        TC055 - P1: API 调用失败
        Given: API 返回错误
        When: 调用 generate
        Then: 抛出 RuntimeError
        """
        from src.ai_evaluator import LLMClient, LLMConfig
        
        config = LLMConfig(
            model="test",
            base_url="https://test.com/v1",
            api_key="test"
        )
        client = LLMClient(config)
        
        # Mock 失败响应
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response
        
        # When & Then
        with pytest.raises(RuntimeError):
            client.generate("test prompt")

    def test_parse_json_response(self):
        """
        TC056 - P1: JSON 解析
        Given: AI 返回 JSON 字符串
        When: 解析响应
        Then: 返回字典
        """
        from src.ai_evaluator import AIEvaluator
        
        evaluator = AIEvaluator()
        
        # Given
        json_str = '{"action": "buy", "confidence": 80}'
        
        # When
        result = evaluator._parse_response(json_str)
        
        # Then
        assert result['action'] == 'buy'
        assert result['confidence'] == 80

    def test_parse_malformed_response(self):
        """
        TC057 - P1: 非法 JSON 处理
        Given: AI 返回非 JSON 文本
        When: 解析响应
        Then: 返回原始文本
        """
        from src.ai_evaluator import AIEvaluator
        
        evaluator = AIEvaluator()
        
        # Given
        text = "这是一段普通文本，不是JSON"
        
        # When
        result = evaluator._parse_response(text)
        
        # Then
        assert 'raw_text' in result

    # ==================== P2: 集成测试 ====================

    @patch('src.ai_evaluator.call_ai')
    def test_evaluate_signal_integration(self, mock_call_ai):
        """
        TC058 - P2: 信号评估集成测试
        Given: 完整的信号和结构数据
        When: 执行评估
        Then: 返回评估结果
        """
        from src.ai_evaluator import AIEvaluator
        
        # Mock AI 响应
        mock_call_ai.return_value = json.dumps({
            "action_recommendation": {
                "action": "buy",
                "confidence": 85,
                "reasoning": "第三类买点确认，突破有效"
            }
        })
        
        evaluator = AIEvaluator(api_key="test_key")
        
        # Given
        structure_data = {
            'zhongshu': {'zg': 11.0, 'zd': 10.0}
        }
        signal_data = {
            'signal_type': 'third_buy'
        }
        
        # When
        result = evaluator.evaluate_signal(
            stock_code='sh.600000',
            price=10.8,
            structure_data=structure_data,
            signal_data=signal_data
        )
        
        # Then
        assert result['success'] is True
        assert 'evaluation' in result

    @patch('src.ai_evaluator.call_ai')
    def test_quick_evaluate(self, mock_call_ai):
        """
        TC059 - P2: 快速评估
        Given: 简化参数
        When: 快速评估
        Then: 返回简要建议
        """
        from src.ai_evaluator import AIEvaluator
        
        mock_call_ai.return_value = '{"action": "buy", "confidence": 80}'
        
        evaluator = AIEvaluator(api_key="test_key")
        
        # When
        result = evaluator.quick_evaluate(
            stock_code='sh.600000',
            signal_type='third_buy',
            price=10.8,
            zhongshu={'zg': 11.0, 'zd': 10.0}
        )
        
        # Then
        assert result['action'] == 'buy'
        assert result['confidence'] == 80
