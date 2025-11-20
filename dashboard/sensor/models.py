from django.db import models
from django.utils import timezone

# 온도 센서 테이블
class TemperatureSensor(models.Model):
	reg_date = models.DateTimeField(editable=False)
	value = models.FloatField()
	def save(self, *args, **kwargs):
		if not self.id:
			self.reg_date = timezone.now()
		return super(TemperatureSensor, self).save(*args, **kwargs)

# 습도 센서 테이블
class HumiditySensor(models.Model):
	reg_date = models.DateTimeField(editable=False)
	value = models.FloatField()

	def save(self, *args, **kwargs):
		if not self.id:
			self.reg_date = timezone.now()
		return super(HumiditySensor, self).save(*args, **kwargs)

# 진동 센서 테이블
class VibratorSensor(models.Model):
	reg_date = models.DateTimeField(editable=False)
	value = models.BooleanField()

	def save(self, *args, **kwargs):
		if not self.id:
			self.reg_date = timezone.now()
		return super(LightSensor, self).save(*args, **kwargs)

# 근접 센서 테이블
class ProximitySensor(models.Model):
	reg_date = models.DateTimeField(editable=False)
	value = models.FloatField()

	def save(self, *args, **kwargs):
		if not self.id:
			self.reg_date = timezone.now()
		return super(ProximitySensor, self).save(*args, **kwargs)

# Create your models here.
