from django.template import RequestContext
from django.templatetags.static import static

from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from ..attachments.models import Attachment
from ..conf import settings
from ..parser.parse import parse
from ..parser.richtext import replace_rich_text_tokens
from ..threads.models import Post
from ..threads.prefetch import prefetch_post_feed_data
from . import common_flavour, finalize_markup
from .serializers import MarkupSerializer, PreviewMarkupSerializer


@api_view(["POST"])
def parse_markup(request):
    serializer = MarkupSerializer(
        data=request.data, context={"settings": request.settings}
    )
    if not serializer.is_valid():
        errors_list = list(serializer.errors.values())[0]
        return Response({"detail": errors_list[0]}, status=status.HTTP_400_BAD_REQUEST)

    parsing_result = common_flavour(
        request, request.user, serializer.data["post"], force_shva=True
    )
    finalized = finalize_markup(parsing_result["parsed_text"])

    return Response({"parsed": finalized})


@api_view(["POST"])
def preview_markup(request):
    serializer = PreviewMarkupSerializer(data=request.data)
    if not serializer.is_valid():
        errors_list = list(serializer.errors.values())[0]
        return Response({"detail": errors_list[0]}, status=status.HTTP_400_BAD_REQUEST)

    parsing_result = parse(serializer.data.get("post") or "")

    data = prefetch_post_feed_data(
        request.settings,
        request.user_permissions,
        get_quoted_posts(parsing_result.metadata),
        attachments=get_attachments(serializer.data.get("attachments")),
    )

    context = RequestContext(
        request, {"BLANK_AVATAR_URL": get_blank_avatar_url(request)}
    )

    return Response(
        {"html": replace_rich_text_tokens(parsing_result.html, context, data, None)}
    )


def get_blank_avatar_url(request) -> str:
    return request.settings.blank_avatar or static(settings.MISAGO_BLANK_AVATAR)


def get_quoted_posts(metadata: dict | None) -> list[Post]:
    post_ids = (metadata or {}).get("posts") or []
    if not post_ids:
        return []

    return list(Post.objects.filter(id__in=post_ids))


def get_attachments(attachment_ids: list[int] | None) -> list[Attachment]:
    if not attachment_ids:
        return []

    return list(Attachment.objects.filter(id__in=attachment_ids))
