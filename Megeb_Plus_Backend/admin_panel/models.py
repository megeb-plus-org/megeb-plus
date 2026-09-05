from django.db import models


class PlatformSettings(models.Model):
    """
    Singleton model — there is only ever one row (pk=1). Holds platform-wide
    configuration the admin can edit from the Settings page.
    """

    platform_name = models.CharField(max_length=100, default="Megeb+")
    support_email = models.EmailField(blank=True)
    maintenance_mode = models.BooleanField(default=False)
    email_notifications = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Settings"
        verbose_name_plural = "Platform Settings"

    def save(self, *args, **kwargs):
        self.pk = 1  # force singleton — always overwrite the same row
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _created = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return "Platform Settings"