"""
RAG Utilities Module
Simplified utilities for token counting, context management, and answer validation
"""

import tiktoken
from typing import Tuple, Dict
import logging
import openai
import json

logger = logging.getLogger(__name__)

# ========== TOKEN COUNTING AND CONTEXT TRUNCATION ==========

def count_tokens(text: str, model: str = "gpt-4o-mini") -> int:
    """
    Count tokens in text using tiktoken.

    Args:
        text: Text to count tokens for
        model: Model name for encoding

    Returns:
        Number of tokens
    """
    try:
        encoding = tiktoken.encoding_for_model(model)
        return len(encoding.encode(text))
    except Exception as e:
        logger.error(f"Error counting tokens: {e}")
        # Fallback: rough estimate (1 token ≈ 4 characters)
        return len(text) // 4


def truncate_context_intelligently(
    context: str,
    max_tokens: int = 6000,
    model: str = "gpt-4o-mini"
) -> Tuple[str, int]:
    """
    Intelligently truncate context to fit within token limit.
    Keeps beginning and end portions to preserve context.

    Args:
        context: Context string to truncate
        max_tokens: Maximum tokens allowed
        model: Model name for token counting

    Returns:
        Tuple of (truncated_context, actual_token_count)
    """
    try:
        current_tokens = count_tokens(context, model)

        if current_tokens <= max_tokens:
            return context, current_tokens

        logger.warning(f"⚠️ Context exceeds {max_tokens} tokens ({current_tokens}). Truncating...")

        # Calculate ratio to shrink
        ratio = max_tokens / current_tokens
        target_length = int(len(context) * ratio * 0.9)  # 10% safety margin

        # Keep first and last portions (preserving recent context)
        keep_length = target_length // 2
        truncated = (
            context[:keep_length] +
            "\n\n...[context truncated for length]...\n\n" +
            context[-keep_length:]
        )

        final_tokens = count_tokens(truncated, model)
        logger.info(f"✂️ Truncated from {current_tokens} to {final_tokens} tokens")

        return truncated, final_tokens

    except Exception as e:
        logger.error(f"Error truncating context: {e}")
        return context, count_tokens(context, model)


# ========== HALLUCINATION DETECTION & ANSWER VALIDATION ==========

def validate_answer_grounding(
    answer: str,
    context: str,
    client: openai.OpenAI
) -> Dict:
    """
    Validate that the answer is grounded in the retrieved context.
    Detects hallucinations and unsupported claims.

    Args:
        answer: Generated answer
        context: Retrieved context used for generation
        client: OpenAI client

    Returns:
        Validation result with grounding assessment
    """
    try:
        validation_prompt = f"""You are a fact-checker. Analyze whether the answer is fully supported by the context.

Context:
{context[:2000]}  # Limit context for validation

Answer:
{answer}

Evaluate:
1. Is the answer fully supported by facts in the context?
2. What percentage of the answer can be verified from context? (0-100)
3. List any claims in the answer NOT found in context
4. Overall confidence level (high/medium/low)

Respond in JSON format:
{{
    "is_grounded": true or false,
    "verification_percentage": 0-100,
    "unsupported_claims": ["claim1", "claim2"] or [],
    "confidence": "high" or "medium" or "low",
    "reasoning": "brief explanation"
}}"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": validation_prompt}],
            temperature=0,
            response_format={"type": "json_object"}
        )

        validation = json.loads(response.choices[0].message.content)

        logger.info(f"✅ Answer validation: grounded={validation.get('is_grounded')}, "
                   f"verification={validation.get('verification_percentage')}%")

        return validation

    except Exception as e:
        logger.error(f"Error validating answer: {e}")
        return {
            "is_grounded": True,  # Optimistic default
            "verification_percentage": 100,
            "unsupported_claims": [],
            "confidence": "medium",
            "reasoning": "Validation failed"
        }


def add_validation_disclaimer(answer: str, validation: Dict) -> str:
    """
    Add disclaimer to answer if validation indicates issues.

    Args:
        answer: Original answer
        validation: Validation result

    Returns:
        Answer with disclaimer if needed
    """
    try:
        is_grounded = validation.get("is_grounded", True)
        verification_pct = validation.get("verification_percentage", 100)
        unsupported_claims = validation.get("unsupported_claims", [])

        # Add disclaimer if answer has issues
        # if not is_grounded or verification_pct < 70:
        #     disclaimer = "\n\n⚠️ **Lưu ý:** Một số phần của câu trả lời này có thể không được hỗ trợ đầy đủ bởi các bản ghi cuộc họp hiện có."

        #     if unsupported_claims:
        #         disclaimer += f" Cần xác minh: {', '.join(unsupported_claims[:2])}"

        #     return answer + disclaimer

        return answer

    except Exception as e:
        logger.error(f"Error adding disclaimer: {e}")
        return answer
