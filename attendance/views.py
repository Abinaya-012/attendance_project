from django.shortcuts import render, redirect
from django.utils import timezone
from django.http import JsonResponse
from django.contrib import messages
from .models import Student, Attendance
import datetime


# ── Session time rules ───────────────────────────────────────────
MORNING_START   = datetime.time(8, 0)     # 8:00 AM
MORNING_END     = datetime.time(9, 30)    # 9:30 AM

AFTERNOON_START = datetime.time(13, 40)    # 1:40 PM
AFTERNOON_END   = datetime.time(14, 15)   # 2:15 PM


def get_current_session():
    """
    Returns:
      'morning'   → if time is between 12:00 AM and 9:30 AM
      'afternoon' → if time is between 9:31 AM and 2:15 PM
      None        → outside both windows (attendance closed)
    """
    now = timezone.localtime(timezone.now()).time()
    if MORNING_START <= now <= MORNING_END:
        return 'morning'
    elif AFTERNOON_START <= now <= AFTERNOON_END:
        return 'afternoon'
    return None


def get_session_info():
    """Returns display info about current session status."""
    now = timezone.localtime(timezone.now()).time()
    session = get_current_session()

    if session == 'morning':
        return {
            'session':    'morning',
            'label':      'Morning Session',
            'open':       True,
            'closes_at':  '9:30 AM',
            'color':      'success',
            'icon':       '🌅'
        }
    elif session == 'afternoon':
        return {
            'session':    'afternoon',
            'label':      'Afternoon Session',
            'open':       True,
            'closes_at':  '2:15 PM',
            'color':      'success',
            'icon':       '🌤'
        }
    elif now < MORNING_START:
        return {
            'session':    None,
            'label':      'Attendance not started yet',
            'open':       False,
            'opens_at':   '8:00 AM',
            'color':      'secondary',
            'icon':       '🔒'
        }
    elif MORNING_END < now < AFTERNOON_START:
        # This gap is only 1 min (9:30 to 9:31) but handle gracefully
        return {
            'session':    None,
            'label':      'Morning closed. Afternoon opens at 9:31 AM',
            'open':       False,
            'color':      'warning',
            'icon':       '⏳'
        }
    else:
        return {
            'session':    None,
            'label':      'Attendance closed for today',
            'open':       False,
            'color':      'danger',
            'icon':       '🔒'
        }


# ── Register student ─────────────────────────────────────────────
def register_student(request):
    if request.method == 'POST':
        name       = request.POST.get('name')
        student_id = request.POST.get('student_id')
        email      = request.POST.get('email', '')

        if Student.objects.filter(student_id=student_id).exists():
            messages.error(request, 'A student with this ID already exists.')
        else:
            Student.objects.create(name=name, student_id=student_id, email=email)
            messages.success(request, f'{name} registered successfully!')
        return redirect('register')

    return render(request, 'attendance/register.html')


# ── Scanner page ─────────────────────────────────────────────────
def scan_attendance(request):
    session_info = get_session_info()
    now          = timezone.localtime(timezone.now())

    # Block on Sundays (weekday() == 6 is Sunday)
    if now.weekday() == 6:
        session_info = {
            'session': None,
            'label':   'No attendance on Sundays',
            'open':    False,
            'color':   'secondary',
            'icon':    '📅'
        }

    return render(request, 'attendance/scan.html', {
        'session_info': session_info,
        'now':          now
    })


# ── Mark attendance API ──────────────────────────────────────────
def mark_attendance(request):
    if request.method == 'POST':
        import json
        data    = json.loads(request.body)
        barcode = data.get('barcode', '').strip()
        now     = timezone.localtime(timezone.now())

        # Block Sundays
        if now.weekday() == 6:
            return JsonResponse({
                'status':  'error',
                'message': '❌ No attendance on Sundays.'
            })

        # Get current session
        session = get_current_session()
        if not session:
            current_time = now.strftime('%I:%M %p')
            return JsonResponse({
                'status':  'closed',
                'message': f'🔒 Attendance is closed at {current_time}. Morning closes at 9:30 AM, Afternoon closes at 2:15 PM.'
            })

        # Find student
        try:
            student = Student.objects.get(student_id=barcode)
        except Student.DoesNotExist:
            return JsonResponse({
                'status':  'error',
                'message': '❌ Student not found. Please register first.'
            })

        today = now.date()

        # Check if already marked for this session today
        existing = Attendance.objects.filter(
            student=student,
            date=today,
            session=session
        ).first()

        if existing:
            session_label = 'Morning' if session == 'morning' else 'Afternoon'
            return JsonResponse({
                'status':  'already',
                'message': f'ℹ️ {student.name} already marked present for {session_label} session today.',
                'student_name': student.name,
                'time': existing.time_in.strftime('%I:%M %p')
            })

        # Mark attendance
        record = Attendance.objects.create(
            student=student,
            session=session
        )

        session_label = 'Morning 🌅' if session == 'morning' else 'Afternoon 🌤'
        return JsonResponse({
            'status':       'success',
            'message':      f'✅ {student.name} marked present — {session_label}',
            'student_name': student.name,
            'time':         record.time_in.strftime('%I:%M %p'),
            'session':      session_label
        })

    return JsonResponse({'status': 'error', 'message': 'Invalid request'})


# ── Dashboard ─────────────────────────────────────────────────────
def dashboard(request):
    today          = timezone.localtime(timezone.now()).date()
    total_students = Student.objects.count()

    morning_present   = Attendance.objects.filter(date=today, session='morning').count()
    afternoon_present = Attendance.objects.filter(date=today, session='afternoon').count()

    morning_absent    = total_students - morning_present
    afternoon_absent  = total_students - afternoon_present

    morning_pct   = round((morning_present / total_students * 100), 1) if total_students > 0 else 0
    afternoon_pct = round((afternoon_present / total_students * 100), 1) if total_students > 0 else 0

    # Last 7 days both sessions
    from datetime import timedelta
    last_7 = []
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        last_7.append({
            'date':      day.strftime('%b %d'),
            'morning':   Attendance.objects.filter(date=day, session='morning').count(),
            'afternoon': Attendance.objects.filter(date=day, session='afternoon').count(),
        })

    # Recent check-ins today
    recent = Attendance.objects.filter(date=today).select_related('student').order_by('-time_in')[:15]

    context = {
        'total_students':   total_students,
        'morning_present':  morning_present,
        'morning_absent':   morning_absent,
        'morning_pct':      morning_pct,
        'afternoon_present': afternoon_present,
        'afternoon_absent': afternoon_absent,
        'afternoon_pct':    afternoon_pct,
        'last_7':           last_7,
        'recent':           recent,
        'today':            today,
    }
    return render(request, 'attendance/dashboard.html', context)