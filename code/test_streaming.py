"""Test the streaming pipeline end-to-end."""
import asyncio
import sys
import time

from backend.batch.utilities.helpers.env_helper import EnvHelper
from backend.batch.utilities.helpers.llm_helper import LLMHelper
from backend.batch.utilities.orchestrator.semantic_kernel import SemanticKernelOrchestrator


async def test_prepare_streaming():
    """Test the prepare_streaming method."""
    print("=" * 60)
    print("Testing prepare_streaming...")
    print("=" * 60)

    orchestrator = SemanticKernelOrchestrator()

    start = time.perf_counter()
    try:
        result = await orchestrator.prepare_streaming(
            user_message="What are the contract terms?",
            chat_history=[],
        )
        elapsed = time.perf_counter() - start
        print(f"\nprepare_streaming completed in {elapsed:.2f}s")
        print(f"streaming: {result['streaming']}")

        if result["streaming"]:
            print(f"question: {result['question']}")
            print(f"source_documents: {len(result['source_documents'])} docs")
            print(f"llm_messages: {len(result['llm_messages'])} messages")

            # Now test the actual streaming
            print("\n--- Streaming LLM response ---")
            llm_helper = LLMHelper()
            stream = llm_helper.get_chat_completion_streaming(
                result["llm_messages"], model=result["model"], temperature=0
            )
            full_text = ""
            token_count = 0
            first_token_time = None
            for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                if delta.content:
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - start
                        print(f"First token at {first_token_time:.2f}s")
                    full_text += delta.content
                    token_count += 1
                    sys.stdout.write(delta.content)
                    sys.stdout.flush()

            total_time = time.perf_counter() - start
            print(f"\n\n--- Done ---")
            print(f"Total tokens: {token_count}")
            print(f"Total time: {total_time:.2f}s")
            print(f"Time to first token: {first_token_time:.2f}s")
        else:
            print(f"messages: {len(result['messages'])} messages")
            for msg in result["messages"]:
                print(f"  role={msg.get('role')}, content={str(msg.get('content', ''))[:80]}...")

    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"\nError after {elapsed:.2f}s: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_prepare_streaming())
