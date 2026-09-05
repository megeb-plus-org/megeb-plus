from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import Conversation, Message
from .serializers import (
    ConversationSerializer,
    MessageSerializer,
)
class ConversationListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        conversations = Conversation.objects.filter(
            client=request.user
        ) | Conversation.objects.filter(
            nutritionist=request.user
        )

        conversations = conversations.distinct().order_by(
            "-updated_at"
        )

        serializer = ConversationSerializer(
            conversations,
            many=True
        )

        return Response(serializer.data)

    def post(self, request):

        nutritionist_id = request.data.get(
            "nutritionist"
        )

        if not nutritionist_id:
            return Response(
                {
                    "detail": "nutritionist is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if request.user.id == int(nutritionist_id):
            return Response(
                {
                    "detail": "You cannot create a conversation with yourself."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        conversation = Conversation.objects.filter(
            client=request.user,
            nutritionist_id=nutritionist_id
        ).first()

        if not conversation:
            conversation = Conversation.objects.create(
                client=request.user,
                nutritionist_id=nutritionist_id
            )

        serializer = ConversationSerializer(
            conversation
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED
        )
class ConversationDetailView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            return Response(
                {
                    "detail": "Conversation not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in [
            conversation.client,
            conversation.nutritionist,
        ]:
            return Response(
                {
                    "detail": "You are not part of this conversation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(
            ConversationSerializer(
                conversation
            ).data
        )
        
class SendMessageView(APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, conversation_id):

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            return Response(
                {
                    "detail": "Conversation not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in [
            conversation.client,
            conversation.nutritionist,
        ]:
            return Response(
                {
                    "detail": "You are not part of this conversation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        text = request.data.get("text")

        if not text or not text.strip():
            return Response(
                {
                    "detail": "Message text is required."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        message = Message.objects.create(
            conversation=conversation,
            sender=request.user,
            text=text.strip(),
        )

        conversation.save(
            update_fields=["updated_at"]
        )

        return Response(
            MessageSerializer(message).data,
            status=status.HTTP_201_CREATED
        )
class MessageListView(APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request, conversation_id):

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            return Response(
                {
                    "detail": "Conversation not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in [
            conversation.client,
            conversation.nutritionist,
        ]:
            return Response(
                {
                    "detail": "You are not part of this conversation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        messages = conversation.messages.order_by(
            "created_at"
        )

        return Response(
            MessageSerializer(
                messages,
                many=True
            ).data
        )
class MarkMessagesReadView(APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, conversation_id):

        try:
            conversation = Conversation.objects.get(
                id=conversation_id
            )
        except Conversation.DoesNotExist:
            return Response(
                {
                    "detail": "Conversation not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        if request.user not in [
            conversation.client,
            conversation.nutritionist,
        ]:
            return Response(
                {
                    "detail": "You are not part of this conversation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        conversation.messages.filter(
            is_read=False
        ).exclude(
            sender=request.user
        ).update(
            is_read=True
        )

        return Response(
            {
                "detail": "Messages marked as read."
            }
        )