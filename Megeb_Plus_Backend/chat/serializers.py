from rest_framework import serializers

from .models import Conversation, Message


class MessageSerializer(serializers.ModelSerializer):

    sender_name = serializers.CharField(
        source="sender.full_name",
        read_only=True,
    )

    class Meta:
        model = Message

        fields = [
            "id",
            "conversation",
            "sender",
            "sender_name",
            "text",
            "is_read",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "conversation",
            "sender",
            "sender_name",
            "is_read",
            "created_at",
            "updated_at",
        ]


class ConversationSerializer(serializers.ModelSerializer):

    nutritionist_name = serializers.CharField(
        source="nutritionist.full_name",
        read_only=True,
    )

    client_name = serializers.CharField(
        source="client.full_name",
        read_only=True,
    )

    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Conversation

        fields = [
            "id",
            "nutritionist",
            "nutritionist_name",
            "client",
            "client_name",
            "last_message",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "nutritionist",
            "nutritionist_name",
            "client",
            "client_name",
            "last_message",
            "created_at",
            "updated_at",
        ]

    def get_last_message(self, obj):

        message = obj.messages.order_by(
            "-created_at"
        ).first()

        if not message:
            return None

        return MessageSerializer(message).data