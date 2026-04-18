from django.db import models


class Book(models.Model):
    """
    Three typed columns + one JSONField. The JSONField (`misc`) is what makes
    plugin-style fields possible: new editable fields can live there without a
    migration. See `forms.JSONBackedMixin` for the write-path.
    """

    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    year = models.PositiveSmallIntegerField()
    misc = models.JSONField(
        default=dict,
        blank=True,
        help_text="Schemaless storage for plugin single-field forms",
    )

    def __str__(self):
        return f"{self.title} — {self.author} ({self.year})"
