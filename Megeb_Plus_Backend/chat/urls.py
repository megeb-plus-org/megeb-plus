from django.urls import path

from .views import (
    ConversationListView,
    ConversationDetailView,
    SendMessageView,
    MessageListView,
    MarkMessagesReadView,
)


urlpatterns = [

    path(
        "",
        ConversationListView.as_view(),
        name="conversation-list",
    ),

    path(
        "<int:conversation_id>/",
        ConversationDetailView.as_view(),
        name="conversation-detail",
    ),

    path(
        "<int:conversation_id>/messages/",
        MessageListView.as_view(),
        name="message-list",
    ),

    path(
        "<int:conversation_id>/messages/send/",
        SendMessageView.as_view(),
        name="send-message",
    ),

    path(
        "<int:conversation_id>/read/",
        MarkMessagesReadView.as_view(),
        name="mark-messages-read",
    ),
]