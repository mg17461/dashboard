from django.db import models

class EPWFile(models.Model):
    file = models.FileField(upload_to='epw_files/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
