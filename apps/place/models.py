from django.db import models

from apps.core.models import TimeStampModel


class Place(TimeStampModel):
    place_name = models.CharField(max_length=50)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    rating_avg = models.DecimalField(max_digits=2, decimal_places=1, null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    tags = models.ManyToManyField("Tag", related_name="places", blank=True)

    class Meta:
        indexes = [models.Index(fields=["place_name"])]

    def __str__(self):
        return self.place_name


class PlaceImage(models.Model):
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE)
    image_url = models.CharField(max_length=255, default="default_image_url")


class Tag(models.Model):
    tag_type = models.CharField(max_length=20)
    tag_name = models.CharField(max_length=20)
