from django.db import models
from django.utils import timezone


class ActivityEntry(models.Model):
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    actor_id = models.IntegerField(null=True, blank=True, db_index=True)
    actor_name = models.CharField(max_length=150, blank=True, db_index=True)
    source = models.CharField(max_length=40)
    operation_id = models.CharField(max_length=32, db_index=True)
    action = models.CharField(max_length=10, choices=[('create', 'Create'), ('update', 'Update'), ('delete', 'Delete')], db_index=True)
    reason = models.TextField()
    record_type = models.CharField(max_length=100, db_index=True)
    record_id = models.CharField(max_length=100)
    record_identity = models.CharField(max_length=100, db_index=True)
    before = models.JSONField(null=True, blank=True)
    after = models.JSONField(null=True, blank=True)

    class Meta:
        ordering = ['-id']
        verbose_name = 'Activity log entry'
        verbose_name_plural = 'Activity log'
        indexes = [models.Index(fields=['record_type', 'record_id'], name='activity_record_idx')]

    def save(self, *args, **kwargs):
        raise TypeError('Activity history is written only by database triggers.')

    def delete(self, *args, **kwargs):
        raise TypeError('Activity history cannot be deleted.')

    def __str__(self):
        return f'{self.timestamp}: {self.action} {self.record_type} #{self.record_id}'
