from django.shortcuts import render
from oauth2_provider.contrib.rest_framework import TokenHasReadWriteScope
from rest_framework import generics


def documentation(request):
    return render(request, "api/documentation.html")


class MatchList(generics.ListAPIView):
    permission_classes = [TokenHasReadWriteScope]
