import logging

from django.conf import settings
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from ..models import ChatConversation, ChatMessage
from .ai_context import AIContextAssembler
from .chat_tools import describe_action, get_all_tools

logger = logging.getLogger(__name__)


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
            response = self.llm.invoke(messages)

            # Check if Gemini wants to call a tool
            if response.tool_calls:
                tc = response.tool_calls[0]
                pending = {
                    "tool_name": tc["name"],
                    "tool_args": tc["args"],
                    "description": describe_action(tc["name"], tc["args"]),
                }
                # Use LLM's text if provided, otherwise generate description
                content = response.content if response.content else pending["description"]

                assistant_msg = ChatMessage.objects.create(
                    conversation=conversation,
                    role=ChatMessage.Role.ASSISTANT,
                    content=content,
                    pending_action=pending,
                    action_status=ChatMessage.ActionStatus.PENDING,
                )
            else:
                # Normal text response
                assistant_msg = ChatMessage.objects.create(
                    conversation=conversation,
                    role=ChatMessage.Role.ASSISTANT,
                    content=response.content,
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
