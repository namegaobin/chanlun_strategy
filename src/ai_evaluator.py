"""
AI 评估模块 - 借鉴 chanlun_ai_Binance 架构
功能：调用 LLM 评估交易信号质量、生成操作建议
"""
import os
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
import requests

logger = logging.getLogger(__name__)


# ============================================
# AI 输出 Schema 定义
# ============================================

AI_EVALUATION_SCHEMA = {
    "version": "2.0",
    "meta": {
        "stock_code": "string",
        "price": "number",
        "timestamp": "string",
        "market_status": "string"
    },
    "structure_analysis": {
        "current_trend": "string (up/down/sideways)",
        "zhongshu": {
            "zg": "number",
            "zd": "number",
            "relation": "string (above/below/inside)"
        },
        "latest_bi": {
            "direction": "string",
            "is_done": "boolean",
            "strength": "string (strong/medium/weak)"
        }
    },
    "signal_evaluation": {
        "signal_type": "string (third_buy/limit_up_breakout)",
        "confidence": "number (0-100)",
        "quality_score": "number (0-100)",
        "risk_reward_ratio": "number",
        "entry_price_zone": ["number", "number"],
        "stop_loss": "number",
        "take_profit": "number"
    },
    "market_context": {
        "trend_alignment": "boolean",
        "volume_confirmation": "boolean",
        "divergence_risk": "string (none/low/medium/high)"
    },
    "action_recommendation": {
        "action": "string (buy/wait/avoid)",
        "position_size": "string (aggressive/normal/conservative)",
        "reasoning": "string",
        "warnings": ["string"]
    }
}


# ============================================
# LLM 调用封装（借鉴 chanlun_ai_Binance/ai/llm.py）
# ============================================

@dataclass
class LLMConfig:
    """LLM 配置"""
    model: str
    base_url: str
    api_key: str
    temperature: float = 0.2
    max_tokens: int = 2048
    timeout: float = 60.0
    extra_headers: Optional[Dict[str, str]] = None


class LLMClient:
    """LLM 客户端封装（OpenAI Chat Completions 兼容）"""
    
    def __init__(self, config: LLMConfig):
        self.config = config
        self.endpoint = config.base_url.rstrip("/") + "/chat/completions"
        
    def generate(self, prompt: str) -> str:
        """
        调用 LLM 生成回复
        
        Args:
            prompt: 完整的提示词
            
        Returns:
            AI 回复文本
        """
        if not isinstance(prompt, str) or not prompt:
            raise ValueError("prompt 必须是非空字符串")
            
        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }
        
        if self.config.extra_headers:
            headers.update(self.config.extra_headers)
            
        payload = {
            "model": self.config.model,
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的缠论量化分析师。你必须输出纯JSON格式，不要包含任何解释、推理过程或markdown标记。直接返回符合Schema的JSON对象。"
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        
        try:
            response = requests.post(
                self.endpoint,
                headers=headers,
                json=payload,
                timeout=self.config.timeout
            )
        except requests.RequestException as e:
            raise RuntimeError(f"LLM 请求失败: {e}")
            
        if not response.ok:
            raise RuntimeError(f"LLM 请求失败: HTTP {response.status_code}, {response.text}")
            
        try:
            data = response.json()
        except ValueError as e:
            raise RuntimeError(f"LLM 响应不是有效JSON: {response.text}")
            
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError(f"LLM 响应无 choices: {data}")
            
        message = choices[0].get("message", {})
        content = message.get("content", "")
        
        # 支持 reasoning_content（DeepSeek 等）
        if not content:
            content = message.get("reasoning_content", "")
            
        if not content:
            raise RuntimeError(f"LLM 响应无有效内容: {data}")
            
        return content


def call_ai(
    prompt: str,
    model: str = None,
    api_key: str = None,
    provider: str = "deepseek",
    temperature: float = 0.2,
    max_tokens: int = 2048
) -> str:
    """
    通用 AI 调用入口
    
    Args:
        prompt: 完整提示词
        model: 模型名称
        api_key: API密钥
        provider: 服务商 (deepseek/openrouter/siliconflow)
        
    Returns:
        AI 回复文本
    """
    # 从环境变量读取默认值
    model = model or os.getenv("AI_MODEL", "deepseek-chat")
    api_key = api_key or os.getenv("AI_API_KEY", "")
    
    if not api_key:
        raise ValueError("AI_API_KEY 未配置，请设置环境变量")
        
    provider = provider.lower()
    
    # 根据服务商配置 base_url
    base_urls = {
        "deepseek": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"),
        "openrouter": "https://openrouter.ai/api/v1",
        "siliconflow": "https://api.siliconflow.cn/v1",
    }
    
    base_url = base_urls.get(provider)
    if not base_url:
        raise ValueError(f"不支持的 provider: {provider}")
        
    config = LLMConfig(
        model=model,
        base_url=base_url,
        api_key=api_key,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=180.0 if provider in ["deepseek", "siliconflow"] else 60.0
    )
    
    client = LLMClient(config)
    return client.generate(prompt)


# ============================================
# Prompt 构建
# ============================================

def build_evaluation_prompt(
    stock_code: str,
    price: float,
    structure_data: Dict,
    signal_data: Dict,
    market_status: str,
    history_stats: Optional[Dict] = None
) -> str:
    """
    构建 AI 评估 Prompt
    
    Args:
        stock_code: 股票代码
        price: 当前价格
        structure_data: 缠论结构数据
        signal_data: 信号数据
        market_status: 市场状态
        history_stats: 历史统计
        
    Returns:
        完整 Prompt
    """
    # 缠论结构摘要
    zhongshu = structure_data.get('zhongshu', {})
    structure_summary = f"""
【缠论结构分析】
股票代码: {stock_code}
当前价格: {price}
市场环境: {market_status}

中枢状态:
- ZG (中枢高点): {zhongshu.get('zg', 'N/A')}
- ZD (中枢低点): {zhongshu.get('zd', 'N/A')}
- 中枢中轴: {zhongshu.get('middle', 'N/A')}

当前笔:
- 方向: {structure_data.get('bi_direction', 'N/A')}
- 是否完成: {structure_data.get('bi_done', False)}
- 力度评估: {structure_data.get('bi_strength', 'N/A')}
"""
    
    # 信号摘要
    signal_summary = f"""
【信号信息】
信号类型: {signal_data.get('signal_type', 'N/A')}
信号强度: {signal_data.get('strength', 'N/A')}
触发条件: {signal_data.get('trigger_condition', 'N/A')}
涨停状态: {signal_data.get('limit_up_info', 'N/A')}
"""
    
    # 历史统计（可选）
    stats_block = ""
    if history_stats:
        stats_block = f"""
【历史准确率统计】
总体准确率: {history_stats.get('accuracy', 'N/A')}%
平均盈亏比: {history_stats.get('avg_rr', 'N/A')}
最近10次: {history_stats.get('recent_10', 'N/A')}
"""
    
    # 输出格式约束
    output_block = f"""
【输出要求】
你必须严格按照以下 JSON Schema 输出，不要添加任何解释：

{json.dumps(AI_EVALUATION_SCHEMA, indent=2, ensure_ascii=False)}

现在请根据以上信息进行专业分析并输出JSON：
"""
    
    return f"{structure_summary}\n{signal_summary}\n{stats_block}\n{output_block}"


# ============================================
# AI 评估器
# ============================================

class AIEvaluator:
    """AI 评估器"""
    
    def __init__(
        self,
        model: str = None,
        api_key: str = None,
        provider: str = "deepseek"
    ):
        """
        Args:
            model: 模型名称
            api_key: API密钥
            provider: 服务商
        """
        self.model = model or os.getenv("AI_MODEL", "deepseek-chat")
        self.api_key = api_key or os.getenv("AI_API_KEY", "")
        self.provider = provider
        
    def evaluate_signal(
        self,
        stock_code: str,
        price: float,
        structure_data: Dict,
        signal_data: Dict,
        market_status: str = "neutral",
        history_stats: Optional[Dict] = None
    ) -> Dict:
        """
        评估交易信号
        
        Args:
            stock_code: 股票代码
            price: 当前价格
            structure_data: 缠论结构数据
            signal_data: 信号数据
            market_status: 市场状态
            history_stats: 历史统计
            
        Returns:
            评估结果字典
        """
        try:
            # 构建 Prompt
            prompt = build_evaluation_prompt(
                stock_code=stock_code,
                price=price,
                structure_data=structure_data,
                signal_data=signal_data,
                market_status=market_status,
                history_stats=history_stats
            )
            
            # 调用 AI
            response = call_ai(
                prompt=prompt,
                model=self.model,
                api_key=self.api_key,
                provider=self.provider
            )
            
            # 解析 JSON
            result = self._parse_response(response)
            
            return {
                "success": True,
                "evaluation": result,
                "raw_response": response
            }
            
        except Exception as e:
            logger.error(f"AI 评估失败: {e}")
            return {
                "success": False,
                "error": str(e)
            }
            
    def _parse_response(self, response: str) -> Dict:
        """解析 AI 响应"""
        try:
            # 尝试直接解析 JSON
            return json.loads(response)
        except json.JSONDecodeError:
            # 尝试提取 JSON 块
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except:
                    pass
                    
        # 返回原始响应
        return {"raw_text": response}
        
    def quick_evaluate(
        self,
        stock_code: str,
        signal_type: str,
        price: float,
        zhongshu: Dict
    ) -> Dict:
        """
        快速评估（简化版）
        
        适用于实时信号过滤
        """
        prompt = f"""
快速评估：{stock_code}
信号类型：{signal_type}
当前价格：{price}
中枢：ZG={zhongshu.get('zg')}, ZD={zhongshu.get('zd')}

请输出简短JSON：
{{"action": "buy/wait/avoid", "confidence": 0-100, "reason": "一句话理由"}}
"""
        try:
            response = call_ai(
                prompt=prompt,
                model=self.model,
                api_key=self.api_key,
                provider=self.provider,
                max_tokens=256
            )
            return self._parse_response(response)
        except Exception as e:
            logger.error(f"快速评估失败: {e}")
            return {"action": "wait", "confidence": 0, "error": str(e)}


# ============================================
# 便捷函数
# ============================================

def evaluate_third_buy_point(
    stock_code: str,
    price: float,
    zhongshu: Dict,
    market_status: str = "neutral"
) -> Dict:
    """
    评估第三类买点信号
    
    便捷函数，用于快速评估
    """
    evaluator = AIEvaluator()
    
    signal_data = {
        "signal_type": "third_buy",
        "strength": "待评估",
        "trigger_condition": "涨停后回抽不破ZG"
    }
    
    structure_data = {
        "zhongshu": zhongshu
    }
    
    return evaluator.evaluate_signal(
        stock_code=stock_code,
        price=price,
        structure_data=structure_data,
        signal_data=signal_data,
        market_status=market_status
    )
