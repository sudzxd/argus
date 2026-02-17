"""Service protocols for the LLM bounded context.

With the adoption of pydantic-ai, the hand-rolled ``LLMProvider`` protocol has
been removed. pydantic-ai ``Agent`` serves as the LLM abstraction. The domain
layer defines *what* to ask the LLM (prompts, output schemas), and the
infrastructure layer creates ``Agent`` instances via ``ModelConfig``.
"""
