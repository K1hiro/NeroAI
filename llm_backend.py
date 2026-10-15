from ollama import Client

MODEL_NAME = "qwen3:4b-instruct"
MAX_HISTORY_MESSAGES = 20

client = Client(host="http://localhost:11434")

SYSTEM_PROMPT = (
    "You are NeroAI, a friendly and helpful AI assistant. "
    "Always respond in English. "
    "Use the conversation history to understand follow-up questions. "
    "If you do not know something, say so clearly."
)


def generate_reply(
    user_message: str,
    history: list[dict[str, str]] | None = None,
) -> str:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
    ]

    if history:
        messages.extend(history[-MAX_HISTORY_MESSAGES:])

    messages.append(
        {"role": "user", "content": user_message}
    )

    response = client.chat(
        model=MODEL_NAME,
        messages=messages,
        stream=False,
    )

    return response.message.content


if __name__ == "__main__":
    example_history = [
        {"role": "user", "content": "My name is Budi."},
        {"role": "assistant", "content": "Hello, Budi!"},
    ]

    for number in range(10):
        example_history.extend([
            {"role": "user", "content": f"Test message {number + 1}."},
            {"role": "assistant", "content": "Message received."},
        ])

    print("Total history messages:", len(example_history))
    print("Messages sent from history:", MAX_HISTORY_MESSAGES)

    reply = generate_reply(
        "What is my name? If it is not in the conversation, say you don't know.",
        history=example_history,
    )
    print(reply)
