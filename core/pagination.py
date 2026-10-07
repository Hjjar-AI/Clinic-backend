# backend/core/pagination.py
from urllib.parse import parse_qs, urlparse

from rest_framework.pagination import CursorPagination
from rest_framework.response import Response


class StandardResultsSetPagination(CursorPagination):
    page_size = 20
    ordering = '-id'
    page_size_query_param = 'per_page'
    max_page_size = 200
    cursor_query_param = 'cursor'

    def get_ordering(self, request, queryset, view):
        # Views validate their public sort keys before applying ORM ordering.
        # Preserve that validated ordering for cursor pagination instead of
        # silently forcing every list back to ``-id``.
        queryset_ordering = tuple(getattr(queryset.query, 'order_by', ()) or ())
        if queryset_ordering:
            return queryset_ordering
        return super().get_ordering(request, queryset, view)

    def _extract_cursor_token(self, link):
        """
        DRF's get_next_link()/get_previous_link() often returns a full URL.
        The frontend expects only the opaque cursor token.
        """
        if not link:
            return None

        try:
            parsed = urlparse(link)
            query = parse_qs(parsed.query)
            token = query.get(self.cursor_query_param, [None])[0]
            return token or link
        except Exception:
            return link

    def get_paginated_response(self, data):
        return Response(
            {
                'data': {
                    'items': data,
                    'meta': {
                        'next_cursor': self._extract_cursor_token(self.get_next_link()),
                        'previous_cursor': self._extract_cursor_token(self.get_previous_link()),
                        'has_more': self.has_next,
                    },
                }
            }
        )
