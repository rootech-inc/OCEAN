from django.db import models

class Agent(models.Model):
    PROVIDER_CHOICES = [
        ('chatgpt', 'ChatGPT'),
        ('claude', 'Claude'),
        ('gemini', 'Gemini'),
        ('grok', 'Grok'),
        ('other', 'Other'),
    ]

    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=50, choices=PROVIDER_CHOICES)
    api_key = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.provider})"
