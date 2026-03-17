from django.db import models

class Student(models.Model):
    name        = models.CharField(max_length=100)
    student_id  = models.CharField(max_length=50, unique=True)
    email       = models.EmailField(blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.student_id})"


class Attendance(models.Model):
    SESSION_CHOICES = [
        ('morning',   'Morning (up to 9:30 AM)'),
        ('afternoon', 'Afternoon (up to 2:15 PM)'),
    ]
    student    = models.ForeignKey(Student, on_delete=models.CASCADE)
    date       = models.DateField(auto_now_add=True)
    session    = models.CharField(max_length=10, choices=SESSION_CHOICES,default='morning')
    time_in    = models.TimeField(auto_now_add=True)

    class Meta:
        # One record per student per session per day
        unique_together = ('student', 'date', 'session')

    def __str__(self):
        return f"{self.student.name} - {self.date} - {self.session}"