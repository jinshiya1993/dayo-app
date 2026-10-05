import logging

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import (
    AIMessage, HumanMessage, SystemMessage, ToolMessage,
)

from ..models import ChatConversation, ChatMessage
from .ai_context import AIContextAssembler
from .chat_tools import (
    READ_ONLY_TOOLS, describe_action, execute_tool, get_all_tools,
)

logger = logging.getLogger(__name__)

# How many times the model may look something up before it has to answer.
# Every step resends the whole system prompt, so this is a cost ceiling as
# much as a safety one. Four covers 'check schedule, check plan, propose'.
MAX_TOOL_STEPS = 4


class ChatService:

    def __init__(self):
        base_llm = ChatGoogleGenerativeAI(
            model='gemini-2.5-flash',
            google_api_key=settings.GEMINI_API_KEY,
            temperature=0.7,
            max_output_tokens=2048,
            transport='rest',
        )
        self.llm = base_llm.bind_tools(get_all_tools())

    def send_message(self, conversation, user_message_text):
        """Save user message, call Gemini with tools, handle tool calls as pending actions."""

        # Auto-cancel any stale pending actions in this conversation
        conversation.messages.filter(
            action_status=ChatMessage.ActionStatus.PENDING
        ).update(action_status=ChatMessage.ActionStatus.CANCELLED)

        # Save user message
        ChatMessage.objects.create(
            conversation=conversation,
            role=ChatMessage.Role.USER,
            content=user_message_text,
        )

        # Build enriched system prompt
        assembler = AIContextAssembler(conversation.profile)
        system_prompt = assembler.build_chat_context()

        # Load recent messages (last 10)
        recent = list(conversation.messages.order_by('-created_at')[:10])
        recent.reverse()

        # Build message list
        messages = [SystemMessage(content=system_prompt)]
        for msg in recent:
            if msg.role == 'user':
                messages.append(HumanMessage(content=msg.content))
            elif msg.role == 'assistant':
                messages.append(AIMessage(content=msg.content))

        try:
            # Agent loop. Read-only tools run immediately and their result is
            # fed back, so the model can chain lookups ("which of Arya's events
            # are today?" then "what is planned for dinner?") before deciding.
            # Anything that WRITES breaks the loop and goes to the user for
            # confirmation exactly as before -- the model never mutates data
            # on its own.
            assistant_msg = None

            for step in range(MAX_TOOL_STEPS):
                response = self.llm.invoke(messages)

                if not response.tool_calls:
                    assistant_msg = ChatMessage.objects.create(
                        conversation=conversation,
                        role=ChatMessage.Role.ASSISTANT,
                        content=response.content,
                    )
                    break

                writes = [
                    tc for tc in response.tool_calls
                    if tc["name"] not in READ_ONLY_TOOLS
                ]
                if writes:
                    tc = writes[0]
                    pending = {
                        "tool_name": tc["name"],
                        "tool_args": tc["args"],
                        "description": describe_action(tc["name"], tc["args"]),
                    }
                    content = response.content or pending["description"]
                    assistant_msg = ChatMessage.objects.create(
                        conversation=conversation,
                        role=ChatMessage.Role.ASSISTANT,
                        content=content,
                        pending_action=pending,
                        action_status=ChatMessage.ActionStatus.PENDING,
                    )
                    break

                # All reads. Run them and hand the results back so the next
                # invoke() can use what this one learned.
                messages.append(response)
                for tc in response.tool_calls:
                    result = execute_tool(
                        tc["name"], tc["args"], conversation.profile
                    )
                    messages.append(ToolMessage(
                        content=str(result.get("message", "")),
                        tool_call_id=tc["id"],
                    ))
            else:
                # Ran out of steps without settling on an answer. Usually means
                # the tool descriptions are unclear rather than that the budget
                # is too small -- worth reading the logs if this recurs.
                logger.warning(
                    'Chat hit MAX_TOOL_STEPS for conversation %s', conversation.id
                )
                assistant_msg = ChatMessage.objects.create(
                    conversation=conversation,
                    role=ChatMessage.Role.ASSISTANT,
                    content="Sorry, I got a bit tangled up there. Could you ask me that again?",
                )

            # Update conversation title from first exchange
            if conversation.title == 'New Chat' and conversation.messages.count() == 2:
                conversation.title = user_message_text[:50]
                conversation.save()

            return assistant_msg

        except Exception as e:
            logger.error(f'Chat service error: {e}')
            return ChatMessage.objects.create(
                conversation=conversation,
                role=ChatMessage.Role.ASSISTANT,
                content="Sorry, I couldn't process that right now. Please try again.",
            )
